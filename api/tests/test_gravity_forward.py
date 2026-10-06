# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/jobs/gravity_forward.py — the shared Redis-queue forwarding job."""
# pylint: disable=missing-function-docstring
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oss.jobs.gravity_forward import (
    ISPINDEL_FORWARD_INTERVAL_SECONDS,
    _DEAD,
    _PROCESSING,
    _PROCESSING_TS,
    _PROCESSING_VISIBILITY_TIMEOUT,
    _QUEUE,
    _brewfather_payload,
    _forward,
    _ispindel_payload,
    _post_built_in,
    _post_custom,
    _render_template,
    enqueue_forward,
    task_drain_gravity_forward_queue,
    task_reclaim_stale_gravity_forwards,
)

_MAX_AGE_SECONDS = 86_400
_MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# Pure payload/template builders
# ---------------------------------------------------------------------------

def _reading(**kwargs):
    r = MagicMock()
    r.device_id = uuid.uuid4()
    r.batch_id = kwargs.get("batch_id", uuid.uuid4())
    r.angle = kwargs.get("angle", 35.0)
    r.temperature = kwargs.get("temperature", 20.0)
    r.gravity = kwargs.get("gravity", 1.050)
    r.velocity = kwargs.get("velocity", 0.5)
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


class TestIspindelPayload:
    """Tests for _ispindel_payload: the original iSpindel format."""

    def test_exact_payload_with_every_value(self):
        d = _device(name="MyDevice", chip_id="A1B2C3")
        r = _reading(gravity=1.050, angle=35.0, temperature=20.0, battery=3.8, rssi=-60.0)
        assert _ispindel_payload(d, r) == {
            "name": "MyDevice",
            "ID": "A1B2C3",
            "angle": 35.0,
            "temperature": 20.0,
            "temp_units": "C",
            "battery": 3.8,
            "gravity": 1.050,
            "interval": 900,
            "RSSI": -60.0,
        }

    def test_id_is_the_chip_id_not_the_internal_uuid(self):
        d = _device(chip_id="A1B2C3")
        assert _ispindel_payload(d, _reading())["ID"] == "A1B2C3"
        assert str(d.id) not in json.dumps(_ispindel_payload(d, _reading()))

    def test_never_sends_a_token(self):
        assert "token" not in _ispindel_payload(_device(), _reading())

    def test_interval_is_the_documented_constant(self):
        assert ISPINDEL_FORWARD_INTERVAL_SECONDS == 900
        assert _ispindel_payload(_device(), _reading())["interval"] == 900

    def test_missing_values_are_left_out_not_zeroed(self):
        r = _reading(angle=None, battery=None, rssi=None)
        p = _ispindel_payload(_device(), r)
        assert "angle" not in p and "battery" not in p and "RSSI" not in p
        assert set(p) == {"name", "ID", "temperature", "temp_units", "gravity", "interval"}

    def test_missing_temperature_is_left_out(self):
        assert "temperature" not in _ispindel_payload(_device(), _reading(temperature=None))

    def test_a_real_zero_is_kept(self):
        p = _ispindel_payload(_device(), _reading(angle=0.0, rssi=0))
        assert p["angle"] == 0.0 and p["RSSI"] == 0


