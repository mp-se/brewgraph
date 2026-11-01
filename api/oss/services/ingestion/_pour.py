# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Pour ingestion use case — KegMon tap/vessel volume and pour events."""
import logging
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ._utils import PourEvent, StorageVessel, Tap, _required_float


class _PourIngestionMixin:
    """Resolves taps/vessels and persists KegMon pour events."""

    def resolve_tap(self, token: Optional[str]) -> Optional[Tap]:
        """Resolve a tap by its ingest token. Returns None if not found."""
        if not token:
            return None
        return self._tap_svc.find_by_token(token)

    def find_active_vessel_for_tap(self, tap: Tap) -> Optional[StorageVessel]:
        """Return the currently tapped vessel for a tap, or None."""
        return self._tap_svc.find_active_vessel(tap.id)

    @staticmethod
    def _vessel_levels(payload: dict) -> tuple[float, float]:
        """The reported ``(volume, maxVolume)``, each stored exactly as received."""
        return _required_float(payload, "volume"), _required_float(payload, "maxVolume")

    def write_pour(self, tap: Tap, payload: dict) -> Optional[PourEvent]:
        """Apply an authoritative KegMon volume update and optionally record its pour."""
        event_id = payload.get("eventId") or payload.get("event_id")
        if event_id:
            existing = self._db.scalars(
                select(PourEvent).where(PourEvent.tap_id == tap.id, PourEvent.event_id == event_id)
            ).first()
            if existing is not None:
                return existing
        vessel = self.find_active_vessel_for_tap(tap)
        if vessel is None:
            raise ValueError(f"No active vessel on tap id={tap.id}")
        previous = vessel.volume_remaining
        volume, max_volume = self._vessel_levels(payload)
        pour_reported = payload.get("pour") is not None
        pour_amount = _required_float(payload, "pour") if pour_reported else None
        # The volume is the authoritative current level, stored as received. A volume above
        # the reported capacity raises the capacity to it, so volume_remaining <= total_volume
        # still holds.
        vessel.total_volume = max(max_volume, volume)
        vessel.volume_remaining = volume
        # A pour with an event id is recorded whatever the level did; without one, only a
        # level that moved down proves it is not a retry.
        if not pour_reported or not (event_id or volume < previous):
            self._db.commit()
            return None
        event = PourEvent(
            vessel_id=vessel.id,
            batch_id=vessel.batch_id,
            tap_id=tap.id,
            event_id=event_id,
            pour_amount=pour_amount,
            volume_remaining=volume,
            is_manual=False,
        )
        self._db.add(event)
        try:
            self._db.commit()
        except IntegrityError:
            # A concurrent retry can win between the lookup above and this insert.
            # Roll back our vessel mutation, then return that request's receipt.
            self._db.rollback()
            existing = self._db.scalars(
                select(PourEvent).where(
                    PourEvent.tap_id == tap.id,
                    PourEvent.event_id == event_id,
                )
            ).first()
            if existing is not None:
                return existing
            raise
        return event

    def stamp_tap_last_seen(self, tap: Tap) -> None:
        """Best-effort durable tap liveness, independent of pour attribution."""
        tap.last_seen = datetime.now(UTC)
        self._commit_or_log("Failed to stamp tap liveness: %s", level=logging.ERROR)
