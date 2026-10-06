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
from oss.schemas.gravity_reading import GravityReadingCreate

from ._utils import Batch, Device, GravityReading, _payload_temperature, _safe_float


logger = logging.getLogger(__name__)


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
        run_time: Optional[float] = None
        velocity: Optional[float] = None
        gravity_units = "SG"

        if payload.get("gravity-unit") is not None:
            gravity_units = payload["gravity-unit"]
        elif "name" in payload and not str(payload["name"]).startswith("[SG]"):
            gravity_units = "P"
        if payload.get("run-time") is not None:
            run_time = _safe_float(payload["run-time"], default=0.0, lo=0.0, hi=1e6)
        if payload.get("velocity") is not None:
            velocity = _safe_float(payload["velocity"], default=0.0, lo=-100.0, hi=100.0)

        temperature = _payload_temperature(payload)

        if gravity_units.upper() == "P":
            plato = _safe_float(payload.get("gravity", 0.0), default=0.0, lo=0.0, hi=40.0)
            gravity = quantise(1 + (plato / (258.6 - ((plato / 258.2) * 227.1))), "gravity")
        else:
            gravity = _safe_float(payload.get("gravity", 0.0), default=0.0, lo=0.8, hi=2.0)

        excluded = False
        if batch.og is not None and gravity > batch.og * 1.10:
            excluded = True
        elif batch.fg is not None and gravity < batch.fg * 0.90:
            excluded = True

        reading = GravityReadingCreate(
            batch_id=batch.id,
            device_id=device.id,
            temperature=temperature,
            gravity=gravity,
            velocity=velocity,
            angle=_safe_float(payload.get("angle", 0.0), default=0.0, lo=0.0, hi=180.0),
            # battery is volts, not a percentage — hi=10.0 is a 1S lithium voltage
            # bound (~3.0-4.2 V nominal), with headroom for a fresh cell and a
            # possible future 2S device. Do not tighten this to a percentage range.
            battery=_safe_float(payload.get("battery", 0.0), default=0.0, lo=0.0, hi=10.0),
            rssi=_safe_float(
                payload.get("RSSI", payload.get("rssi", 0.0)), default=0.0, lo=-200.0, hi=0.0
            ),
            run_time=run_time,
            excluded=excluded,
            created_at=datetime.now(UTC),
        )
        return self._gravity_svc.create(reading) if commit else self._gravity_svc.build(reading)

    def ingest_gravity(
        self, device: Device, device_type: str, payload: dict
    ) -> tuple[Batch, GravityReading]:
        """Atomically create/attach context and persist one gravity reading."""
        self.stamp_device_last_seen(device)
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