class TestBrewfatherPayload:
    """Tests for _brewfather_payload: Brewfather's custom stream format."""

    def test_exact_payload_with_every_value(self):
        d = _device(name="MyDevice")
        r = _reading(gravity=1.048, temperature=19.5, battery=3.9, angle=40.0, rssi=-55.0)
        assert _brewfather_payload(d, r) == {
            "name": "MyDevice[SG]",
            "temp": 19.5,
            "temp_unit": "C",
            "gravity": 1.048,
            "gravity_unit": "G",
            "battery": 3.9,
            "angle": 40.0,
            "rssi": -55.0,
        }

    def test_name_gets_the_sg_suffix_once(self):
        assert _brewfather_payload(_device(name="MyDevice"), _reading())["name"] == "MyDevice[SG]"
        assert _brewfather_payload(_device(name="Pill[SG]"), _reading())["name"] == "Pill[SG]"
        assert _brewfather_payload(_device(name="[SG] Pill"), _reading())["name"] == "[SG] Pill"

    def test_a_device_without_a_name_is_still_marked_sg(self):
        assert _brewfather_payload(_device(name=None), _reading())["name"] == "[SG]"

    def test_missing_battery_angle_rssi_are_left_out(self):
        p = _brewfather_payload(_device(), _reading(battery=None, angle=None, rssi=None))
        assert set(p) == {"name", "temp", "temp_unit", "gravity", "gravity_unit"}

    def test_missing_temperature_is_left_out(self):
        assert "temp" not in _brewfather_payload(_device(), _reading(temperature=None))


class TestRenderTemplate:
    """Tests for _render_template's ${key} substitution."""

    def test_substitutes_every_documented_token(self):
        d = _device(name="Kitchen", chip_id="A1B2")
        r = _reading(gravity=1.052, temperature=19.0, angle=40.0, velocity=0.3,
                     battery=3.9, rssi=-55.0)
        template = (
            "g=${gravity} t=${temperature} a=${angle} v=${velocity} b=${battery} "
            "rssi=${rssi} name=${deviceName} id=${deviceId} chip=${chipId} "
            "batch=${batchId} ts=${timestamp}"
        )
        rendered = _render_template(template, d, r)
        assert "${" not in rendered  # every token consumed
        assert "g=1.052" in rendered
        assert "name=Kitchen" in rendered
        assert "chip=A1B2" in rendered
        assert str(d.id) in rendered
        assert str(r.batch_id) in rendered

    def test_missing_batch_id_renders_empty_string(self):
        d, r = _device(), _reading(batch_id=None)
        rendered = _render_template("batch=${batchId}", d, r)
        assert rendered == "batch="

    def test_missing_numbers_render_null_and_missing_text_empty(self):
        d = _device(name=None, chip_id=None)
        r = _reading(temperature=None, angle=None, velocity=None, battery=None,
                     rssi=None, batch_id=None)
        rendered = _render_template(
            '{"t":${temperature},"a":${angle},"v":${velocity},"b":${battery},'
            '"r":${rssi},"n":"${deviceName}","c":"${chipId}","batch":"${batchId}"}',
            d, r,
        )
        assert json.loads(rendered) == {
            "t": None, "a": None, "v": None, "b": None, "r": None,
            "n": "", "c": "", "batch": "",
        }

    def test_present_values_render_unchanged_including_zero(self):
        r = _reading(gravity=1.042, temperature=0.0, angle=45.2, rssi=-62)
        rendered = _render_template("${gravity}|${temperature}|${angle}|${rssi}", _device(), r)
        assert rendered == "1.042|0.0|45.2|-62"

    def test_unrelated_text_is_untouched(self):
        rendered = _render_template(
            "api_key=XXXX&field1=${gravity}", _device(), _reading(gravity=1.05)
        )
        assert rendered == "api_key=XXXX&field1=1.05"

class TestEnqueueForward:
    """Tests for enqueue_forward's queued payload shape."""

    def test_pushes_json_with_device_and_tenant(self):
        with patch("oss.jobs.gravity_forward.set_key_if_absent", return_value=True), \
             patch("oss.jobs.gravity_forward.queue_push") as mock_push:
            enqueue_forward("dev-1", "tenant-1")
            queue_name, raw = mock_push.call_args[0]
            assert queue_name == _QUEUE
            item = json.loads(raw)
            assert item["device_id"] == "dev-1"
            assert item["tenant_id"] == "tenant-1"
            assert item["attempts"] == 0
            assert "enqueued_at" in item

    def test_coalesces_when_a_job_is_already_pending(self):
        with patch("oss.jobs.gravity_forward.set_key_if_absent", return_value=False), \
             patch("oss.jobs.gravity_forward.queue_push") as mock_push:
            enqueue_forward("dev-1", "tenant-1")
        mock_push.assert_not_called()

    def test_logs_warning_when_queue_push_fails(self, caplog):
        with patch("oss.jobs.gravity_forward.set_key_if_absent", return_value=True), \
             patch("oss.jobs.gravity_forward.queue_push", return_value=False), \
             patch("oss.jobs.gravity_forward.delete_key") as mock_delete, \
             caplog.at_level("WARNING"):
            enqueue_forward("dev-1", "tenant-1")
        assert any("dev-1" in record.message for record in caplog.records)
        mock_delete.assert_called_once_with("gravity_forward_pending:dev-1")


