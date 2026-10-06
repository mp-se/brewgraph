# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Reliable Redis-backed queue: forward accepted gravity readings to every
enabled Integration target configured for the account.

Nothing here is tenant-specific: every queue item and every `Integration` row
carries `tenant_id` as a bare column with no FK — this app is single-tenant
and every row carries `DEFAULT_TENANT_ID`; there is no tenant table to
reference — which is all the drain and reclaim jobs need to look up the
right integration targets. This module used to be a synchronous 15-minute
full-device-table scan reading two hardcoded `Device` columns; replaced with
this reliable, hardened Redis queue instead.

At ingest time the ingest path calls `enqueue_forward(device_id, tenant_id)`.
`task_drain_gravity_forward_queue` drains that queue every 30 seconds,
forwarding each device's *latest* reading to every enabled `Integration` row
for that account — an integration is account-level, not per-device, so one
queued device item can fan out to several targets.

Reliable-queue pattern: each drained item moves atomically into
`gravity_forward_processing` via `queue_pop_to_processing`, which also
records the move time in `gravity_forward_processing_ts`. An item is only
removed from both (`queue_lrem`/`queue_zrem`) after every target for it has
reached a terminal outcome, or after `_handle_failure`'s retry-push or
dead-letter move has actually landed — a crash in between leaves it
recoverable rather than silently dropped. A failure on any one target retries
the *whole* item (every target is attempted again, not just the failed one)
— simpler than per-target retry bookkeeping, and forwards are best-effort
telemetry a duplicate delivery doesn't corrupt.

Retry policy: up to `_MAX_RETRIES` attempts per item. On final failure the
item is moved to `gravity_forward_dead` for operator inspection.

`task_reclaim_stale_gravity_forwards` reads `gravity_forward_processing_ts`
back: an item stuck in processing longer than
`_PROCESSING_VISIBILITY_TIMEOUT` (a crash mid-forward, no retry/dead-letter
push ever landed) is moved back onto the main queue for another attempt.
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
                                      deliver_custom,
                                      without_missing,
                                      reclaim_stale_items,
                                      recover_forwarding_error,
                                      render_template as _render_values,
                                      retry_or_dead_letter)

logger = logging.getLogger(__name__)

_QUEUE = "gravity_forward_queue"
_DEAD = "gravity_forward_dead"
_DRAIN_LOCK = "gravity_forward_drain_lock"
# Liveness TTL, not a worst-case bound: the drain loop renews it after every
# item popped, so a live drain never lets it lapse. Only a dead worker's lock
# is meant to expire on this.
_DRAIN_LOCK_TTL = 120
_MAX_PER_RUN = 200
_MAX_RETRIES = 3
_MAX_AGE_SECONDS = 86_400  # drop items older than 24 h
_PENDING_PREFIX = "gravity_forward_pending:"
_PENDING_TTL = 90  # 3x the 30s drain cadence -- coalescing window for a reading burst
_PROCESSING = "gravity_forward_processing"
_PROCESSING_TS = "gravity_forward_processing_ts"
# A legitimate in-flight item sees one sequential HTTP call per configured
# target (_TIMEOUT's 5s connect + 10s read each) plus scheduler/lock jitter.
# 180s gives a handful of targets a wide margin so a still-processing item is
# never falsely reclaimed, while staying far short of _MAX_AGE_SECONDS so a
# genuinely stuck item (worker crash) recovers within a couple of sweep runs.
_PROCESSING_VISIBILITY_TIMEOUT = 180


