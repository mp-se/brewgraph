# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Pressure ingestion use case — PressureMon readings."""
from datetime import UTC, datetime
from typing import Optional

from oss.precision import quantise
from oss.schemas.pressure_reading import PressureReadingCreate

from ._utils import Device, PressureReading, _payload_temperature, _safe_float


class _PressureIngestionMixin:
    """Parses and persists pressure readings, auto-assigning a batch when needed."""

    def write_pressure(
        self, device: Device, payload: dict, commit: bool = True
    ) -> PressureReading:
        """Parse and write a pressure reading from raw payload dict."""
        # Best-effort liveness stamp: device is already resolved for attribution above,
        # so this rides in the same transaction as the reading write below.
        device.last_seen = datetime.now(UTC)
        device.failed_ingest_counter = 0
        temperature = _payload_temperature(payload)

        pressure = _safe_float(payload.get("pressure", 0.0), default=0.0, lo=0.0, hi=2000.0)
        # battery is volts, not a percentage — see the write_gravity clamp above
        # for why hi=10.0 (1S lithium voltage bound, not a tighter "percentage"
        # range someone might be tempted to substitute).
        battery: Optional[float] = (
            _safe_float(payload.get("battery"), default=0.0, lo=0.0, hi=10.0)
            if payload.get("battery") is not None else None
        )
        run_time: Optional[float] = (
            _safe_float(payload.get("run-time"), default=0.0, lo=0.0, hi=1e6)
            if payload.get("run-time") is not None else None
        )

        pressure_unit = payload.get("pressure_units", "kPa")
        if pressure_unit.upper() == "BAR":
            pressure = quantise(pressure * 100, "pressure")
        elif pressure_unit.upper() == "PSI":
            pressure = quantise(pressure * 6.89476, "pressure")

        reading = PressureReadingCreate(
            batch_id=device.batch_id if device.vessel_id is None else None,
            vessel_id=device.vessel_id,
            device_id=device.id,
            temperature=temperature,
            pressure=pressure,
            battery=battery,
            rssi=_safe_float(
                payload.get("rssi", 0.0), default=0.0, lo=-200.0, hi=0.0
            ),
            run_time=run_time,
            excluded=False,
            created_at=datetime.now(UTC),
        )
        return self._pressure_svc.create(reading) if commit else self._pressure_svc.build(reading)

    def ingest_pressure(self, device: Device, payload: dict) -> PressureReading:
        """Atomically persist pressure and any required batch auto-assignment."""
        self.stamp_device_last_seen(device)
        try:
            if device.vessel_id is None:
                self.find_or_create_batch(device, "pressuremon")
            reading = self.write_pressure(device, payload, commit=False)
            self._commit_or_raise()
            return reading
        except Exception:
            self._db.rollback()
            raise
