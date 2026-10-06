# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/jobs/pour_forward.py — the reliable Redis-queue forwarding job
for measurement=pour Integration targets. Tap-keyed, not device-keyed
(PourEvent has no device column). Mirrors tests/test_gravity_forward.py's
structure and its _FakeReliableRedis-based reliable-queue mechanics tests,
adapted for the tap/vessel subject shape."""
# pylint: disable=missing-function-docstring
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oss.jobs._forward_common import render_template

from oss.jobs.pour_forward import (
    _DEAD,
    _PROCESSING,
    _PROCESSING_TS,
    _PROCESSING_VISIBILITY_TIMEOUT,
    _QUEUE,
    _forward,
    _template_values,
    enqueue_forward,
    task_drain_pour_forward_queue,
    task_reclaim_stale_pour_forwards,
)

_MAX_AGE_SECONDS = 86_400
_MAX_RETRIES = 3


def _reading(**kwargs):
    r = MagicMock()
    r.tap_id = uuid.uuid4()
    r.vessel_id = kwargs.get("vessel_id", uuid.uuid4())
    r.batch_id = kwargs.get("batch_id", uuid.uuid4())
    r.pour_amount = kwargs.get("pour_amount", 0.33)
    r.volume_remaining = kwargs.get("volume_remaining", 12.4)
    r.created_at = kwargs.get("created_at", datetime(2026, 9, 1, tzinfo=UTC))
    return r


def _tap(**kwargs):
    t = MagicMock()
    t.id = kwargs.get("id", uuid.uuid4())
    t.name = kwargs.get("name", "Tap 1")
    return t


def _integration(url="http://example.com/hook", enabled=True, method="POST",
                 template="a=${pourAmount}", headers=None):
    row = MagicMock()
    row.type = "custom_forward"
    row.enabled = enabled
    row.config = {"url": url, "method": method, "headers": headers or {}, "template": template}
    row.consecutive_failures = 0
    return row


# ---------------------------------------------------------------------------
# _template_values
# ---------------------------------------------------------------------------

class TestTemplateValues:
    """The pour token set: no device tokens at all -- PourEvent carries no
    device_id, only tap_id/vessel_id/batch_id."""

    def test_contains_documented_tokens(self):
        t, r = _tap(name="Tap 1"), _reading(pour_amount=0.33, volume_remaining=12.4)
        values = _template_values(t, r)
        assert values["pourAmount"] == 0.33
        assert values["volumeRemaining"] == 12.4
        assert values["tapId"] == str(t.id)
        assert values["tapName"] == "Tap 1"
        assert values["vesselId"] == str(r.vessel_id)
        assert values["batchId"] == str(r.batch_id)
        assert set(values.keys()) == {
            "pourAmount", "volumeRemaining", "tapId", "tapName",
            "vesselId", "batchId", "timestamp",
        }
        assert "deviceId" not in values
        assert "deviceName" not in values

    def test_missing_vessel_and_batch_id_render_empty_string(self):
        values = _template_values(_tap(), _reading(vessel_id=None, batch_id=None))
        assert values["vesselId"] == ""
        assert values["batchId"] == ""


def test_missing_amounts_render_null():
    values = _template_values(_tap(), _reading(pour_amount=None, volume_remaining=None))
    rendered = render_template('{"a":${pourAmount},"v":${volumeRemaining}}', values)
    assert json.loads(rendered) == {"a": None, "v": None}


# ---------------------------------------------------------------------------
# _forward
# ---------------------------------------------------------------------------

class TestForward:
    """Every target is custom_forward -- pour has no built-in payload type."""

    @pytest.mark.asyncio
    async def test_delegates_to_shared_deliver_custom(self):
        tap, reading = _tap(), _reading(pour_amount=0.5)
        target = _integration()
        db = MagicMock()
        with patch("oss.jobs.pour_forward.deliver_custom", new_callable=AsyncMock,
                   return_value="delivered") as mock_deliver:
            result = await _forward(db, tap, reading, [target])
        assert result is True
        args = mock_deliver.call_args[0]
        assert args[0] == target.config
        assert args[1]["pourAmount"] == 0.5
        assert args[2] == tap.id
        assert args[3] == "pour_forward custom_forward"

    @pytest.mark.asyncio
    async def test_all_must_succeed(self):
        tap, reading = _tap(), _reading()
        targets = [_integration(), _integration()]
        db = MagicMock()
        with patch("oss.jobs.pour_forward.deliver_custom", new_callable=AsyncMock,
                   side_effect=["delivered", "failed"]):
            assert await _forward(db, tap, reading, targets) is False


# ---------------------------------------------------------------------------
# enqueue_forward
# ---------------------------------------------------------------------------

class TestEnqueueForward:
    """Tests for enqueue_forward's queued payload shape."""

    def test_pushes_json_with_tap_and_tenant(self):
        with patch("oss.jobs.pour_forward.set_key_if_absent", return_value=True), \
             patch("oss.jobs.pour_forward.queue_push") as mock_push:
            enqueue_forward("tap-1", "tenant-1")
            queue_name, raw = mock_push.call_args[0]
            assert queue_name == _QUEUE
            item = json.loads(raw)
            assert item["tap_id"] == "tap-1"
            assert item["tenant_id"] == "tenant-1"
            assert item["attempts"] == 0

    def test_coalesces_when_a_job_is_already_pending(self):
        with patch("oss.jobs.pour_forward.set_key_if_absent", return_value=False), \
             patch("oss.jobs.pour_forward.queue_push") as mock_push:
            enqueue_forward("tap-1", "tenant-1")
        mock_push.assert_not_called()

    def test_logs_warning_when_queue_push_fails(self, caplog):
        with patch("oss.jobs.pour_forward.set_key_if_absent", return_value=True), \
             patch("oss.jobs.pour_forward.queue_push", return_value=False), \
             patch("oss.jobs.pour_forward.delete_key") as mock_delete, \
             caplog.at_level("WARNING"):
            enqueue_forward("tap-1", "tenant-1")
        assert any("tap-1" in record.message for record in caplog.records)
        mock_delete.assert_called_once_with("pour_forward_pending:tap-1")


