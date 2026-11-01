# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Gravity ingestion use case — GravityMon and iSpindel readings."""
import logging
import uuid
from datetime import UTC, datetime
from typing import Optional

from core.log import LogLevel, system_log
from oss.precision import quantise
from oss.schemas.gravity_reading import GravityReadingIngest

from ._utils import (
    Batch,
    Device,
    GravityReading,
    UnstorableValueError,
    _finite,
    _optional_float,
    _payload_temperature,
    _required_float,
)


logger = logging.getLogger(__name__)


def _payload_gravity(payload: dict, gravity_units: str, device: Device) -> Optional[float]:
    """The payload's gravity as SG. Only an iSpindel or GravityMon device may omit it (the
    reading then keeps a null gravity); for every other source it cannot be stored."""
    if payload.get("gravity") is None and device.device_type in ("ispindel", "gravitymon"):
        return None
    gravity = _required_float(payload, "gravity")
    if gravity_units.upper() == "P":
        try:
            gravity = quantise(1 + (gravity / (258.6 - ((gravity / 258.2) * 227.1))), "gravity")
        except ZeroDivisionError as exc:
            raise UnstorableValueError("gravity", "no specific gravity for this Plato") from exc
    return _finite(gravity, "gravity")


class _GravityIngestionMixin:
    """Parses and persists gravity readings, and triggers gravity-driven side effects."""

    def write_gravity(
        self, batch: Batch, device: Device, payload: dict, commit: bool = True
    ) -> GravityReading:
        """Parse and write a gravity reading from raw payload dict."""
        # Best-effort liveness stamp: device is already resolved for attribution above,
        # so this rides in the same transaction as the reading write below.
        device.last_seen = datetime.now(UTC)
        device.failed_ingest_counter = 0
        gravity_units = "SG"

        if payload.get("gravity-unit") is not None:
            gravity_units = payload["gravity-unit"]
        elif "name" in payload and not str(payload["name"]).startswith("[SG]"):
            gravity_units = "P"

        temperature = _payload_temperature(payload)

        gravity = _payload_gravity(payload, gravity_units, device)

        excluded = False
        if gravity is not None:
            if batch.og is not None and gravity > batch.og * 1.10:
                excluded = True
            elif batch.fg is not None and gravity < batch.fg * 0.90:
                excluded = True

        # Every measurement is stored as received; an optional one that was not sent is
        # null. Battery is volts, rssi is dBm: neither is range-checked.
        reading = GravityReadingIngest(
            batch_id=batch.id,
            device_id=device.id,
            temperature=temperature,
            gravity=gravity,
            velocity=_optional_float(payload, "velocity"),
            angle=_optional_float(payload, "angle"),
            battery=_optional_float(payload, "battery"),
            battery_percent=_optional_float(payload, "battery_percent"),
            rssi=_optional_float(payload, "RSSI", "rssi"),
            run_time=_optional_float(payload, "run-time"),
            excluded=excluded,
            created_at=datetime.now(UTC),
        )
        return self._gravity_svc.create(reading) if commit else self._gravity_svc.build(reading)

    def ingest_gravity(
        self, device: Device, device_type: str, payload: dict
    ) -> tuple[Batch, GravityReading]:
        """Atomically create/attach context and persist one gravity reading."""
        try:
            batch = self.find_or_create_batch(device, device_type)
            reading = self.write_gravity(
                batch, device, payload, commit=False
            )
            self._commit_or_raise()
            return batch, reading
        except Exception:
            self._db.rollback()
            raise

    def trigger_dry_hops(self, batch_id: uuid.UUID, gravity: float) -> None:
        """Evaluate and trigger pending dry hops for a batch after a gravity reading.

        Owned by the service so the router does not need its session handle. Advisory:
        Dry-hop triggering must never fail the measurement ingest, so callers schedule
        it as a background task.  A failure is nevertheless recorded: the next gravity
        reading will retry this idempotent evaluation, and the brewer can diagnose an
        outage in System Logs instead of silently missing a scheduled addition.
        """
        from oss.services.batch_dry_hop import BatchDryHopService  # pylint: disable=import-outside-toplevel

        try:
            BatchDryHopService(self._db).check_and_trigger(
                batch_id, gravity=gravity, hours_left=None
            )
            self._commit_or_log("Dry hop commit failed: %s")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._db.rollback()
            logger.error("Dry-hop trigger failed for batch %s: %s", batch_id, exc)
            system_log(
                "dry_hop_trigger_failed",
                f"Dry-hop trigger failed for batch {batch_id}: {exc}",
                level=LogLevel.ERROR,
            )
