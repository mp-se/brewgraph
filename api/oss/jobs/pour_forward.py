# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Reliable Redis-backed queue: forward accepted pour events to every enabled
measurement=pour Integration target configured for the account.

Sibling of oss/jobs/gravity_forward.py — same reliable-queue mechanics
(pop-to-processing, ack, retry, dead-letter, reclaim sweep), a separate queue
so a stuck/misbehaving pour forward can never block gravity/pressure/temp
forwarding or vice versa. Only `custom_forward` applies here: pour has no
built-in payload type equivalent to ispindel_forward/brewfather_forward,
which are gravity-hydrometer concepts.

**Keyed on tap_id, not device_id** — `PourEvent` has no device column:
`write_pour(tap, payload)` is keyed on the tap, not a device. So this
module's subject is a `Tap`, not a `Device`, and its token set carries no
device tokens at all.

At ingest time the ingest path calls `enqueue_forward(tap_id, tenant_id)`.
`task_drain_pour_forward_queue` drains that queue every 30 seconds,
forwarding each tap's *latest* pour event to every enabled measurement=pour
`Integration` row for that account.
"""
import json
import logging
import time
from datetime import UTC, datetime

from sqlalchemy import desc, select

from core.cache import delete_key, set_key_if_absent
from core.enums import MeasurementType
from core.log import LogLevel, system_log_scheduler
from core.models.registry import resolve_model
from core.queue import (queue_acquire_lock, queue_len, queue_lrem,
                        queue_pop_to_processing, queue_push,
                        queue_reclaim_stale, queue_release_lock,
                        queue_renew_lock, queue_zrangebyscore, queue_zrem)
from core.db import create_session
from oss.jobs._forward_common import (apply_delivery_outcome, as_uuid, deliver_custom,
                                      recover_forwarding_error,
                                      reclaim_stale_items, retry_or_dead_letter)

logger = logging.getLogger(__name__)

_QUEUE = "pour_forward_queue"
_DEAD = "pour_forward_dead"
_DRAIN_LOCK = "pour_forward_drain_lock"
_DRAIN_LOCK_TTL = 120
_MAX_PER_RUN = 200
_MAX_RETRIES = 3
_MAX_AGE_SECONDS = 86_400  # drop items older than 24 h
_PENDING_PREFIX = "pour_forward_pending:"
_PENDING_TTL = 90  # 3x the 30s drain cadence -- coalescing window for a pour burst
_PROCESSING = "pour_forward_processing"
_PROCESSING_TS = "pour_forward_processing_ts"
_PROCESSING_VISIBILITY_TIMEOUT = 180


def enqueue_forward(tap_id, tenant_id) -> None:
    """Push a forwarding job onto the Redis queue. Called from the ingest path.

    The worker fetches the latest pour event for the tap at drain time — no
    pour_id required. A per-tap pending marker coalesces a burst of pours
    into a single queued job instead of one per pour.
    """
    pending_key = f"{_PENDING_PREFIX}{tap_id}"
    if not set_key_if_absent(pending_key, "1", ttl=_PENDING_TTL):
        return

    item = json.dumps({
        "tap_id": str(tap_id),
        "tenant_id": str(tenant_id),
        "enqueued_at": datetime.now(UTC).isoformat(),
        "attempts": 0,
    })
    if not queue_push(_QUEUE, item):
        delete_key(pending_key)
        logger.warning(
            "pour_forward: enqueue_forward failed to queue job for tap %s "
            "(Redis unavailable?)", tap_id,
        )


async def task_drain_pour_forward_queue() -> None:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Drain up to _MAX_PER_RUN items from the pour forward queue.

    Guarded by a distributed lock so a misconfigured multi-instance deployment
    cannot interleave drains. The lock's TTL is renewed after every item
    popped, so a live drain never lets a peer steal the lock mid-run.
    """
    depth = queue_len(_QUEUE)
    if depth == 0:
        return

    lock_token = queue_acquire_lock(_DRAIN_LOCK, ttl=_DRAIN_LOCK_TTL)
    if lock_token is None:
        logger.info("task_drain_pour_forward_queue: another worker holds the drain lock")
        return

    logger.info("task_drain_pour_forward_queue: %d items in queue", depth)
    forwarded = failed = skipped = 0

    pour_model = resolve_model("PourEvent")
    tap_model = resolve_model("Tap")
    integration_model = resolve_model("Integration")

    db = create_session()
    try:
        for _ in range(min(depth, _MAX_PER_RUN)):
            raw = queue_pop_to_processing(_QUEUE, _PROCESSING, _PROCESSING_TS)
            if raw is None:
                break

            if not queue_renew_lock(_DRAIN_LOCK, lock_token, ttl=_DRAIN_LOCK_TTL):
                logger.warning(
                    "task_drain_pour_forward_queue: lost drain lock ownership mid-run, "
                    "stopping before processing further items"
                )
                break

            try:
                item = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                logger.warning("pour_forward: malformed queue item dropped")
                _ack(raw)
                skipped += 1
                continue

            enqueued_at = datetime.fromisoformat(
                item.get("enqueued_at", "2000-01-01T00:00:00+00:00")
            )
            age = (datetime.now(UTC) - enqueued_at).total_seconds()
            if age > _MAX_AGE_SECONDS:
                logger.info("pour_forward: dropping stale item (%.0fs old)", age)
                _ack(raw)
                skipped += 1
                continue

            tap_id = item.get("tap_id")
            tenant_id = item.get("tenant_id")
            if tap_id:
                delete_key(f"{_PENDING_PREFIX}{tap_id}")

            try:
                tap_uuid, tenant_uuid = as_uuid(tap_id), as_uuid(tenant_id)
            except (ValueError, TypeError):
                logger.warning("pour_forward: malformed tap_id/tenant_id, dropping item")
                _ack(raw)
                skipped += 1
                continue

            try:
                tap = db().get(tap_model, tap_uuid)
                if tap is None:
                    _ack(raw)
                    skipped += 1
                    continue

                targets = list(db().scalars(
                    select(integration_model).where(
                        integration_model.tenant_id == tenant_uuid,
                        integration_model.measurement == MeasurementType.POUR.value,
                        integration_model.enabled,
                    )
                ).all())
                if not targets:
                    _ack(raw)
                    skipped += 1
                    continue

                reading = db().execute(
                    select(pour_model)
                    .where(pour_model.tap_id == tap_uuid)
                    .order_by(desc(pour_model.created_at))
                    .limit(1)
                ).scalar_one_or_none()
                if reading is None:
                    _ack(raw)
                    skipped += 1
                    continue

                ok = await _forward(db, tap, reading, targets)
                if ok:
                    _ack(raw)
                    forwarded += 1
                else:
                    _handle_failure(item, raw)
                    failed += 1

            except Exception as exc:  # pylint: disable=broad-exception-caught
                recover_forwarding_error(
                    db, label="pour_forward", subject_id=tap_id,
                    item=item, raw=raw, retry=_handle_failure, log=logger, exc=exc,
                )
                failed += 1

    finally:
        db.remove()
        queue_release_lock(_DRAIN_LOCK, lock_token)

    if forwarded or failed:
        system_log_scheduler(
            f"pour_forward: forwarded={forwarded} failed={failed} skipped={skipped}",
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
        label="pour_forward", push=queue_push, acknowledge=_ack, log=logger,
    )


