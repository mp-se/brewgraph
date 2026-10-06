# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""brewfather_forward for pressure and temp: payloads, the shared 15 minute window and delivery
through the drain jobs. Gravity's own payload tests live in tests/test_gravity_forward.py."""
# pylint: disable=missing-function-docstring,protected-access
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oss.jobs import pressure_forward, temp_forward
from oss.jobs._forward_common import (BREWFATHER_FORWARD_MIN_INTERVAL_SECONDS,
                                      deliver_built_in)

MODULES = {"pressure": pressure_forward, "temp": temp_forward}


def _device(name="Fermenter 1"):
    device = MagicMock()
    device.id = uuid.uuid4()
    device.name = name
    device.chip_id = "ABC123"
    return device


def _reading(measurement, **overrides):
    values = {"temperature": 18.5, "battery": 3.98, "rssi": -62}
    if measurement == "pressure":
        values.update(pressure=12.5, temperature=4.0)
    values.update(overrides)
    reading = MagicMock()
    for key, value in values.items():
        setattr(reading, key, value)
    reading.batch_id = uuid.uuid4()
    reading.created_at = datetime(2026, 9, 1, tzinfo=UTC)
    return reading


def _integration(type_="brewfather_forward", url="http://8.8.8.8/hook"):
    row = MagicMock()
    row.id = uuid.uuid4()
    row.type = type_
    row.enabled = True
    row.config = {"url": url}
    row.consecutive_failures = 0
    return row


def test_pressure_payload_has_every_stored_value():
    payload = pressure_forward._brewfather_payload(_device(), _reading("pressure"))
    assert json.dumps(payload) == json.dumps({
        "name": "Fermenter 1", "pressure": 12.5, "pressure_unit": "KPA", "temp": 4.0,
        "temp_unit": "C", "battery": 3.98, "rssi": -62,
    })


def test_temp_payload_has_every_stored_value():
    payload = temp_forward._brewfather_payload(_device(), _reading("temp"))
    assert json.dumps(payload) == json.dumps({
        "name": "Fermenter 1", "temp": 18.5, "temp_unit": "C", "battery": 3.98, "rssi": -62,
    })


@pytest.mark.parametrize("measurement", ["pressure", "temp"])
def test_name_gets_no_sg_suffix(measurement):
    payload = MODULES[measurement]._brewfather_payload(
        _device("Pill"), _reading(measurement)
    )
    assert payload["name"] == "Pill"


def test_pressure_payload_leaves_out_missing_values():
    reading = _reading("pressure", temperature=None, battery=None, rssi=None)
    assert pressure_forward._brewfather_payload(_device(), reading) == {
        "name": "Fermenter 1", "pressure": 12.5, "pressure_unit": "KPA",
    }
    reading = _reading("pressure", pressure=None)
    payload = pressure_forward._brewfather_payload(_device(), reading)
    assert "pressure" not in payload and "pressure_unit" not in payload


def test_temp_payload_leaves_out_missing_values():
    reading = _reading("temp", temperature=None, battery=None, rssi=None)
    assert temp_forward._brewfather_payload(_device(), reading) == {"name": "Fermenter 1"}


@pytest.mark.parametrize("measurement", ["pressure", "temp"])
class TestRateLimit:
    """Brewfather ignores more than one request per 15 minutes per device."""

    @pytest.mark.asyncio
    async def test_first_send_is_delivered_and_sets_the_window(self, measurement):
        integration = _integration()
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True) as post, \
             patch("oss.jobs._forward_common.set_key_if_absent", return_value=True) as marker:
            outcome = await MODULES[measurement]._post_built_in(
                _device(), _reading(measurement), integration
            )
        assert outcome == "delivered"
        assert post.await_count == 1
        assert str(integration.id) in marker.call_args[0][0]
        assert marker.call_args[1]["ttl"] == BREWFATHER_FORWARD_MIN_INTERVAL_SECONDS == 900

    @pytest.mark.asyncio
    async def test_send_inside_the_window_is_skipped(self, measurement):
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock) as post, \
             patch("oss.jobs._forward_common.set_key_if_absent", return_value=False):
            outcome = await MODULES[measurement]._post_built_in(
                _device(), _reading(measurement), _integration()
            )
        assert outcome == "skipped"
        post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_failed_send_releases_the_window(self, measurement):
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=False), \
             patch("oss.jobs._forward_common.set_key_if_absent", return_value=True), \
             patch("oss.jobs._forward_common.delete_key") as release:
            outcome = await MODULES[measurement]._post_built_in(
                _device(), _reading(measurement), _integration()
            )
        assert outcome == "failed"
        release.assert_called_once()

    @pytest.mark.asyncio
    async def test_blocked_destination_is_not_sent(self, measurement):
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock) as post:
            outcome = await MODULES[measurement]._post_built_in(
                _device(), _reading(measurement), _integration(url="http://127.0.0.1/x")
            )
        assert outcome == "blocked"
        post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_posts_the_brewfather_payload(self, measurement):
        device, reading = _device(), _reading(measurement)
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True) as post, \
             patch("oss.jobs._forward_common.set_key_if_absent", return_value=True):
            await MODULES[measurement]._post_built_in(device, reading, _integration())
        assert post.call_args[0][1] == MODULES[measurement]._brewfather_payload(device, reading)

    @pytest.mark.asyncio
    async def test_forward_routes_by_type_and_a_skip_is_not_a_failure(self, measurement):
        module = MODULES[measurement]
        brewfather, custom = _integration(), _integration("custom_forward")
        brewfather.consecutive_failures = 2
        with patch.object(module, "_post_built_in", new_callable=AsyncMock,
                          return_value="skipped") as built_in, \
             patch.object(module, "deliver_custom", new_callable=AsyncMock,
                          return_value="delivered") as deliver:
            ok = await module._forward(
                MagicMock(), _device(), _reading(measurement), [brewfather, custom]
            )
        assert ok is True
        assert built_in.await_count == 1 and deliver.await_count == 1
        assert brewfather.consecutive_failures == 2

    @pytest.mark.asyncio
    async def test_drain_job_delivers_brewfather_targets(self, measurement):
        module = MODULES[measurement]
        raw = json.dumps({
            "device_id": "00000000-0000-0000-0000-000000000001",
            "tenant_id": str(uuid.uuid4()),
            "enqueued_at": datetime.now(UTC).isoformat(), "attempts": 0,
        })
        session = MagicMock()
        session.get.return_value = _device()
        session.execute.return_value.scalar_one_or_none.return_value = _reading(measurement)
        session.scalars.return_value.all.return_value = [_integration()]
        scoped = MagicMock(return_value=session, remove=MagicMock())
        drain = getattr(module, f"task_drain_{measurement}_forward_queue")
        with patch.object(module, "queue_len", return_value=1), \
             patch.object(module, "queue_pop_to_processing", return_value=raw.encode()), \
             patch.object(module, "create_session", return_value=scoped), \
             patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True) as post, \
             patch("oss.jobs._forward_common.set_key_if_absent", return_value=True):
            await drain()
        assert post.await_count == 1
        assert post.call_args[0][1]["name"] == "Fermenter 1"


@pytest.mark.asyncio
async def test_ispindel_is_never_rate_limited():
    with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
               return_value=True), \
         patch("oss.jobs._forward_common.set_key_if_absent", return_value=False) as marker:
        outcome = await deliver_built_in(
            _integration("ispindel_forward"), {"a": 1}, uuid.uuid4(), "test"
        )
    assert outcome == "delivered"
    marker.assert_not_called()