def enqueue_forward(device_id, tenant_id) -> None:
    """Push a forwarding job onto the Redis queue. Called from the ingest path.

    The worker fetches the latest reading for the device at drain time — no
    reading_id required. A per-device pending marker coalesces a burst of
    ingests into a single queued job instead of one per reading; the marker is
    cleared once the drain loop pops that device's item.
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
            "gravity_forward: enqueue_forward failed to queue job for device %s "
            "(Redis unavailable?)", device_id,
        )


async def task_drain_gravity_forward_queue() -> None:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Drain up to _MAX_PER_RUN items from the gravity forward queue.

    Guarded by a distributed lock so a misconfigured multi-instance deployment
    cannot interleave drains (duplicate retries, out-of-order dead-lettering).
    Pops themselves are atomic. The lock's TTL is renewed after every item
    popped rather than sized for the drain's worst case, so a live drain never
    lets a peer steal the lock mid-run.
    """
    depth = queue_len(_QUEUE)
    if depth == 0:
        return

    lock_token = queue_acquire_lock(_DRAIN_LOCK, ttl=_DRAIN_LOCK_TTL)
    if lock_token is None:
        logger.info("task_drain_gravity_forward_queue: another worker holds the drain lock")
        return

    logger.info("task_drain_gravity_forward_queue: %d items in queue", depth)
    forwarded = failed = skipped = 0

    gravity_model = resolve_model("GravityReading")
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
                    "task_drain_gravity_forward_queue: lost drain lock ownership mid-run, "
                    "stopping before processing further items"
                )
                break

            try:
                item = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                logger.warning("gravity_forward: malformed queue item dropped")
                _ack(raw)
                skipped += 1
                continue

            enqueued_at = datetime.fromisoformat(
                item.get("enqueued_at", "2000-01-01T00:00:00+00:00")
            )
            age = (datetime.now(UTC) - enqueued_at).total_seconds()
            if age > _MAX_AGE_SECONDS:
                logger.info("gravity_forward: dropping stale item (%.0fs old)", age)
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
                logger.warning("gravity_forward: malformed device_id/tenant_id, dropping item")
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
                        integration_model.measurement == MeasurementType.GRAVITY.value,
                        integration_model.enabled,
                    )
                ).all())
                if not targets:
                    _ack(raw)
                    skipped += 1
                    continue

                reading = db().execute(
                    select(gravity_model)
                    .where(gravity_model.device_id == device_uuid)
                    .order_by(desc(gravity_model.created_at))
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
                    db, label="gravity_forward", subject_id=device_id,
                    item=item, raw=raw, retry=_handle_failure, log=logger, exc=exc,
                )
                failed += 1

    finally:
        db.remove()
        queue_release_lock(_DRAIN_LOCK, lock_token)

    if forwarded or failed:
        system_log_scheduler(
            f"gravity_forward: forwarded={forwarded} failed={failed} skipped={skipped}",
            level=LogLevel.INFO if not failed else LogLevel.WARNING,
        )


def _ack(raw) -> None:
    """Acknowledge a processing-list item once it no longer needs forwarding —
    forwarded successfully, dropped as malformed/stale/unroutable, or handed
    off to retry/dead-letter by _handle_failure."""
    queue_lrem(_PROCESSING, raw)
    queue_zrem(_PROCESSING_TS, raw)


def _handle_failure(item: dict, raw) -> None:
    """Retry up to _MAX_RETRIES times, then dead-letter the item.

    The processing-list entry is only acked after the retry-push or
    dead-letter push actually lands — a crash between the pop and this point
    leaves the item in gravity_forward_processing, recoverable by
    task_reclaim_stale_gravity_forwards, instead of silently discarding it.
    """
    retry_or_dead_letter(
        item, raw, queue=_QUEUE, dead_letter=_DEAD, max_retries=_MAX_RETRIES,
        label="gravity_forward", push=queue_push, acknowledge=_ack, log=logger,
    )


async def task_reclaim_stale_gravity_forwards() -> None:
    """Move gravity_forward_processing items past the visibility timeout back
    onto gravity_forward_queue for another attempt.

    A crash between queue_pop_to_processing and _ack/_handle_failure's
    acknowledgment leaves an item in gravity_forward_processing with nothing
    else reading it back — this sweep is that read-back.
    """
    reclaimed = reclaim_stale_items(
        processing=_PROCESSING, processing_timestamps=_PROCESSING_TS, queue=_QUEUE,
        visibility_timeout=_PROCESSING_VISIBILITY_TIMEOUT, now=time.time,
        list_stale=queue_zrangebyscore, reclaim=queue_reclaim_stale,
    )

    if reclaimed:
        logger.warning(
            "task_reclaim_stale_gravity_forwards: reclaimed %d stale item(s) past "
            "%ds visibility timeout", reclaimed, _PROCESSING_VISIBILITY_TIMEOUT,
        )
        system_log_scheduler(
            f"gravity_forward: reclaimed {reclaimed} stale processing item(s)",
            level=LogLevel.WARNING,
        )