# ---------------------------------------------------------------------------
# task_drain_gravity_forward_queue
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


def _integration(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    itype="ispindel_forward", url="http://example.com/hook", enabled=True,
    method="POST", template=None, headers=None,
):
    row = MagicMock()
    row.type = itype
    row.enabled = enabled
    row.config = {"url": url, "method": method, "headers": headers or {}, "template": template}
    row.consecutive_failures = 0
    return row


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
    """Tests for task_drain_gravity_forward_queue's per-item processing."""

    @pytest.mark.asyncio
    async def test_empty_queue_returns_early(self):
        with patch("oss.jobs.gravity_forward.queue_len", return_value=0):
            await task_drain_gravity_forward_queue()  # must not raise

    @pytest.mark.asyncio
    async def test_skips_malformed_json(self):
        with patch("oss.jobs.gravity_forward.queue_len", return_value=1), \
             patch("oss.jobs.gravity_forward.queue_pop_to_processing", return_value=b"not-json"), \
             patch("oss.jobs.gravity_forward.create_session") as mock_sess:
            mock_sess.return_value = MagicMock(remove=MagicMock())
            await task_drain_gravity_forward_queue()  # must not raise

    @pytest.mark.asyncio
    async def test_drops_stale_item(self):
        old_item = _make_item(age_seconds=_MAX_AGE_SECONDS + 1)
        with patch("oss.jobs.gravity_forward.queue_len", return_value=1), \
             patch("oss.jobs.gravity_forward.queue_pop_to_processing",
                   return_value=old_item.encode()), \
             patch("oss.jobs.gravity_forward.create_session") as mock_sess:
            mock_sess.return_value = MagicMock(remove=MagicMock())
            await task_drain_gravity_forward_queue()  # must not raise

    @pytest.mark.asyncio
    async def test_skips_unknown_device(self):
        raw = _make_item()
        session = MagicMock()
        session.get.return_value = None
        scoped = MagicMock(return_value=session, remove=MagicMock())
        with patch("oss.jobs.gravity_forward.queue_len", return_value=1), \
             patch("oss.jobs.gravity_forward.queue_pop_to_processing", return_value=raw.encode()), \
             patch("oss.jobs.gravity_forward.create_session", return_value=scoped):
            await task_drain_gravity_forward_queue()  # must not raise

    @pytest.mark.asyncio
    async def test_no_configured_targets_skips_item(self):
        """A device on an account with zero enabled Integration rows is a no-op,
        not an error."""
        raw = _make_item(tenant_id=str(uuid.uuid4()))
        scoped = _scoped_db(_device(), _reading(), [])
        with patch("oss.jobs.gravity_forward.queue_len", return_value=1), \
             patch("oss.jobs.gravity_forward.queue_pop_to_processing", return_value=raw.encode()), \
             patch("oss.jobs.gravity_forward.create_session", return_value=scoped):
            await task_drain_gravity_forward_queue()  # must not raise

    @pytest.mark.asyncio
    async def test_fans_out_to_every_enabled_target(self):
        """One queued device item is delivered to every enabled Integration row
        for the account — an integration is account-level, not per-device."""
        raw = _make_item(tenant_id=str(uuid.uuid4()))
        targets = [
            _integration("ispindel_forward", "http://ispindel.example/x"),
            _integration("brewfather_forward", "http://brewfather.example/y"),
            _integration("custom_forward", "http://custom.example/z", template="g=${gravity}"),
        ]
        scoped = _scoped_db(_device(), _reading(), targets)

        with patch("oss.jobs.gravity_forward.queue_len", return_value=1), \
             patch("oss.jobs.gravity_forward.queue_pop_to_processing", return_value=raw.encode()), \
             patch("oss.jobs.gravity_forward.create_session", return_value=scoped), \
             patch("oss.jobs.gravity_forward._post_built_in",
                   new_callable=AsyncMock, return_value=True) as post_built_in, \
             patch("oss.jobs.gravity_forward._post_custom",
                   new_callable=AsyncMock, return_value=True) as post_custom:
            await task_drain_gravity_forward_queue()

        assert post_built_in.await_count == 2  # ispindel + brewfather
        assert post_custom.await_count == 1

    @pytest.mark.asyncio
    async def test_disabled_target_is_not_attempted(self):
        """A target with enabled=False is excluded by the DB query, not just
        skipped in Python -- simulated here by simply not returning it."""
        raw = _make_item(tenant_id=str(uuid.uuid4()))
        # Only the enabled target is returned, mirroring the real
        # `Integration.enabled.is_(True)` filter.
        targets = [_integration("ispindel_forward")]
        scoped = _scoped_db(_device(), _reading(), targets)

        with patch("oss.jobs.gravity_forward.queue_len", return_value=1), \
             patch("oss.jobs.gravity_forward.queue_pop_to_processing", return_value=raw.encode()), \
             patch("oss.jobs.gravity_forward.create_session", return_value=scoped), \
             patch("oss.jobs.gravity_forward._post_built_in",
                   new_callable=AsyncMock, return_value=True) as post_built_in:
            await task_drain_gravity_forward_queue()

        assert post_built_in.await_count == 1