# ---------------------------------------------------------------------------
# task_drain_pour_forward_queue
# ---------------------------------------------------------------------------

def _make_item(
    tap_id="00000000-0000-0000-0000-000000000003",
    tenant_id="00000000-0000-0000-0000-000000000002",
    age_seconds=0, attempts=0,
) -> str:
    enqueued = datetime.now(UTC) - timedelta(seconds=age_seconds)
    return json.dumps({
        "tap_id": tap_id,
        "tenant_id": tenant_id,
        "enqueued_at": enqueued.isoformat(),
        "attempts": attempts,
    })


def _scoped_db(tap, reading, integrations):
    session = MagicMock()
    session.get.return_value = tap
    session.execute.return_value.scalar_one_or_none.return_value = reading
    session.scalars.return_value.all.return_value = integrations
    scoped = MagicMock()
    scoped.return_value = session
    scoped.remove = MagicMock()
    return scoped


class TestDrainQueue:
    """Tests for task_drain_pour_forward_queue's per-item processing."""

    @pytest.mark.asyncio
    async def test_empty_queue_returns_early(self):
        with patch("oss.jobs.pour_forward.queue_len", return_value=0):
            await task_drain_pour_forward_queue()  # must not raise

    @pytest.mark.asyncio
    async def test_skips_unknown_tap(self):
        raw = _make_item()
        session = MagicMock()
        session.get.return_value = None
        scoped = MagicMock(return_value=session, remove=MagicMock())
        with patch("oss.jobs.pour_forward.queue_len", return_value=1), \
             patch("oss.jobs.pour_forward.queue_pop_to_processing", return_value=raw.encode()), \
             patch("oss.jobs.pour_forward.create_session", return_value=scoped):
            await task_drain_pour_forward_queue()  # must not raise

    @pytest.mark.asyncio
    async def test_no_configured_targets_skips_item(self):
        raw = _make_item(tenant_id=str(uuid.uuid4()))
        scoped = _scoped_db(_tap(), _reading(), [])
        with patch("oss.jobs.pour_forward.queue_len", return_value=1), \
             patch("oss.jobs.pour_forward.queue_pop_to_processing", return_value=raw.encode()), \
             patch("oss.jobs.pour_forward.create_session", return_value=scoped):
            await task_drain_pour_forward_queue()  # must not raise

    @pytest.mark.asyncio
    async def test_fans_out_to_every_enabled_target(self):
        raw = _make_item(tenant_id=str(uuid.uuid4()))
        targets = [_integration(), _integration()]
        scoped = _scoped_db(_tap(), _reading(), targets)

        with patch("oss.jobs.pour_forward.queue_len", return_value=1), \
             patch("oss.jobs.pour_forward.queue_pop_to_processing", return_value=raw.encode()), \
             patch("oss.jobs.pour_forward.create_session", return_value=scoped), \
             patch("oss.jobs.pour_forward.deliver_custom",
                   new_callable=AsyncMock, return_value="delivered") as mock_deliver:
            await task_drain_pour_forward_queue()

        assert mock_deliver.await_count == 2


# ---------------------------------------------------------------------------
# Reliable-queue mechanics: real (unmocked) core.queue calls against a fake
# Redis, so these tests exercise the actual atomicity contract rather than a
# MagicMock that would accept any call.
# ---------------------------------------------------------------------------

