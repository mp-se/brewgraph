# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/jobs/pressure_forward.py — the reliable Redis-queue forwarding
job for measurement=pressure Integration targets. Mirrors
tests/test_gravity_forward.py's structure and its _FakeReliableRedis-based
reliable-queue mechanics tests."""
# pylint: disable=missing-function-docstring
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oss.jobs._forward_common import render_template

from oss.jobs.pressure_forward import (
    _DEAD,
    _PROCESSING,
    _PROCESSING_TS,
    _PROCESSING_VISIBILITY_TIMEOUT,
    _QUEUE,
    _forward,
    _template_values,
    enqueue_forward,
    task_drain_pressure_forward_queue,
    task_reclaim_stale_pressure_forwards,
)

_MAX_AGE_SECONDS = 86_400
_MAX_RETRIES = 3


def _reading(**kwargs):
    r = MagicMock()
    r.device_id = uuid.uuid4()
    r.batch_id = kwargs.get("batch_id", uuid.uuid4())
    r.pressure = kwargs.get("pressure", 12.5)
    r.temperature = kwargs.get("temperature", 4.0)
    r.battery = kwargs.get("battery", 3.8)
    r.rssi = kwargs.get("rssi", -60.0)
    r.created_at = kwargs.get("created_at", datetime(2026, 9, 1, tzinfo=UTC))
    return r


def _device(**kwargs):
    d = MagicMock()
    d.id = kwargs.get("id", uuid.uuid4())
    d.name = kwargs.get("name", "MyDevice")
    d.chip_id = kwargs.get("chip_id", "ABC123")
    return d


def _integration(url="http://example.com/hook", enabled=True, method="POST",
                 template="p=${pressure}", headers=None):
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
    """The pressure token set: no ${gravity}/${angle}/${velocity}."""

    def test_contains_documented_tokens(self):
        d, r = _device(name="Kitchen", chip_id="A1B2"), _reading(pressure=12.5, temperature=4.0)
        values = _template_values(d, r)
        assert values["pressure"] == 12.5
        assert values["temperature"] == 4.0
        assert values["deviceName"] == "Kitchen"
        assert values["chipId"] == "A1B2"
        assert values["deviceId"] == str(d.id)
        assert values["batchId"] == str(r.batch_id)
        assert set(values.keys()) == {
            "pressure", "temperature", "battery", "rssi",
            "deviceName", "deviceId", "chipId", "batchId", "timestamp",
        }

    def test_missing_batch_id_renders_empty_string(self):
        values = _template_values(_device(), _reading(batch_id=None))
        assert values["batchId"] == ""


def test_missing_values_stay_none_not_zero():
    values = _template_values(_device(), _reading(temperature=None, battery=None, rssi=None))
    assert values["temperature"] is None
    assert values["battery"] is None
    assert values["rssi"] is None


def test_missing_values_render_null_in_a_json_template():
    values = _template_values(_device(), _reading(temperature=None, battery=None, rssi=None))
    rendered = render_template(
        '{"p":${pressure},"t":${temperature},"b":${battery},"r":${rssi}}', values
    )
    assert json.loads(rendered) == {"p": 12.5, "t": None, "b": None, "r": None}


# ---------------------------------------------------------------------------
# _forward
# ---------------------------------------------------------------------------

class TestForward:
    """Every target is custom_forward -- pressure has no built-in payload type."""

    @pytest.mark.asyncio
    async def test_delegates_to_shared_deliver_custom(self):
        device, reading = _device(), _reading(pressure=13.1)
        target = _integration()
        db = MagicMock()
        with patch("oss.jobs.pressure_forward.deliver_custom", new_callable=AsyncMock,
                   return_value="delivered") as mock_deliver:
            result = await _forward(db, device, reading, [target])
        assert result is True
        args = mock_deliver.call_args[0]
        assert args[0] == target.config
        assert args[1]["pressure"] == 13.1
        assert args[2] == device.id
        assert args[3] == "pressure_forward custom_forward"

    @pytest.mark.asyncio
    async def test_all_must_succeed(self):
        device, reading = _device(), _reading()
        targets = [_integration(), _integration()]
        db = MagicMock()
        with patch("oss.jobs.pressure_forward.deliver_custom", new_callable=AsyncMock,
                   side_effect=["delivered", "failed"]):
            assert await _forward(db, device, reading, targets) is False


# ---------------------------------------------------------------------------
# enqueue_forward
# ---------------------------------------------------------------------------

class TestEnqueueForward:
    """Tests for enqueue_forward's queued payload shape."""

    def test_pushes_json_with_device_and_tenant(self):
        with patch("oss.jobs.pressure_forward.set_key_if_absent", return_value=True), \
             patch("oss.jobs.pressure_forward.queue_push") as mock_push:
            enqueue_forward("dev-1", "tenant-1")
            queue_name, raw = mock_push.call_args[0]
            assert queue_name == _QUEUE
            item = json.loads(raw)
            assert item["device_id"] == "dev-1"
            assert item["tenant_id"] == "tenant-1"
            assert item["attempts"] == 0

    def test_coalesces_when_a_job_is_already_pending(self):
        with patch("oss.jobs.pressure_forward.set_key_if_absent", return_value=False), \
             patch("oss.jobs.pressure_forward.queue_push") as mock_push:
            enqueue_forward("dev-1", "tenant-1")
        mock_push.assert_not_called()

    def test_logs_warning_when_queue_push_fails(self, caplog):
        with patch("oss.jobs.pressure_forward.set_key_if_absent", return_value=True), \
             patch("oss.jobs.pressure_forward.queue_push", return_value=False), \
             patch("oss.jobs.pressure_forward.delete_key") as mock_delete, \
             caplog.at_level("WARNING"):
            enqueue_forward("dev-1", "tenant-1")
        assert any("dev-1" in record.message for record in caplog.records)
        mock_delete.assert_called_once_with("pressure_forward_pending:dev-1")


