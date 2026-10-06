# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Batch service for managing brewing batch data and operations."""
import logging
import uuid as _uuid
from datetime import UTC, date, datetime  # noqa: F401 (UTC used by soft_delete)
from typing import Any, List, Optional, Tuple, Union

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from core.enums import BatchStatus
from core.models.registry import resolve_model
from oss.schemas.batch import BatchCreate, BatchUpdate
from oss.services.base import BaseService

Batch = resolve_model("Batch")
Device = resolve_model("Device")
GravityReading = resolve_model("GravityReading")
StorageVessel = resolve_model("StorageVessel")

logger = logging.getLogger(__name__)


def _as_uuid(value: Union[str, _uuid.UUID]) -> _uuid.UUID:
    """Coerce a string or UUID to a uuid.UUID object for SQLAlchemy Uuid columns."""
    if isinstance(value, _uuid.UUID):
        return value
    return _uuid.UUID(str(value))


class BatchService(BaseService[Batch, BatchCreate, BatchUpdate]):
    """Service for managing brewing batch data and operations."""

    # `dry_hops` is created by the router in the same request flow; the schema's
    # `cost_per_liter` is a computed convenience property. Neither is a Batch
    # column, so list them explicitly instead of relying on BaseService to drop
    # unknown data silently.
    transient_fields = frozenset({"cost_per_liter", "dry_hops"})

    def __init__(self, db_session: Session):
        super().__init__(Batch, db_session)

    def _apply_status_transition(
        self, db_obj: Batch, obj: BatchUpdate, data: dict
    ) -> BatchUpdate:
        """Validate and apply every ``status``-transition side effect that does not
        involve the gravity-measurement backfill, which is kept in ``update()``.

        Deliberately its own method, not inlined in ``update()``: alternate update
        implementations can apply the common status-transition rules without
        duplicating them. **Any future `status`-transition rule belongs here.**

        - ``rating`` may only be set/changed while the resulting status (after this
          update is applied) is ``packaged`` or ``archived`` — rejected with 400
          otherwise. Checking the resulting status (not just the pre-existing one)
          allows setting a rating in the same request that transitions the batch to
          packaged/archived.
        - While ``status`` stays ``archived`` across this update, every other field
          is read-only — rejected with 400, since the batch exists but the edit is
          refused for its lifecycle state.
        - Archiving (``fermenting``/``packaged`` → ``archived``) ends chamber
          control in the same transaction if it was active — an archived batch is
          not under active control by definition, and this is what stops the
          chamber-reminder job from continuing to nag about it.
        - Un-archiving (``archived`` → anything else) ignores the client's literal
          status value and derives the real one: ``packaged`` if a `StorageVessel`
          is currently connected to the batch, otherwise ``fermenting`` — live
          state, not a replayed snapshot. See spec-data-model.md §5.7 "Archiving".

        Returns the (possibly replaced) ``obj`` for the caller to continue with.
        """
        current_status = db_obj.status
        requested_status = data.get("status")
        resulting_status = requested_status if requested_status is not None else current_status

        if (
            current_status == BatchStatus.ARCHIVED.value
            and resulting_status == BatchStatus.ARCHIVED.value
            # `cost_per_liter` is a computed_field: model_dump() always includes it,
            # exclude_unset or not, so it must not count as a real field edit here.
            and set(data) - {"status", "rating"} - self.transient_fields
        ):
            raise HTTPException(
                status_code=400,
                detail="Batch is archived and read-only; only status/rating may be changed.",
            )

        if data.get("rating") is not None and resulting_status not in (
            BatchStatus.PACKAGED.value,
            BatchStatus.ARCHIVED.value,
        ):
            raise HTTPException(
                status_code=400,
                detail="Rating can only be set once the batch is packaged or archived",
            )

        if (
            requested_status == BatchStatus.ARCHIVED.value
            and current_status == BatchStatus.FERMENTING.value
            and db_obj.chamber_control_active
        ):
            db_obj.chamber_control_active = False

        if (
            current_status == BatchStatus.ARCHIVED.value
            and requested_status is not None
            and requested_status != BatchStatus.ARCHIVED.value
        ):
            has_vessel = self.db_session.scalar(
                select(func.count())  # pylint: disable=not-callable
                .select_from(StorageVessel)
                .where(
                    StorageVessel.batch_id == db_obj.id,
                    StorageVessel.deleted_at.is_(None),
                )
            )
            actual_status = BatchStatus.PACKAGED if has_vessel else BatchStatus.FERMENTING
            obj = obj.model_copy(update={"status": actual_status})

        return obj

    def update(self, item_id: Any, obj: BatchUpdate) -> Optional[Batch]:
        """Update a batch, snapshotting measured gravity when status becomes PACKAGED.

        On transition to ``packaged``, ``og_measured``/``fg_measured`` are filled from
        the batch's gravity readings (first non-excluded reading for OG, last
        non-excluded reading for FG) but only when still NULL on the existing row, so
        a manual correction already in place is never overwritten by re-packaging.

        Every other ``status``-transition rule (rating gate, archived read-only,
        chamber-control cleanup, un-archive derivation) lives in
        ``_apply_status_transition`` — see its docstring.
        """
        data = obj.model_dump(exclude_unset=True)
        db_obj = self.get_active(item_id)
        if db_obj is None:
            return None

        obj = self._apply_status_transition(db_obj, obj, data)
        data = obj.model_dump(exclude_unset=True)
        requested_status = data.get("status")

        if requested_status == BatchStatus.PACKAGED.value:
            # Same snapshot the vessel-driven path applies, so a status set through
            # the API and one caused by filling a keg record the same gravities.
            updates: dict = {}
            if db_obj.og_measured is None:
                first_reading = self._first_gravity(db_obj.id)
                if first_reading is not None:
                    updates["og_measured"] = first_reading
            if db_obj.fg_measured is None:
                last_reading = self._last_gravity(db_obj.id)
                if last_reading is not None:
                    updates["fg_measured"] = last_reading
            if updates:
                obj = obj.model_copy(update=updates)

        return super().update(item_id, obj)

    def list(self) -> List[Batch]:
        """Return all non-deleted batches."""
        objs: List[Batch] = self.db_session.scalars(
            select(self.model).where(self.model.deleted_at.is_(None))
        ).all()
        return objs

    def search_device_id(self, device_id: Union[str, _uuid.UUID]) -> List[Batch]:
        """Search batches linked to a device (any role)."""
        uid = _as_uuid(device_id)
        objs: List[Batch] = self.db_session.scalars(
            select(self.model)
            .join(Device, Device.batch_id == self.model.id)
            .where(Device.id == uid, self.model.deleted_at.is_(None))
        ).all()
        logger.info("Fetched batches based on device_id=%s, records found %d", device_id, len(objs))
        return objs

    def search_accepting_ingest(self) -> List[Batch]:
        """Return all non-deleted batches that accept ingest."""
        objs: List[Batch] = self.db_session.scalars(
            select(self.model).where(
                self.model.accept_ingest,
                self.model.deleted_at.is_(None),
            )
        ).all()
        logger.info("Fetched accept_ingest batches, records found %d", len(objs))
        return objs

    def search_device_id_accepting(self, device_id: Union[str, _uuid.UUID]) -> List[Batch]:
        """Find batches linked to a device that are accepting ingest."""
        uid = _as_uuid(device_id)
        objs: List[Batch] = self.db_session.scalars(
            select(self.model)
            .join(Device, Device.batch_id == self.model.id)
            .where(
                Device.id == uid,
                self.model.accept_ingest,
                self.model.deleted_at.is_(None),
            )
        ).all()
        logger.info(
            "Fetched accepting batches for device_id=%s, records found %d", device_id, len(objs)
        )
        return objs

    def search_brewfather_id(self, brewfather_batch_id: str) -> List[Batch]:
        """Search batches by Brewfather batch ID."""
        objs: List[Batch] = self.db_session.scalars(
            select(self.model).where(
                self.model.brewfather_batch_id == brewfather_batch_id,
                self.model.deleted_at.is_(None),
            )
        ).all()
        logger.info(
            "Fetched batches based on brewfather_batch_id=%s, records found %d",
            brewfather_batch_id,
            len(objs),
        )
        return objs


    def get_names_by_ids(self, batch_ids: List[_uuid.UUID]) -> dict:
        """Return a map of batch_id → batch name for the given IDs."""
        if not batch_ids:
            return {}
        rows = self.db_session.execute(
            select(Batch.id, Batch.name).where(Batch.id.in_(batch_ids))
        ).all()
        return {row.id: row.name for row in rows}

    def soft_delete(self, batch_id: int) -> bool:
        """Soft-delete a batch by setting deleted_at."""
        batch = self.get(batch_id)
        if batch is None:
            return False
        batch.deleted_at = datetime.now(UTC)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return True

    def restore(self, batch_id) -> Optional[Any]:
        """Restore a soft-deleted batch; returns the batch or None if not soft-deleted."""
        batch = self.get(batch_id)
        if batch is None or batch.deleted_at is None:
            return None
        batch.deleted_at = None
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return batch

    def list_filtered(
        self,
        device_id: Optional[str] = None,
        retention_cutoff: Optional[datetime] = None,
    ) -> List[Batch]:
        """List batches with optional device_id and retention cutoff filters."""
        query = select(self.model).where(self.model.deleted_at.is_(None))
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)

        if device_id is not None:
            uid = _as_uuid(device_id)
            query = query.join(Device, Device.batch_id == self.model.id).where(Device.id == uid)

        objs: List[Batch] = self.db_session.scalars(query).all()
        logger.info("list_filtered: found %d batches", len(objs))
        return objs

    def mark_packaged(self, batch_id: Any, fill_date: Optional[date] = None) -> None:
        """Mark a batch packaged because a vessel was filled from it. Idempotent.

        Called when a keg or bottles become linked to a batch — putting beer into a
        cellar vessel *is* packaging it, so the transition follows the vessel rather
        than a separate "package" action the user has to remember. This replaced
        `POST /batches/{id}/package` and the modal that drove it, which asked for a
        fill date, conditioning days and carbonation target that were already fields
        on the batch form beside it.

        Does nothing unless the batch is still fermenting, so assigning a second keg
        cannot re-stamp the date or re-snapshot gravity, and an archived batch is never
        dragged back to packaged.

        Not committed here: the caller owns the transaction, so the vessel link and the
        batch transition succeed or fail together.
        """
        batch = self.get(batch_id)
        if batch is None or batch.deleted_at is not None:
            return
        if batch.status != BatchStatus.FERMENTING.value:
            return

        if batch.package_date is None:
            batch.package_date = fill_date or date.today()
        self._apply_gravity_snapshot(batch)
        batch.status = BatchStatus.PACKAGED.value

    def _apply_gravity_snapshot(self, batch: Any) -> None:
        """Fill og_measured/fg_measured from the batch's own readings, if still unset.

        Only when NULL: a manual correction already in place is never overwritten by
        packaging, or by re-packaging.
        """
        if batch.og_measured is None:
            first_reading = self._first_gravity(batch.id)
            if first_reading is not None:
                batch.og_measured = first_reading
        if batch.fg_measured is None:
            last_reading = self._last_gravity(batch.id)
            if last_reading is not None:
                batch.fg_measured = last_reading

    def _first_gravity(self, batch_id: Any) -> Optional[float]:
        """Return the earliest non-excluded gravity reading value for a batch, or None."""
        return self.db_session.scalars(
            select(GravityReading.gravity)
            .where(
                GravityReading.batch_id == batch_id,
                ~GravityReading.excluded,
            )
            .order_by(GravityReading.created_at.asc())
            .limit(1)
        ).first()

    def _last_gravity(self, batch_id: Any) -> Optional[float]:
        """Return the latest non-excluded gravity reading value for a batch, or None."""
        return self.db_session.scalars(
            select(GravityReading.gravity)
            .where(
                GravityReading.batch_id == batch_id,
                ~GravityReading.excluded,
            )
            .order_by(GravityReading.created_at.desc())
            .limit(1)
        ).first()

    def list_filtered_page(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        page: int = 1,
        page_size: int = 50,
        device_id: Optional[str] = None,
        retention_cutoff: Optional[datetime] = None,
    ) -> Tuple[List[Batch], int]:
        """Offset-paginated list_filtered returning (items, total)."""
        base_query = select(self.model).where(self.model.deleted_at.is_(None))
        if retention_cutoff is not None:
            base_query = base_query.where(self.model.created_at >= retention_cutoff)

        if device_id is not None:
            uid = _as_uuid(device_id)
            base_query = base_query.join(
                Device, Device.batch_id == self.model.id
            ).where(Device.id == uid)

        total: int = self.db_session.scalar(
            select(func.count()).select_from(base_query.subquery())  # pylint: disable=not-callable
        ) or 0
        offset = (page - 1) * page_size
        items: List[Batch] = list(
            self.db_session.scalars(base_query.offset(offset).limit(page_size)).all()
        )
        logger.info("list_filtered_page: page=%d total=%d returned=%d", page, total, len(items))
        return items, total
