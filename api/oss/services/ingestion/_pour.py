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
import math
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.enums import TempType
from oss.schemas.temp_reading import TempReadingIngest

from ._utils import NoActiveVesselError, PourEvent, StorageVessel, Tap, _required_float


def kegmon_temperature(payload: dict) -> tuple[Optional[float], Optional[str]]:
    """The optional KegMon temperature in Celsius as ``(value, drop_cause)``.

    Absent gives ``(None, None)``. A number or numeric string that is finite is the value;
    anything else is dropped with a short cause, never the value itself.
    """
    raw = payload.get("temperature")
    if raw is None:
        return None, None
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None, "not a number"
    try:
        value = float(raw)
    except ValueError:
        return None, "not a number"
    if not math.isfinite(value):
        return None, "not a finite number"
    return value, None


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

    def _stage_temperature(self, vessel: StorageVessel, payload: dict) -> None:
        """Stage the payload's temperature as a reading on the vessel, in the pour's commit."""
        temperature, _ = kegmon_temperature(payload)
        if temperature is None:
            return
        self._temp_svc.build(TempReadingIngest(
            vessel_id=vessel.id,
            temperature=temperature,
            temp_type=TempType.BEER,
            is_aggregate=False,
            created_at=datetime.now(UTC),
        ))

    def _active_vessel_with_batch(self, tap: Tap) -> StorageVessel:
        """The tap's active vessel; a vessel with no batch is ignored like no vessel."""
        vessel = self.find_active_vessel_for_tap(tap)
        if vessel is None or vessel.batch_id is None:
            raise NoActiveVesselError(f"No active vessel with a batch on tap id={tap.id}")
        return vessel

    def write_pour(self, tap: Tap, payload: dict) -> Optional[PourEvent]:
        """Apply an authoritative KegMon volume update and optionally record its pour."""
        event_id = payload.get("eventId") or payload.get("event_id")
        if event_id:
            existing = self._db.scalars(
                select(PourEvent).where(PourEvent.tap_id == tap.id, PourEvent.event_id == event_id)
            ).first()
            if existing is not None:
                return existing
        vessel = self._active_vessel_with_batch(tap)
        previous = vessel.volume_remaining
        volume, max_volume = self._vessel_levels(payload)
        pour_reported = payload.get("pour") is not None
        pour_amount = _required_float(payload, "pour") if pour_reported else None
        self._stage_temperature(vessel, payload)
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