class TestPostBuiltIn:
    """Tests for _post_built_in's SSRF guard and payload dispatch."""

    @pytest.mark.asyncio
    async def test_blocked_url_returns_blocked_without_retry(self):
        """A loopback/link-local URL is 'blocked', distinct from 'delivered' --
        both mean don't retry the item, but only 'delivered' resets the
        per-target consecutive_failures counter."""
        integration = _integration("ispindel_forward", "http://127.0.0.1/hook")
        result = await _post_built_in(_device(), _reading(), integration)
        assert result == "blocked"

    @pytest.mark.asyncio
    async def test_dispatches_ispindel_payload_shape(self):
        integration = _integration("ispindel_forward", "http://8.8.8.8/hook")
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True) as mock_post:
            await _post_built_in(_device(name="Dev"), _reading(gravity=1.05), integration)
        payload = mock_post.call_args[0][1]
        assert "ID" in payload and "RSSI" in payload  # ispindel shape

    @pytest.mark.asyncio
    async def test_dispatches_brewfather_payload_shape(self):
        integration = _integration("brewfather_forward", "http://8.8.8.8/hook")
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True) as mock_post:
            await _post_built_in(_device(name="Dev"), _reading(), integration)
        payload = mock_post.call_args[0][1]
        assert "gravity_unit" in payload  # brewfather shape