async def task_reclaim_stale_pour_forwards() -> None:
    """Move pour_forward_processing items past the visibility timeout back
    onto pour_forward_queue for another attempt."""
    reclaimed = reclaim_stale_items(
        processing=_PROCESSING, processing_timestamps=_PROCESSING_TS, queue=_QUEUE,
        visibility_timeout=_PROCESSING_VISIBILITY_TIMEOUT, now=time.time,
        list_stale=queue_zrangebyscore, reclaim=queue_reclaim_stale,
    )

    if reclaimed:
        logger.warning(
            "task_reclaim_stale_pour_forwards: reclaimed %d stale item(s) past "
            "%ds visibility timeout", reclaimed, _PROCESSING_VISIBILITY_TIMEOUT,
        )
        system_log_scheduler(
            f"pour_forward: reclaimed {reclaimed} stale processing item(s)",
            level=LogLevel.WARNING,
        )


def _template_values(tap, reading) -> dict:
    """Build the ${key} substitution values for a pour event — pour_amount,
    volume_remaining, tap/vessel/batch identity, and a timestamp. No device
    tokens at all: PourEvent carries no device_id, only
    tap_id/vessel_id/batch_id."""
    return {
        "pourAmount": reading.pour_amount,
        "volumeRemaining": reading.volume_remaining,
        "tapId": str(tap.id),
        "tapName": tap.name or "",
        "vesselId": str(reading.vessel_id) if reading.vessel_id else "",
        "batchId": str(reading.batch_id) if reading.batch_id else "",
        "timestamp": reading.created_at.isoformat() if reading.created_at else "",
    }


async def _forward(db, tap, reading, targets: list, *, on_disable=None) -> bool:
    """Deliver the pour event to every enabled Integration target. Returns True if none
    failed outright (delivered or blocked both count; only a genuine failure means
    retry the item). Every target here is custom_forward -- pour has no built-in
    payload type. Applies each target's outcome via apply_delivery_outcome before
    returning."""
    values = _template_values(tap, reading)
    outcomes = []
    for integration in targets:
        outcome = await deliver_custom(
            integration.config, values, tap.id, "pour_forward custom_forward"
        )
        outcomes.append(outcome)
        await apply_delivery_outcome(integration, outcome, on_disable)
    db().commit()
    return all(o != "failed" for o in outcomes)
