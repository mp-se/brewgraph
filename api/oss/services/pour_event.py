# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""PourEvent service."""
from datetime import UTC, datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from core.models.registry import resolve_model
from oss.schemas.pour_event import PourEventBulkCreate, PourEventCreate
from oss.services._batched import latest_by_owner
from oss.services._cursor import Cursor, apply_cursor_filter, cursor_order_by
from oss.services.base import BaseService

PourEvent = resolve_model("PourEvent")
StorageVessel = resolve_model("StorageVessel")
Tap = resolve_model("Tap")


class PourEventService(BaseService[PourEvent, PourEventCreate, PourEventCreate]):
    """Service for recording and listing pour events against keg vessels."""

    def __init__(self, db_session: Session):
        """Initialise with a SQLAlchemy session."""
        super().__init__(PourEvent, db_session)

    def latest_global(self, limit: int = 5) -> List[PourEvent]:
        """Return the most recent pour events across all vessels."""
        return list(
            self.db_session.scalars(
                select(PourEvent)
                .order_by(PourEvent.created_at.desc())
                .limit(limit)
            ).all()
        )

    def bulk_insert(self, vessel_id: UUID, rows: List[PourEventBulkCreate]) -> List[PourEvent]:
        """Insert pour history directly without touching vessel volume (for restore)."""
        now = datetime.now(UTC)
        vessel = self.db_session.get(StorageVessel, vessel_id)
        batch_id = vessel.batch_id if vessel is not None else None
        events = [
            PourEvent(
                vessel_id=vessel_id,
                batch_id=batch_id,
                pour_amount=r.pour_amount,
                volume_remaining=r.volume_remaining,
                is_manual=r.is_manual,
                created_at=r.created_at or now,
            )
            for r in rows
        ]
        self.db_session.add_all(events)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return events

    def count_by_vessel_ids(self, vessel_ids: List[UUID]) -> Dict[UUID, int]:
        """Return a map of vessel_id → pour event count for the given vessel IDs."""
        if not vessel_ids:
            return {}
        rows = self.db_session.execute(
            select(PourEvent.vessel_id, func.count(PourEvent.id).label("cnt"))  # pylint: disable=not-callable
            .where(PourEvent.vessel_id.in_(vessel_ids))
            .group_by(PourEvent.vessel_id)
        ).all()
        return {row.vessel_id: row.cnt for row in rows}

    def count_by_batch_ids(self, batch_ids: List[UUID]) -> Dict[UUID, int]:
        """Return a map of batch_id → pour event count for the given batch IDs.

        Counts on the pour's own `batch_id` rather than joining through the vessel's
        current one, so a keg that has since been emptied and refilled still reports
        each batch's own pours.
        """
        if not batch_ids:
            return {}
        rows = self.db_session.execute(
            select(PourEvent.batch_id, func.count(PourEvent.id).label("cnt"))  # pylint: disable=not-callable
            .where(PourEvent.batch_id.in_(batch_ids))
            .group_by(PourEvent.batch_id)
        ).all()
        return {row.batch_id: row.cnt for row in rows}

    def latest_by_vessel_ids(self, vessel_ids):
        """Return `{vessel_id: most recent pour}` in one query."""
        return latest_by_owner(self.db_session, self.model, self.model.vessel_id, vessel_ids)

    def list_for_vessel(self, vessel_id: UUID) -> List[PourEvent]:
        """Return all pour events for a vessel, newest first."""
        return list(
            self.db_session.scalars(
                select(PourEvent)
                .where(PourEvent.vessel_id == vessel_id)
                .order_by(PourEvent.created_at.desc())
            ).all()
        )

    def list_for_vessel_cursor(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        vessel_id: UUID,
        limit: int = 200,
        cursor: Optional[Cursor] = None,
        current_fill_only: bool = False,
    ) -> Tuple[List[PourEvent], bool]:
        """Cursor-paginated pour events for a vessel, **oldest first**.

        cursor is the (created_at, id) of the last item from the previous page.

        Ascending is normative: cursor pagination on this API is always ascending
        (created_at ASC) — oldest first — matching how graph and list views consume
        the data. Views wanting newest-first sort for display; the wire order is
        fixed.
        """
        stmt = select(PourEvent).where(PourEvent.vessel_id == vessel_id)
        if current_fill_only:
            vessel = self.db_session.get(StorageVessel, vessel_id)
            # An empty keg has no current fill, so its pours are all from past ones —
            # filtering on a null batch_id would hide the pours that emptied it.
            if vessel is not None and vessel.batch_id is not None:
                stmt = stmt.where(PourEvent.batch_id == vessel.batch_id)
        stmt = apply_cursor_filter(stmt, PourEvent, cursor)
        stmt = stmt.order_by(*cursor_order_by(PourEvent))
        rows = list(self.db_session.scalars(stmt.limit(limit + 1)).all())
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def _advance_tap_counter(self, tap_id: UUID, amount: float) -> None:
        """Adjust a tap's lifetime throughput counter by `amount` (may be negative).

        Not derived from PourEvent rows -- see Tap.total_volume_poured -- so this
        is the only writer. Called from record_pour/record_bottle_pour (always
        positive, at pour time) and toggle_excluded (either sign, on exclusion
        state change).
        """
        self.db_session.execute(
            update(Tap).where(Tap.id == tap_id).values(
                total_volume_poured=Tap.total_volume_poured + amount
            )
        )

    def record_pour(
        self, vessel_id: UUID, amount: float, created_at: Optional[datetime] = None,
    ) -> PourEvent:
        """Atomically decrement vessel volume and write a PourEvent row (keg)."""
        vessel = self.db_session.get(StorageVessel, vessel_id)
        if vessel is None or vessel.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Vessel not found")
        if vessel.vessel_type != "keg":
            raise HTTPException(
                status_code=400, detail="Use the /pours/bottles endpoint for bottle vessels"
            )

        # Captured before the drain-to-empty branch below can clear it: the pour
        # went through this tap even if the keg is unassigned from it below.
        tap_id = vessel.tap_id

        # Atomic decrement — avoids race conditions under concurrent pours
        self.db_session.execute(
            update(StorageVessel)
            .where(StorageVessel.id == vessel_id)
            .values(
                volume_remaining=case(
                    (StorageVessel.volume_remaining <= amount, 0.0),
                    else_=StorageVessel.volume_remaining - amount,
                )
            )
        )
        self.db_session.refresh(vessel)

        if vessel.volume_remaining <= 0:
            vessel.tap_id = None

        event = PourEvent(
            vessel_id=vessel_id,
            batch_id=vessel.batch_id,
            tap_id=tap_id,
            pour_amount=amount,
            volume_remaining=max(vessel.volume_remaining, 0.0),
            is_manual=False,
            **({"created_at": created_at} if created_at is not None else {}),
        )
        self.db_session.add(event)
        if tap_id is not None:
            self._advance_tap_counter(tap_id, amount)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return event

    def record_bottle_pour(
        self, vessel_id: UUID, bottle_count: int, created_at: Optional[datetime] = None,
    ) -> PourEvent:
        """Decrement bottles_remaining and write a PourEvent row (bottle vessel)."""
        vessel = self.db_session.get(StorageVessel, vessel_id)
        if vessel is None or vessel.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Vessel not found")
        if vessel.vessel_type != "bottles":
            raise HTTPException(status_code=400, detail="Use the /pours endpoint for keg vessels")
        if vessel.bottle_volume is None:
            raise HTTPException(status_code=400, detail="Vessel has no bottle_volume_l set")
        if vessel.bottles_remaining is None:
            raise HTTPException(status_code=400, detail="Vessel has no bottles_remaining set")

        # Stamped for tap-scoped attribution, same as record_pour -- see its comment.
        # Bottle vessels are not normally assigned to a tap, so this is usually None.
        tap_id = vessel.tap_id

        new_remaining = max(vessel.bottles_remaining - bottle_count, 0)
        # Not rounded here -- pour_amount/volume_remaining are quantised once, at
        # the API boundary, by PourEventResponse (see oss/schemas/pour_event.py
        # and oss/precision.py). Rounding an intermediate result here as well
        # would just be a second, redundant place for the figure to live.
        pour_amount = bottle_count * vessel.bottle_volume
        new_volume = new_remaining * vessel.bottle_volume

        self.db_session.execute(
            update(StorageVessel)
            .where(StorageVessel.id == vessel_id)
            .values(bottles_remaining=new_remaining, volume_remaining=new_volume)
        )
        self.db_session.refresh(vessel)

        event = PourEvent(
            vessel_id=vessel_id,
            batch_id=vessel.batch_id,
            tap_id=tap_id,
            pour_amount=pour_amount,
            volume_remaining=new_volume,
            is_manual=True,
            **({"created_at": created_at} if created_at is not None else {}),
        )
        self.db_session.add(event)
        if tap_id is not None:
            self._advance_tap_counter(tap_id, pour_amount)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return event

    def toggle_excluded(self, vessel_id: UUID, pour_id: UUID) -> "PourEvent":
        """Toggle the excluded flag on a pour event.

        Excluding a pour retroactively removes its volume from the tap's lifetime
        throughput counter (an excluded pour is judged not to have really
        happened, so it shouldn't count toward when the line last needs
        cleaning); un-excluding restores it. See Tap.total_volume_poured.
        """
        pour = self.db_session.scalars(
            select(PourEvent).where(PourEvent.id == pour_id, PourEvent.vessel_id == vessel_id)
        ).first()
        if pour is None:
            raise HTTPException(status_code=404, detail="Pour not found")
        pour.excluded = not pour.excluded
        if pour.tap_id is not None:
            self._advance_tap_counter(
                pour.tap_id, -pour.pour_amount if pour.excluded else pour.pour_amount
            )
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        self.db_session.refresh(pour)
        return pour