class TestBrewfatherRateLimit:
    """Brewfather ignores a device that logs more than once per 15 minutes, so
    brewfather_forward sends at most one request per (integration, device) in
    that window. A skipped delivery is neither a success nor a failure."""

    @pytest.mark.asyncio
    async def test_first_delivery_is_sent_and_sets_the_window(self):
        integration = _integration("brewfather_forward", "http://8.8.8.8/hook")
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True) as mock_post, \
             patch("oss.jobs._forward_common.set_key_if_absent",
                   return_value=True) as mock_set:
            result = await _post_built_in(_device(), _reading(), integration)
        assert result == "delivered"
        assert mock_post.await_count == 1
        key = mock_set.call_args[0][0]
        assert str(integration.id) in key
        assert mock_set.call_args[1]["ttl"] == 900

    @pytest.mark.asyncio
    async def test_delivery_inside_the_window_is_skipped(self):
        integration = _integration("brewfather_forward", "http://8.8.8.8/hook")
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock) as mock_post, \
             patch("oss.jobs._forward_common.set_key_if_absent", return_value=False):
            result = await _post_built_in(_device(), _reading(), integration)
        assert result == "skipped"
        mock_post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_failed_request_releases_the_window_for_the_retry(self):
        integration = _integration("brewfather_forward", "http://8.8.8.8/hook")
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=False), \
             patch("oss.jobs._forward_common.set_key_if_absent", return_value=True), \
             patch("oss.jobs._forward_common.delete_key") as mock_delete:
            result = await _post_built_in(_device(), _reading(), integration)
        assert result == "failed"
        mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_ispindel_is_not_rate_limited(self):
        integration = _integration("ispindel_forward", "http://8.8.8.8/hook")
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True) as mock_post, \
             patch("oss.jobs._forward_common.set_key_if_absent",
                   return_value=False) as mock_set:
            result = await _post_built_in(_device(), _reading(), integration)
        assert result == "delivered"
        assert mock_post.await_count == 1
        mock_set.assert_not_called()

    @pytest.mark.asyncio
    async def test_skipped_does_not_touch_the_failure_counter(self):
        integration = _integration("brewfather_forward")
        integration.consecutive_failures = 2
        with patch("oss.jobs.gravity_forward._post_built_in", new_callable=AsyncMock,
                   return_value="skipped"):
            ok = await _forward(_scoped_db(_device(), _reading(), []),
                                _device(), _reading(), [integration])
        assert ok is True
        assert integration.consecutive_failures == 2


class TestPostCustom:
    """Tests for _post_custom — now a thin wrapper that builds the gravity ${key}
    values dict and delegates dispatch to the shared oss.jobs._forward_common.
    deliver_custom (see tests/test_forward_common.py for its own HTTP GET/POST
    dispatch and template-rendering coverage in isolation)."""

    @pytest.mark.asyncio
    async def test_delegates_to_shared_deliver_custom_with_gravity_values(self):
        integration = _integration(
            "custom_forward", "http://8.8.8.8/hook", method="POST",
            template='{"g": ${gravity}}',
        )
        device = _device(name="Dev", chip_id="A1B2")
        reading = _reading(gravity=1.05)
        with patch("oss.jobs.gravity_forward.deliver_custom", new_callable=AsyncMock,
                   return_value="delivered") as mock_deliver:
            result = await _post_custom(device, reading, integration)

        assert result == "delivered"
        args = mock_deliver.call_args[0]
        assert args[0] == integration.config
        assert args[1]["gravity"] == 1.05
        assert args[1]["deviceId"] == str(device.id)
        assert args[2] == device.id
        assert args[3] == "gravity_forward custom_forward"

    @pytest.mark.asyncio
    async def test_returns_deliver_custom_result(self):
        integration = _integration("custom_forward", "http://8.8.8.8/hook",
                                   template="x=${gravity}")
        with patch("oss.jobs.gravity_forward.deliver_custom", new_callable=AsyncMock,
                   return_value="failed"):
            assert await _post_custom(_device(), _reading(), integration) == "failed"


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
    """Patch core.queue's and core.cache's pool/client so gravity_forward's
    already-imported queue primitives (and the delete_key/set_key_if_absent
    calls it makes for the pending-marker) run for real against `fake`,
    instead of mocking the primitives themselves."""
    return (
        patch("core.queue.pool", MagicMock()),
        patch("core.queue.redis.Redis", return_value=fake),
        patch("core.cache.pool", MagicMock()),
        patch("core.cache.redis.Redis", return_value=fake),
    )