async def _forward(db, device, reading, targets: list, *, on_disable=None) -> bool:
    """POST the reading to every enabled Integration target. Returns True if none failed
    outright (delivered or blocked both count; only a genuine failure means retry the item).
    Applies each target's outcome via apply_delivery_outcome before returning."""
    outcomes = []
    for integration in targets:
        if integration.type == IntegrationType.CUSTOM_FORWARD.value:
            outcome = await _post_custom(device, reading, integration)
        else:
            outcome = await _post_built_in(device, reading, integration)
        outcomes.append(outcome)
        await apply_delivery_outcome(integration, outcome, on_disable)
    db().commit()
    return all(o != "failed" for o in outcomes)


# The reading does not store how often the device reports, so the iSpindel
# payload carries a fixed interval. 900 s (15 min) is what external services
# that consume the iSpindel format expect.
ISPINDEL_FORWARD_INTERVAL_SECONDS = 900

def _ispindel_payload(device, reading) -> dict:
    """The original iSpindel format. `ID` is the device's chip id, and no
    `token` is ever sent. Missing values are left out, never defaulted."""
    return without_missing({
        "name": device.name,
        "ID": device.chip_id,
        "angle": reading.angle,
        "temperature": reading.temperature,
        "temp_units": "C",
        "battery": reading.battery,
        "gravity": reading.gravity,
        "interval": ISPINDEL_FORWARD_INTERVAL_SECONDS,
        "RSSI": reading.rssi,
    })


def _brewfather_name(device) -> str:
    """The device name with `[SG]` appended unless it has it: that suffix tells Brewfather the
    gravity is specific gravity (`gravity_unit` "G")."""
    name = device.name or ""
    return name if "[SG]" in name else name + "[SG]"


def _brewfather_payload(device, reading) -> dict:
    """Brewfather's custom stream format. Missing values are left out."""
    return without_missing({
        "name": _brewfather_name(device),
        "temp": reading.temperature,
        "temp_unit": "C",
        "gravity": reading.gravity,
        "gravity_unit": "G",
        "battery": reading.battery,
        "angle": reading.angle,
        "rssi": reading.rssi,
    })


def _template_values(device, reading) -> dict:
    """Build the ${key} substitution values for a gravity reading — gravity,
    temperature, angle, velocity, battery, rssi, and device/batch identity."""
    return {
        "gravity": reading.gravity,
        "temperature": reading.temperature,
        "angle": reading.angle,
        "velocity": reading.velocity,
        "battery": reading.battery,
        "rssi": reading.rssi,
        "deviceName": device.name or "",
        "deviceId": str(device.id),
        "chipId": device.chip_id or "",
        "batchId": str(reading.batch_id) if reading.batch_id else "",
        "timestamp": reading.created_at.isoformat() if reading.created_at else "",
    }


def _render_template(template: str, device, reading) -> str:
    """Plain ${key} string substitution — deliberately not a general-purpose
    template engine, since the string is user-supplied and rendered
    server-side on every forward. Thin wrapper over the shared
    oss.jobs._forward_common.render_template, kept with this signature so
    callers/tests need not build the values dict themselves."""
    return _render_values(template, _template_values(device, reading))


async def _post_built_in(device, reading, integration) -> DeliveryOutcome:
    """Deliver to the ispindel_forward/brewfather_forward fixed payload shape via the
    shared oss.jobs._forward_common.deliver_built_in. brewfather_forward is limited to
    one request per device per 15 minutes there."""
    is_ispindel = integration.type == IntegrationType.ISPINDEL_FORWARD.value
    payload = (_ispindel_payload if is_ispindel else _brewfather_payload)(device, reading)
    return await deliver_built_in(
        integration, payload, device.id, "gravity_forward", once_per_interval=not is_ispindel,
    )


async def _post_custom(device, reading, integration) -> DeliveryOutcome:
    """Deliver to a custom_forward target via the shared
    oss.jobs._forward_common.deliver_custom helper — the same one the
    pressure/pour/temp forward jobs use, just supplied gravity's own
    device/reading-derived values."""
    values = _template_values(device, reading)
    return await deliver_custom(
        integration.config, values, device.id, "gravity_forward custom_forward"
    )
