# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Reliable Redis-backed queue: forward accepted pressure readings to every
enabled measurement=pressure Integration target configured for the account.

Sibling of oss/jobs/gravity_forward.py — same reliable-queue mechanics
(pop-to-processing, ack, retry, dead-letter, reclaim sweep), a separate queue
so a stuck/misbehaving pressure forward can never block gravity/pour/temp
forwarding or vice versa. `custom_forward` renders the user's template;
`brewfather_forward` sends Brewfather's custom stream
payload (pressure and the reading's own temperature, stored values only), at
most once per device per 15 minutes. `ispindel_forward` is gravity-only.

At ingest time the ingest path calls `enqueue_forward(device_id, tenant_id)`.
`task_drain_pressure_forward_queue` drains that queue every 30 seconds,
forwarding each device's *latest* pressure reading to every enabled
measurement=pressure `Integration` row for that account.
"""
import json
import logging
import time
from datetime import UTC, datetime

from sqlalchemy import desc, select

from core.cache import delete_key, set_key_if_absent
from core.enums import IntegrationType, MeasurementType
from core.log import LogLevel, system_log_scheduler
from core.models.registry import resolve_model
from core.queue import (queue_acquire_lock, queue_len, queue_lrem,
                        queue_pop_to_processing, queue_push,
                        queue_reclaim_stale, queue_release_lock,
                        queue_renew_lock, queue_zrangebyscore, queue_zrem)
from core.db import create_session
from oss.jobs._forward_common import (DeliveryOutcome, apply_delivery_outcome,
                                      as_uuid, deliver_built_in,
                                      deliver_custom, without_missing,
                                      recover_forwarding_error,
                                      reclaim_stale_items, retry_or_dead_letter)

logger = logging.getLogger(__name__)

_QUEUE = "pressure_forward_queue"
_DEAD = "pressure_forward_dead"
_DRAIN_LOCK = "pressure_forward_drain_lock"
_DRAIN_LOCK_TTL = 120
_MAX_PER_RUN = 200
_MAX_RETRIES = 3
_MAX_AGE_SECONDS = 86_400  # drop items older than 24 h
_PENDING_PREFIX = "pressure_forward_pending:"
_PENDING_TTL = 90  # 3x the 30s drain cadence -- coalescing window for a reading burst
_PROCESSING = "pressure_forward_processing"
_PROCESSING_TS = "pressure_forward_processing_ts"
_PROCESSING_VISIBILITY_TIMEOUT = 180


def enqueue_forward(device_id, tenant_id) -> None:
    """Push a forwarding job onto the Redis queue. Called from the ingest path.

    The worker fetches the latest reading for the device at drain time — no
    reading_id required. A per-device pending marker coalesces a burst of
    ingests into a single queued job instead of one per reading.
    """
    pending_key = f"{_PENDING_PREFIX}{device_id}"
    if not set_key_if_absent(pending_key, "1", ttl=_PENDING_TTL):
        return

    item = json.dumps({
        "device_id": str(device_id),
        "tenant_id": str(tenant_id),
        "enqueued_at": datetime.now(UTC).isoformat(),
        "attempts": 0,
    })
    if not queue_push(_QUEUE, item):
        delete_key(pending_key)
        logger.warning(
            "pressure_forward: enqueue_forward failed to queue job for device %s "
            "(Redis unavailable?)", device_id,
        )


async def task_drain_pressure_forward_queue() -> None:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Drain up to _MAX_PER_RUN items from the pressure forward queue.

    Guarded by a distributed lock so a misconfigured multi-instance deployment
    cannot interleave drains. The lock's TTL is renewed after every item
    popped, so a live drain never lets a peer steal the lock mid-run.
    """
    depth = queue_len(_QUEUE)
    if depth == 0:
        return

    lock_token = queue_acquire_lock(_DRAIN_LOCK, ttl=_DRAIN_LOCK_TTL)
    if lock_token is None:
        logger.info("task_drain_pressure_forward_queue: another worker holds the drain lock")
        return

    logger.info("task_drain_pressure_forward_queue: %d items in queue", depth)
    forwarded = failed = skipped = 0

    pressure_model = resolve_model("PressureReading")
    device_model = resolve_model("Device")
    integration_model = resolve_model("Integration")

    db = create_session()
    try:
        for _ in range(min(depth, _MAX_PER_RUN)):
            raw = queue_pop_to_processing(_QUEUE, _PROCESSING, _PROCESSING_TS)
            if raw is None:
                break

            if not queue_renew_lock(_DRAIN_LOCK, lock_token, ttl=_DRAIN_LOCK_TTL):
                logger.warning(
                    "task_drain_pressure_forward_queue: lost drain lock ownership mid-run, "
                    "stopping before processing further items"
                )
                break

            try:
                item = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                logger.warning("pressure_forward: malformed queue item dropped")
                _ack(raw)
                skipped += 1
                continue

            enqueued_at = datetime.fromisoformat(
                item.get("enqueued_at", "2000-01-01T00:00:00+00:00")
            )
            age = (datetime.now(UTC) - enqueued_at).total_seconds()
            if age > _MAX_AGE_SECONDS:
                logger.info("pressure_forward: dropping stale item (%.0fs old)", age)
                _ack(raw)
                skipped += 1
                continue

            device_id = item.get("device_id")
            tenant_id = item.get("tenant_id")
            if device_id:
                delete_key(f"{_PENDING_PREFIX}{device_id}")

            try:
                device_uuid, tenant_uuid = as_uuid(device_id), as_uuid(tenant_id)
            except (ValueError, TypeError):
                logger.warning("pressure_forward: malformed device_id/tenant_id, dropping item")
                _ack(raw)
                skipped += 1
                continue

            try:
                device = db().get(device_model, device_uuid)
                if device is None:
                    _ack(raw)
                    skipped += 1
                    continue

                targets = list(db().scalars(
                    select(integration_model).where(
                        integration_model.tenant_id == tenant_uuid,
                        integration_model.measurement == MeasurementType.PRESSURE.value,
                        integration_model.enabled,
                    )
                ).all())
                if not targets:
                    _ack(raw)
                    skipped += 1
                    continue

                reading = db().execute(
                    select(pressure_model)
                    .where(pressure_model.device_id == device_uuid)
                    .order_by(desc(pressure_model.created_at))
                    .limit(1)
                ).scalar_one_or_none()
                if reading is None:
                    _ack(raw)
                    skipped += 1
                    continue

                ok = await _forward(db, device, reading, targets)
                if ok:
                    _ack(raw)
                    forwarded += 1
                else:
                    _handle_failure(item, raw)
                    failed += 1

            except Exception as exc:  # pylint: disable=broad-exception-caught
                recover_forwarding_error(
                    db, label="pressure_forward", subject_id=device_id,
                    item=item, raw=raw, retry=_handle_failure, log=logger, exc=exc,
                )
                failed += 1

    finally:
        db.remove()
        queue_release_lock(_DRAIN_LOCK, lock_token)

    if forwarded or failed:
        system_log_scheduler(
            f"pressure_forward: forwarded={forwarded} failed={failed} skipped={skipped}",
            level=LogLevel.INFO if not failed else LogLevel.WARNING,
        )


def _ack(raw) -> None:
    """Acknowledge a processing-list item once it no longer needs forwarding."""
    queue_lrem(_PROCESSING, raw)
    queue_zrem(_PROCESSING_TS, raw)


def _handle_failure(item: dict, raw) -> None:
    """Retry up to _MAX_RETRIES times, then dead-letter the item."""
    retry_or_dead_letter(
        item, raw, queue=_QUEUE, dead_letter=_DEAD, max_retries=_MAX_RETRIES,
        label="pressure_forward", push=queue_push, acknowledge=_ack, log=logger,
    )


async def task_reclaim_stale_pressure_forwards() -> None:
    """Move pressure_forward_processing items past the visibility timeout back
    onto pressure_forward_queue for another attempt."""
    reclaimed = reclaim_stale_items(
        processing=_PROCESSING, processing_timestamps=_PROCESSING_TS, queue=_QUEUE,
        visibility_timeout=_PROCESSING_VISIBILITY_TIMEOUT, now=time.time,
        list_stale=queue_zrangebyscore, reclaim=queue_reclaim_stale,
    )

    if reclaimed:
        logger.warning(
            "task_reclaim_stale_pressure_forwards: reclaimed %d stale item(s) past "
            "%ds visibility timeout", reclaimed, _PROCESSING_VISIBILITY_TIMEOUT,
        )
        system_log_scheduler(
            f"pressure_forward: reclaimed {reclaimed} stale processing item(s)",
            level=LogLevel.WARNING,
        )


def _template_values(device, reading) -> dict:
    """Build the ${key} substitution values for a pressure reading — pressure,
    temperature, battery, rssi, and device/batch identity."""
    return {
        "pressure": reading.pressure,
        "temperature": reading.temperature,
        "battery": reading.battery,
        "rssi": reading.rssi,
        "deviceName": device.name or "",
        "deviceId": str(device.id),
        "chipId": device.chip_id or "",
        "batchId": str(reading.batch_id) if reading.batch_id else "",
        "timestamp": reading.created_at.isoformat() if reading.created_at else "",
    }


def _brewfather_payload(device, reading) -> dict:
    """Brewfather's custom stream format for a pressure reading. The name is the device's own
    (the `[SG]` suffix marks specific gravity and has no meaning here). Missing values are
    left out. Mirrored by previewIntegration in web/src/core/integrations/integrationPreview.ts."""
    return without_missing({
        "name": device.name or "",
        "pressure": reading.pressure,
        "pressure_unit": "KPA" if reading.pressure is not None else None,
        "temp": reading.temperature,
        "temp_unit": "C" if reading.temperature is not None else None,
        "battery": reading.battery,
        "rssi": reading.rssi,
    })


async def _post_built_in(device, reading, integration) -> DeliveryOutcome:
    """Deliver to a brewfather_forward target via the shared
    oss.jobs._forward_common.deliver_built_in (15 minute window per device)."""
    return await deliver_built_in(
        integration, _brewfather_payload(device, reading), device.id,
        "pressure_forward", once_per_interval=True,
    )


async def _forward(db, device, reading, targets: list, *, on_disable=None) -> bool:
    """Deliver the reading to every enabled Integration target. Returns True if none
    failed outright (delivered, blocked or skipped all count; only a genuine failure
    means retry the item). Applies each target's outcome via apply_delivery_outcome
    before returning."""
    values = _template_values(device, reading)
    outcomes = []
    for integration in targets:
        if integration.type == IntegrationType.BREWFATHER_FORWARD.value:
            outcome = await _post_built_in(device, reading, integration)
        else:
            outcome = await deliver_custom(
                integration.config, values, device.id, "pressure_forward custom_forward"
            )
        outcomes.append(outcome)
        await apply_delivery_outcome(integration, outcome, on_disable)
    db().commit()
    return all(o != "failed" for o in outcomes)
