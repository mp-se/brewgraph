# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Chamber ingestion use case — chamber-controller temp readings and setpoint
resolution against a batch's FermentationStep schedule."""
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from core.enums import DeviceType, TempType
from core.models.registry import resolve_model

from ._utils import Device


class _ChamberIngestionMixin:
    """Writes chamber temp readings and resolves the chamber's target setpoint."""

    def _resolve_temp_context(self, device: Device) -> tuple[bool, Optional[uuid.UUID]]:
        """Return ``(should_write, batch_id)`` for a temp reading from this device.

        A vessel-linked probe records **even when the vessel has no batch** — a keg in a
        storage fridge with no active fermentation is the primary use case, so `batch_id`
        is context when it exists rather than a precondition.

        Only two things suppress the write: nothing to attach the reading to at all, or a
        resolved batch that is refusing ingest (``accept_ingest`` False, or soft-deleted).
        """
        batch_id = device.batch_id
        if batch_id is None:
            vessel = self._vessel_svc.get(device.vessel_id) if device.vessel_id else None
            if vessel is None:
                return False, None
            batch_id = vessel.batch_id
            if batch_id is None:
                return True, None
        batch = self._batch_svc.get(batch_id)
        if not batch or not batch.accept_ingest or batch.deleted_at is not None:
            return False, None
        return True, batch_id

    def write_temp(  # pylint: disable=too-many-arguments
        self,
        token: Optional[str],
        temperature: Optional[float] = None,
        *,
        fridge_temp: Optional[float] = None,
        rssi: Optional[float] = None,
        temp_type: str = TempType.BEER.value,
        device_id: Optional[str] = None,
        battery: Optional[float] = None,
    ) -> Optional[Device]:
        """Write TempReading row(s) resolved via device token or chamber chip ID.

        **One row per value present**, not one row total: a chamber controller reporting
        both ``beer-temp`` and ``fridge-temp`` produces two readings, tagged `beer` and
        `chamber`. ``temp_type`` labels ``temperature`` and defaults to `beer` — a plain
        ambient probe overrides it. ``fridge_temp`` is always `chamber`, since only a
        chamber controller has one.

        Identity resolves through ``resolve_device``, so a ``chamber_controller`` may be
        matched by its configured chip ID when no valid token is supplied — the same
        trusted-LAN path GravityMon and PressureMon already use, and not authentication.
        Callers that pass no ``device_id`` are unchanged: token or 401, as before.

        Drops silently (but still returns the resolved device) if the resolved batch has
        accept_ingest=False or is deleted. Raises HTTP 401 if neither identifier resolves.
        Returns the resolved device so callers (e.g. chamber setpoint resolution)
        can use it without a second lookup.
        """
        from fastapi import HTTPException  # pylint: disable=import-outside-toplevel

        device = self.resolve_device(token, device_id, DeviceType.CHAMBER_CONTROLLER.value)
        if device is None:
            raise HTTPException(status_code=401, detail="Token not registered")
        # Best-effort liveness stamp: covers both the dropped-write and normal paths below.
        device.last_seen = datetime.now(UTC)
        should_write, batch_id = self._resolve_temp_context(device)
        if not should_write:
            self._commit_or_log("Failed to stamp device liveness: %s", level=logging.ERROR)
            return device

        # Reading is actually going to persist below — this is the "next success"
        # that clears any prior drop streak, unlike the last_seen stamp above which
        # rides even the dropped (should_write=False) path.
        device.failed_ingest_counter = 0
        self._create_temp_rows(
            device, batch_id, ((temperature, temp_type), (fridge_temp, TempType.CHAMBER.value)),
            (rssi, battery),
        )
        self._commit_or_raise()
        return device

    def _create_temp_rows(self, device, batch_id, values, telemetry) -> None:
        """Create one TempReading per non-None (value, temp_type) pair, sharing a timestamp.

        Both rows from one chamber poll must carry the same ``created_at`` — they are two
        facets of a single observation, and a split timestamp would let aggregation bucket
        them apart. ``battery`` and ``rssi`` are likewise stamped on every row produced by
        this call: both readings come from one physical device on one poll, so there is
        only ever one battery/signal value to report, not one per temp_type.
        """
        from oss.schemas.temp_reading import TempReadingCreate  # pylint: disable=import-outside-toplevel
        rssi, battery = telemetry
        now = datetime.now(UTC)
        for value, kind in values:
            if value is None:
                continue
            self._temp_svc.create(TempReadingCreate(
                vessel_id=device.vessel_id,
                batch_id=batch_id,
                device_id=device.id,
                temperature=value,
                battery=battery,
                rssi=rssi,
                temp_type=kind,
                is_aggregate=False,
                created_at=now,
            ))

    def _step_has_ended(self, step, today: date, end: date) -> bool:
        """Return True if a non-triggered step's date/days window has elapsed.

        Manual-trigger steps never auto-end via the days timeout -- only via
        triggered_at, which callers check before invoking this helper.
        """
        is_manual = step.trigger_type == "manual"
        return not is_manual and today >= end

    def _find_active_step(self, steps, today: date):
        """Return (matched_step_or_None, last_computed_end_date_or_None) for a batch's steps.

        Walks steps in order, tracking the latest computed end date across all
        of them and returning the first step whose window is currently open.
        A step that already fired (triggered_at set) advances the cursor early
        so the next step becomes current even before its own window starts.
        """
        matched = None
        last_end = None
        advanced_early = False
        for step in steps:
            if step.date is None:
                continue
            start = step.date
            end = start + timedelta(days=step.days)
            if last_end is None or end > last_end:
                last_end = end
            if step.triggered_at is not None:
                advanced_early = True
                continue
            if self._step_has_ended(step, today, end):
                continue
            effective_start = today if advanced_early else start
            if effective_start <= today:
                matched = step
                break
        return matched, last_end

    def _resolve_today(
        self,
        local_timestamp: Optional[str] = None,
        tz_name: Optional[str] = None,
    ) -> date:
        """Return "today" for chamber-mode day-based step-window resolution.

        When the polling device supplies both `local_timestamp` (a naive ISO
        8601 wall-clock reading, e.g. "2026-08-26T14:32:00") and a valid IANA
        `tz_name` (e.g. "America/Chicago"), the device's own local calendar
        date is trusted directly -- no further tz conversion is needed since
        local_timestamp is already the device's local wall-clock time; the
        ZoneInfo lookup exists to validate the identifier. Any parse failure
        (bad timestamp, unknown/garbage timezone) falls back to the server's
        local calendar date rather than raising -- a chamber controller with
        a wrong clock can't retry or fix itself mid-poll.

        Subclasses that need a different notion of "today" (for example one
        derived from stored timezone settings) should override this method
        rather than reimplementing resolve_chamber_mode() -- the returned
        date is used verbatim as the day-based cursor for matching
        FermentationStep windows.
        """
        if local_timestamp and tz_name:
            try:
                ZoneInfo(tz_name)
                return datetime.fromisoformat(local_timestamp).date()
            except (ValueError, ZoneInfoNotFoundError):
                pass
        return date.today()

    def resolve_chamber_mode(
        self,
        device: Optional[Device],
        local_timestamp: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> dict:
        """Resolve the chamber controller's target setpoint for the polling device.

        `local_timestamp`/`timezone` are the device's optional self-reported
        wall-clock reading and IANA identifier (see `_resolve_today`) -- when
        both are present and valid they drive the day-boundary used to match
        FermentationStep windows instead of the server's own date. Absent or
        invalid values fall back to today's server date unchanged.

        The response is never empty: either a concrete target_temperature+mode pair,
        or mode R with no target temperature.
        """
        rest = {"target_temperature": None, "temp_units": "C", "mode": "R"}

        # Step 1: device not linked to any batch at all -> R (degenerate case of step 2).
        if device is None or device.batch_id is None:
            return rest

        batch = self._batch_svc.get(device.batch_id)
        # Steps 2-3: batch not accepting ingest (unlinked, deleted, accept_ingest=false),
        # or not activated for temperature control -> R.
        if (
            not batch
            or not batch.accept_ingest
            or batch.deleted_at is not None
            or not batch.chamber_control_active
        ):
            return rest

        # Step 4: find the FermentationStep for this batch/device whose computed
        # date range (date to date+days) contains today.
        FermentationStep = resolve_model("FermentationStep")  # pylint: disable=invalid-name
        steps = self._db.execute(
            select(FermentationStep).where(
                FermentationStep.batch_id == batch.id,
                FermentationStep.device_id == device.id,
            ).order_by(FermentationStep.order.asc())
        ).scalars().all()

        today = self._resolve_today(local_timestamp, timezone)
        matched, last_end = self._find_active_step(steps, today)

        if matched is not None:
            # Unknown/empty control (common on Brewfather-imported steps) -> bare R:
            # spec says R never carries a target temperature.
            if matched.control == "beer":
                return {"target_temperature": matched.temp, "temp_units": "C", "mode": "B"}
            if matched.control == "fridge":
                return {"target_temperature": matched.temp, "temp_units": "C", "mode": "F"}
        # Step 5: no matching step. Past the last step's end -> auto-deactivate.
        elif last_end is not None and today >= last_end:
            batch.chamber_control_active = False
            self._commit_or_log(
                "Failed to auto-deactivate chamber control for batch %s: %s", batch.id
            )
        return rest