# ---------------------------------------------------------------------------
# task_drain_pressure_forward_queue
# ---------------------------------------------------------------------------

def _make_item(
    device_id="00000000-0000-0000-0000-000000000001",
    tenant_id="00000000-0000-0000-0000-000000000002",
    age_seconds=0, attempts=0,
) -> str:
    enqueued = datetime.now(UTC) - timedelta(seconds=age_seconds)
    return json.dumps({
        "device_id": device_id,
        "tenant_id": tenant_id,
        "enqueued_at": enqueued.isoformat(),
        "attempts": attempts,
    })


def _scoped_db(device, reading, integrations):
    session = MagicMock()
    session.get.return_value = device
    session.execute.return_value.scalar_one_or_none.return_value = reading
    session.scalars.return_value.all.return_value = integrations
    scoped = MagicMock()
    scoped.return_value = session
    scoped.remove = MagicMock()
    return scoped


class TestDrainQueue:
    """Tests for task_drain_pressure_forward_queue's per-item processing."""

    @pytest.mark.asyncio
    async def test_empty_queue_returns_early(self):
        with patch("oss.jobs.pressure_forward.queue_len", return_value=0):
            await task_drain_pressure_forward_queue()  # must not raise

    @pytest.mark.asyncio
    async def test_skips_unknown_device(self):
        raw = _make_item()
        session = MagicMock()
        session.get.return_value = None
        scoped = MagicMock(return_value=session, remove=MagicMock())
        with patch("oss.jobs.pressure_forward.queue_len", return_value=1), \
             patch("oss.jobs.pressure_forward.queue_pop_to_processing",
                   return_value=raw.encode()), \
             patch("oss.jobs.pressure_forward.create_session", return_value=scoped):
            await task_drain_pressure_forward_queue()  # must not raise

    @pytest.mark.asyncio
    async def test_no_configured_targets_skips_item(self):
        raw = _make_item(tenant_id=str(uuid.uuid4()))
        scoped = _scoped_db(_device(), _reading(), [])
        with patch("oss.jobs.pressure_forward.queue_len", return_value=1), \
             patch("oss.jobs.pressure_forward.queue_pop_to_processing",
                   return_value=raw.encode()), \
             patch("oss.jobs.pressure_forward.create_session", return_value=scoped):
            await task_drain_pressure_forward_queue()  # must not raise

    @pytest.mark.asyncio
    async def test_fans_out_to_every_enabled_target(self):
        raw = _make_item(tenant_id=str(uuid.uuid4()))
        targets = [_integration(), _integration()]
        scoped = _scoped_db(_device(), _reading(), targets)

        with patch("oss.jobs.pressure_forward.queue_len", return_value=1), \
             patch("oss.jobs.pressure_forward.queue_pop_to_processing",
                   return_value=raw.encode()), \
             patch("oss.jobs.pressure_forward.create_session", return_value=scoped), \
             patch("oss.jobs.pressure_forward.deliver_custom",
                   new_callable=AsyncMock, return_value="delivered") as mock_deliver:
            await task_drain_pressure_forward_queue()

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

        scoped = _scoped_db(_device(), _reading(), [_integration()])
        patches = _patched_redis(fake)
        with patches[0], patches[1], patches[2], patches[3], \
             patch("oss.jobs.pressure_forward.create_session", return_value=scoped), \
            patch("oss.jobs.pressure_forward._forward",
                   new_callable=AsyncMock, side_effect=RuntimeError("crash")):
            await task_drain_pressure_forward_queue()

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

        scoped = _scoped_db(_device(), _reading(), [_integration()])
        patches = _patched_redis(fake)
        with patches[0], patches[1], patches[2], patches[3], \
             patch("oss.jobs.pressure_forward.create_session", return_value=scoped), \
             patch("oss.jobs.pressure_forward._forward",
                   new_callable=AsyncMock, side_effect=RuntimeError("crash")):
            await task_drain_pressure_forward_queue()

        assert raw_item not in fake.lists.get(_PROCESSING, [])
        assert len(fake.lists.get(_DEAD, [])) == 1

    @pytest.mark.asyncio
    async def test_reclaim_sweep_recovers_a_stale_processing_item(self):
        fake = _FakeReliableRedis()
        stale_item = _make_item(device_id="dev-stale").encode()
        fake.lists[_PROCESSING] = [stale_item]
        fake.zsets[_PROCESSING_TS] = {
            stale_item: time.time() - _PROCESSING_VISIBILITY_TIMEOUT - 30
        }

        patches = _patched_redis(fake)
        with patches[0], patches[1], patches[2], patches[3]:
            await task_reclaim_stale_pressure_forwards()

        assert stale_item not in fake.lists.get(_PROCESSING, [])
        assert stale_item not in fake.zsets.get(_PROCESSING_TS, {})
        assert stale_item in fake.lists.get(_QUEUE, [])

    @pytest.mark.asyncio
    async def test_reclaim_sweep_does_not_touch_an_in_flight_item(self):
        fake = _FakeReliableRedis()
        fresh_item = _make_item(device_id="dev-fresh").encode()
        fake.lists[_PROCESSING] = [fresh_item]
        fake.zsets[_PROCESSING_TS] = {fresh_item: time.time()}

        patches = _patched_redis(fake)
        with patches[0], patches[1], patches[2], patches[3]:
            await task_reclaim_stale_pressure_forwards()

        assert fresh_item in fake.lists.get(_PROCESSING, [])
        assert fresh_item not in fake.lists.get(_QUEUE, [])