class TestReliableQueueMechanics:
    """End-to-end coverage of the pop-into-processing / ack / reclaim cycle."""

    @pytest.mark.asyncio
    async def test_crash_mid_forward_leaves_item_recoverable_when_retry_push_fails(self):
        """_forward raising mid-processing is handled by _handle_failure; if the
        retry-push itself also fails, the item is NOT acked -- it stays in
        gravity_forward_processing, recoverable by the reclaim sweep."""
        fake = _FakeReliableRedis()
        raw_item = _make_item(attempts=0).encode()
        fake.lpush(_QUEUE, raw_item)

        scoped = _scoped_db(_device(), _reading(), [_integration()])
        patches = _patched_redis(fake)
        with patches[0], patches[1], patches[2], patches[3], \
             patch("oss.jobs.gravity_forward.create_session", return_value=scoped), \
             patch("oss.jobs.gravity_forward._forward",
                   new_callable=AsyncMock, side_effect=RuntimeError("crash")), \
             patch("oss.jobs.gravity_forward.queue_push", return_value=False):
            await task_drain_gravity_forward_queue()

        assert raw_item in fake.lists.get(_PROCESSING, [])
        assert raw_item in fake.zsets.get(_PROCESSING_TS, {})
        assert raw_item not in fake.lists.get(_QUEUE, [])

    @pytest.mark.asyncio
    async def test_crash_mid_forward_acks_once_retry_push_lands(self):
        """Same crash, but the retry-push succeeds: acked out of processing and
        reappears on the main queue with attempts incremented."""
        fake = _FakeReliableRedis()
        raw_item = _make_item(attempts=0).encode()
        fake.lpush(_QUEUE, raw_item)

        scoped = _scoped_db(_device(), _reading(), [_integration()])
        patches = _patched_redis(fake)
        with patches[0], patches[1], patches[2], patches[3], \
             patch("oss.jobs.gravity_forward.create_session", return_value=scoped), \
            patch("oss.jobs.gravity_forward._forward",
                   new_callable=AsyncMock, side_effect=RuntimeError("crash")):
            await task_drain_gravity_forward_queue()

        scoped.return_value.rollback.assert_called_once_with()
        assert raw_item not in fake.lists.get(_PROCESSING, [])
        assert raw_item not in fake.zsets.get(_PROCESSING_TS, {})
        requeued = [json.loads(v) for v in fake.lists.get(_QUEUE, [])]
        assert any(r["attempts"] == 1 for r in requeued)

    @pytest.mark.asyncio
    async def test_dead_letters_after_max_retries(self):
        """An item at its final attempt is pushed to the dead-letter list,
        not requeued."""
        fake = _FakeReliableRedis()
        raw_item = _make_item(attempts=_MAX_RETRIES - 1).encode()
        fake.lpush(_QUEUE, raw_item)

        scoped = _scoped_db(_device(), _reading(), [_integration()])
        patches = _patched_redis(fake)
        with patches[0], patches[1], patches[2], patches[3], \
             patch("oss.jobs.gravity_forward.create_session", return_value=scoped), \
             patch("oss.jobs.gravity_forward._forward",
                   new_callable=AsyncMock, side_effect=RuntimeError("crash")):
            await task_drain_gravity_forward_queue()

        assert raw_item not in fake.lists.get(_PROCESSING, [])
        assert len(fake.lists.get(_DEAD, [])) == 1
        assert not any(
            json.loads(v)["attempts"] < _MAX_RETRIES for v in fake.lists.get(_QUEUE, [])
        )

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
            await task_reclaim_stale_gravity_forwards()

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
            await task_reclaim_stale_gravity_forwards()

        assert fresh_item in fake.lists.get(_PROCESSING, [])
        assert fresh_item in fake.zsets.get(_PROCESSING_TS, {})
        assert fresh_item not in fake.lists.get(_QUEUE, [])
