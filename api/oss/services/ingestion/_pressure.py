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

from ._utils import (
    Device,
    PressureReading,
    _finite,
    _optional_float,
    _payload_temperature,
    _required_float,
)


class _IngestedPressureReading(PressureReadingCreate):
    """A reading as ingested: carries the stored-only second sensor, which no API schema
    exposes, and may omit the pressure (a sensor fault), which is then stored as null."""

    pressure: Optional[float] = None
    pressure2: Optional[float] = None


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

        # The pressure is stored as received, in kPa after the unit conversion: there is no
        # range, and a negative pressure (a vacuum) is a valid reading.
        # Only a PressureMon device may omit it (the reading then keeps a null pressure);
        # for every other source a missing pressure cannot be stored.
        pressure_unit = payload.get("pressure_units") or "kPa"
        if payload.get("pressure") is None and device.device_type == "pressuremon":
            pressure = None
        else:
            pressure = _required_float(payload, "pressure")
            if pressure_unit.upper() == "BAR":
                pressure = quantise(pressure * 100, "pressure")
            elif pressure_unit.upper() == "PSI":
                pressure = quantise(pressure * 6.89476, "pressure")
            _finite(pressure, "pressure")

        pressure2 = _optional_float(payload, "pressure2")
        if pressure2 is not None:
            if pressure_unit.upper() == "BAR":
                pressure2 = quantise(pressure2 * 100, "pressure")
            elif pressure_unit.upper() == "PSI":
                pressure2 = quantise(pressure2 * 6.89476, "pressure")
            _finite(pressure2, "pressure2")

        reading = _IngestedPressureReading(
            pressure2=pressure2,
            batch_id=device.batch_id if device.vessel_id is None else None,
            vessel_id=device.vessel_id,
            device_id=device.id,
            temperature=temperature,
            pressure=pressure,
            battery=_optional_float(payload, "battery"),
            battery_percent=_optional_float(payload, "battery_percent"),
            rssi=_optional_float(payload, "rssi"),
            run_time=_optional_float(payload, "run-time"),
            excluded=False,
            created_at=datetime.now(UTC),
        )
        return self._pressure_svc.create(reading) if commit else self._pressure_svc.build(reading)

    def ingest_pressure(self, device: Device, payload: dict) -> PressureReading:
        """Atomically persist pressure and any required batch auto-assignment."""
        try:
            if device.vessel_id is None:
                self.find_or_create_batch(device, "pressuremon")
            reading = self.write_pressure(device, payload, commit=False)
            self._commit_or_raise()
            return reading
        except Exception:
            self._db.rollback()
            raise
