# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""StorageVessel service."""
from datetime import UTC, datetime
from typing import Any, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from core.enums import BatchStatus, VesselStatus
from core.models.registry import resolve_model
from oss.schemas.registry import get as _s
from oss.schemas.storage_vessel import (StorageVesselCreate,
                                         StorageVesselUpdate)
from oss.services.base import BaseService
from oss.services.batch import BatchService
from oss.services.pour_event import PourEventService
from oss.services.tap import TapService

StorageVessel = resolve_model("StorageVessel")


class StorageVesselService(BaseService[StorageVessel, StorageVesselCreate, StorageVesselUpdate]):
    """Service for managing storage vessels (kegs and bottle batches)."""

    def __init__(self, db_session: Session):
        """Initialise with a SQLAlchemy session."""
        super().__init__(StorageVessel, db_session)

    def create(self, obj: StorageVesselCreate) -> StorageVessel:
        """Create a vessel, packaging its batch when it is created already linked.

        This is the bottles path — bottles have no reuse concept, so "add bottles"
        creates the vessel with `batch_id` set rather than assigning an existing one.
        It has to package the batch for the same reason `update()` does when a batch is
        linked, or which of the two the user happened to click would decide whether the
        batch ever left `fermenting`.
        """
        if obj.batch_id is not None:
            self._reject_archived_batch(obj.batch_id)
        if obj.tap_id is not None:
            self._reject_deleted_tap(obj.tap_id)
        vessel = self.build(obj)
        if obj.batch_id is not None:
            # Flush so mark_packaged() sees the vessel, then commit once: two commits
            # would leave a vessel attached to a batch that was never packaged if the
            # transition failed — still fermenting, no package_date, no gravity snapshot.
            self.db_session.flush()
            try:
                BatchService(self.db_session).mark_packaged(vessel.batch_id, vessel.fill_date)
            except Exception:
                # Drop the flushed vessel too — the session outlives this call and
                # would otherwise commit it on the way out of the request.
                self.db_session.rollback()
                raise
        self.commit()
        return vessel

    def _reject_archived_batch(self, batch_id) -> None:
        """An archived batch is read-only and done fermenting/packaging — it cannot
        gain a new vessel link. Also keeps the un-archive vessel-connection check
        (BatchService.update, spec-data-model.md §5.7 "Archiving") from being fooled
        by a vessel attached after the fact.

        Uses `get_active()` (not `get()`) to detect a soft-deleted batch instead of
        hand-rolling another `deleted_at` check — a soft-deleted batch is rejected
        the same way an archived one is: both are a parent the rest of the API
        treats as gone, and a vessel should not be linkable to either. A batch_id
        that does not exist at all is left alone here; that FK still gets caught
        downstream, same as before this fix.
        """
        batch_service = BatchService(self.db_session)
        if batch_service.get(batch_id) is None:
            return
        active_batch = batch_service.get_active(batch_id)
        if active_batch is None:
            raise HTTPException(
                status_code=409, detail="Cannot assign a vessel to a deleted batch."
            )
        if active_batch.status == BatchStatus.ARCHIVED.value:
            raise HTTPException(
                status_code=409, detail="Cannot assign a vessel to an archived batch."
            )

    def _reject_deleted_tap(self, tap_id) -> None:
        """A soft-deleted tap is a parent the rest of the API treats as gone —
        same reasoning as `_reject_archived_batch` above, on the other parent a
        vessel can be linked to. A tap_id that does not exist at all is left
        alone here; that FK still gets caught downstream, same as batch_id."""
        tap_service = TapService(self.db_session)
        if tap_service.get(tap_id) is not None and tap_service.get_active(tap_id) is None:
            raise HTTPException(
                status_code=409, detail="Cannot assign a vessel to a deleted tap."
            )

    def list_active(
        self, batch_id: Optional[UUID] = None, status: Optional[str] = None
    ) -> List[StorageVessel]:
        """List vessels filtered by batch and/or status, excluding soft-deleted."""
        stmt = (
            select(StorageVessel)
            .where(StorageVessel.deleted_at.is_(None))
            .order_by(StorageVessel.vessel_number.nullslast(), StorageVessel.name)
        )
        if batch_id:
            stmt = stmt.where(StorageVessel.batch_id == batch_id)
        if status:
            stmt = stmt.where(StorageVessel.status == status)
        return list(self.db_session.scalars(stmt).all())

    def list_page(
        self,
        page: int = 1,
        page_size: int = 50,
        batch_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[StorageVessel], int]:
        """Offset-paginated vessel list returning (items, total)."""
        stmt = (
            select(StorageVessel)
            .where(StorageVessel.deleted_at.is_(None))
            .order_by(StorageVessel.vessel_number.nullslast(), StorageVessel.name)
        )
        if batch_id:
            stmt = stmt.where(StorageVessel.batch_id == batch_id)
        if status:
            stmt = stmt.where(StorageVessel.status == status)
        total: int = self.db_session.scalar(
            select(func.count()).select_from(stmt.subquery())  # pylint: disable=not-callable
        ) or 0
        offset = (page - 1) * page_size
        items = list(self.db_session.scalars(stmt.offset(offset).limit(page_size)).all())
        return items, total

    def list_page_with_summary(
        self,
        page: int = 1,
        page_size: int = 50,
        batch_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[Any], int]:
        """Vessel list page enriched with pour count and denormalised batch name.

        Composes `PourEventService` and `BatchService` internally so the router's list
        endpoint depends on this one service method for the listing use-case, rather than
        orchestrating three services itself to build a single response — that orchestration
        was the specific router-level coupling the vessels.py split was meant to remove.
        """
        vessels, total = self.list_page(
            page=page, page_size=page_size, batch_id=batch_id, status=status
        )
        vessel_ids = [v.id for v in vessels]
        pour_counts = PourEventService(self.db_session).count_by_vessel_ids(vessel_ids)
        batch_ids = list({v.batch_id for v in vessels})
        batch_name_map = BatchService(self.db_session).get_names_by_ids(batch_ids)
        list_response_cls = _s("StorageVesselListResponse")
        items = []
        for v in vessels:
            data = list_response_cls.model_validate(v)
            data.pour_count = pour_counts.get(v.id, 0)
            data.batch_name = batch_name_map.get(v.batch_id)
            items.append(data)
        return items, total

    def restore(self, vessel_id) -> bool:
        """Clear `deleted_at`. False when not found or not currently deleted.

        Children soft-deleted in their own right stay deleted: this restores the
        vessel, not everything that ever hung off it.
        """
        vessel = self.get(vessel_id)
        if vessel is None or vessel.deleted_at is None:
            return False
        vessel.deleted_at = None
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return True

    def soft_delete(self, vessel_id: UUID) -> bool:
        """Soft-delete a vessel; returns False if it does not exist."""
        vessel = self.get(vessel_id)
        if vessel is None:
            return False
        vessel.deleted_at = datetime.now(UTC)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return True

    def update(self, item_id: Any, obj: StorageVesselUpdate) -> Optional[StorageVessel]:
        """Update a vessel, including its batch and tap links.

        Replaces the former `assign_batch` / `assign_tap` endpoints: both wrote a single
        FK, so they were a field write wearing a verb. Their side effects moved here
        rather than being dropped, which also means one transaction instead of two.

        **`exclude_unset`, not `is None`.** For these two fields null is a command, not
        an absence: `batchId: null` empties the keg, `tapId: null` releases it from its
        tap. Testing `is None` would make every unrelated edit — renaming a keg, changing
        its location — silently unassign both.
        """
        vessel = self.get_active(item_id)
        if vessel is None:
            return None

        fields = obj.model_dump(exclude_unset=True)

        if fields.get("batch_id") is not None:
            self._reject_archived_batch(fields["batch_id"])

        if "tap_id" in fields and fields["tap_id"] is not None:
            self._reject_deleted_tap(fields["tap_id"])

            # A tap holds one vessel. Evicting the previous holder in this same
            # transaction is what stops two vessels claiming one tap.
            #
            # This has to happen — and be flushed — *before* the new tap_id is set:
            # `storage_vessel.tap_id` is UNIQUE, and SQLAlchemy batches both UPDATEs
            # into one executemany whose order is not ours to choose, so writing the
            # new holder first trips the constraint instead of the old one clearing.
            other = self.db_session.scalars(
                select(StorageVessel).where(
                    StorageVessel.tap_id == fields["tap_id"],
                    StorageVessel.id != vessel.id,
                )
            ).first()
            if other is not None:
                other.tap_id = None
                self.db_session.flush()

        for column, value in fields.items():
            setattr(vessel, column, value)

        if "batch_id" in fields:
            if fields["batch_id"] is None:
                # `clean` here means "empty and unassigned" — nothing observes whether the
                # keg was actually washed; that is the keg-hygiene reminder's concern. An
                # explicit status in the same request wins over this default.
                if "status" not in fields:
                    vessel.status = VesselStatus.CLEAN
                # An emptied vessel holds nothing -- stale remaining figures from its
                # last fill would otherwise persist and read as still-full stock.
                vessel.volume_remaining = 0.0
                vessel.bottles_remaining = 0
            else:
                # Filling a cellar vessel from a batch *is* packaging it. Idempotent and
                # fermenting-only, so a second keg changes nothing.
                BatchService(self.db_session).mark_packaged(fields["batch_id"], vessel.fill_date)

        self.commit()
        return vessel