class _FakeReliableRedis:
    """In-memory Redis stand-in covering SET/GET (lock), list/sorted-set ops,
    and EVAL for all three Lua scripts core.queue's primitives use."""

    def __init__(self):
        self.store: dict = {}
        self.lists: dict = {}
        self.zsets: dict = {}

    def set(self, name, value, nx=False, ex=None):  # pylint: disable=unused-argument
        if nx and name in self.store:
            return False
        self.store[name] = value
        return True

    def get(self, name):
        return self.store.get(name)

    def delete(self, name):
        self.store.pop(name, None)

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)
        return 1

    def rpop(self, key):
        lst = self.lists.get(key)
        return lst.pop() if lst else None

    def llen(self, key):
        return len(self.lists.get(key, []))

    def lrem(self, key, _count, value):
        lst = self.lists.get(key, [])
        if value in lst:
            lst.remove(value)
            return 1
        return 0

    def zrem(self, key, value):
        return 1 if self.zsets.get(key, {}).pop(value, None) is not None else 0

    def zrangebyscore(self, key, _min_score, max_score):
        zset = self.zsets.get(key, {})
        return [m for m, s in sorted(zset.items(), key=lambda kv: kv[1]) if s <= max_score]

    def eval(self, script, numkeys, *args):  # pylint: disable=too-many-locals
        keys, argv = args[:numkeys], args[numkeys:]
        if "rpoplpush" in script:
            src, dst, ts = keys
            raw = self.rpop(src)
            if raw is not None:
                self.lpush(dst, raw)
                self.zsets.setdefault(ts, {})[raw] = float(argv[0])
            return raw
        if "lrem" in script:
            processing, ts, dest = keys
            member = argv[0]
            removed = self.lrem(processing, 1, member)
            self.zrem(ts, member)
            if removed:
                self.lpush(dest, member)
            return removed
        key, token = keys[0], argv[0]
        if self.store.get(key) != token:
            return 0
        if "del" in script:
            del self.store[key]
        return 1


def _patched_redis(fake):
    return (
        patch("core.queue.pool", MagicMock()),
        patch("core.queue.redis.Redis", return_value=fake),
        patch("core.cache.pool", MagicMock()),
        patch("core.cache.redis.Redis", return_value=fake),
    )


class TestReliableQueueMechanics:
    """End-to-end coverage of the pop-into-processing / ack / reclaim cycle."""

    @pytest.mark.asyncio
    async def test_crash_mid_forward_acks_once_retry_push_lands(self):
        fake = _FakeReliableRedis()
        raw_item = _make_item(attempts=0).encode()
        fake.lpush(_QUEUE, raw_item)

        scoped = _scoped_db(_tap(), _reading(), [_integration()])
        patches = _patched_redis(fake)
        with patches[0], patches[1], patches[2], patches[3], \
             patch("oss.jobs.pour_forward.create_session", return_value=scoped), \
            patch("oss.jobs.pour_forward._forward",
                   new_callable=AsyncMock, side_effect=RuntimeError("crash")):
            await task_drain_pour_forward_queue()

        scoped.return_value.rollback.assert_called_once_with()
        assert raw_item not in fake.lists.get(_PROCESSING, [])
        assert raw_item not in fake.zsets.get(_PROCESSING_TS, {})
        requeued = [json.loads(v) for v in fake.lists.get(_QUEUE, [])]
        assert any(r["attempts"] == 1 for r in requeued)

    @pytest.mark.asyncio
    async def test_dead_letters_after_max_retries(self):
        fake = _FakeReliableRedis()
        raw_item = _make_item(attempts=_MAX_RETRIES - 1).encode()
        fake.lpush(_QUEUE, raw_item)

        scoped = _scoped_db(_tap(), _reading(), [_integration()])
        patches = _patched_redis(fake)
        with patches[0], patches[1], patches[2], patches[3], \
             patch("oss.jobs.pour_forward.create_session", return_value=scoped), \
             patch("oss.jobs.pour_forward._forward",
                   new_callable=AsyncMock, side_effect=RuntimeError("crash")):
            await task_drain_pour_forward_queue()

        assert raw_item not in fake.lists.get(_PROCESSING, [])
        assert len(fake.lists.get(_DEAD, [])) == 1

    @pytest.mark.asyncio
    async def test_reclaim_sweep_recovers_a_stale_processing_item(self):
        fake = _FakeReliableRedis()
        stale_item = _make_item(tap_id="tap-stale").encode()
        fake.lists[_PROCESSING] = [stale_item]
        fake.zsets[_PROCESSING_TS] = {
            stale_item: time.time() - _PROCESSING_VISIBILITY_TIMEOUT - 30
        }

        patches = _patched_redis(fake)
        with patches[0], patches[1], patches[2], patches[3]:
            await task_reclaim_stale_pour_forwards()

        assert stale_item not in fake.lists.get(_PROCESSING, [])
        assert stale_item not in fake.zsets.get(_PROCESSING_TS, {})
        assert stale_item in fake.lists.get(_QUEUE, [])

    @pytest.mark.asyncio
    async def test_reclaim_sweep_does_not_touch_an_in_flight_item(self):
        fake = _FakeReliableRedis()
        fresh_item = _make_item(tap_id="tap-fresh").encode()
        fake.lists[_PROCESSING] = [fresh_item]
        fake.zsets[_PROCESSING_TS] = {fresh_item: time.time()}

        patches = _patched_redis(fake)
        with patches[0], patches[1], patches[2], patches[3]:
            await task_reclaim_stale_pour_forwards()

        assert fresh_item in fake.lists.get(_PROCESSING, [])
        assert fresh_item not in fake.lists.get(_QUEUE, [])
