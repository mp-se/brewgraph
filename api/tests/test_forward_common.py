# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/jobs/_forward_common.py — the measurement-agnostic template
substitution and HTTP POST/GET dispatch shared by all four forwarding jobs
(gravity/pressure/pour/temp)."""
# pylint: disable=missing-function-docstring
import json
import uuid as uuid_module
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import oss.jobs._forward_common as forward_common
from core.log import LogLevel
from oss.jobs._forward_common import (apply_delivery_outcome, as_uuid, deliver_custom,
                                      get_http_client, http_get, http_post,
                                      close_http_client, get_pinned_https_client,
                                      recover_forwarding_error,
                                      render_template)


# ---------------------------------------------------------------------------
# as_uuid
# ---------------------------------------------------------------------------

class TestAsUuid:
    """as_uuid coerces a queue item's string ids to real uuid.UUID objects --
    required for SQLAlchemy's Uuid(as_uuid=True) columns to bind correctly on
    SQLite, whose bind processor calls .hex on the value and fails with
    'str' object has no attribute 'hex' if given a plain string."""

    def test_string_is_coerced_to_uuid(self):
        raw = "00000000-0000-0000-0000-000000000001"
        result = as_uuid(raw)
        assert isinstance(result, uuid_module.UUID)
        assert result == uuid_module.UUID(raw)

    def test_uuid_object_passes_through_unchanged(self):
        original = uuid_module.uuid4()
        assert as_uuid(original) is original

    def test_invalid_string_raises_value_error(self):
        with pytest.raises(ValueError):
            as_uuid("not-a-uuid")


# ---------------------------------------------------------------------------
# render_template
# ---------------------------------------------------------------------------

class TestRenderTemplate:
    """Tests for render_template's ${key} substitution over a plain values dict."""

    def test_missing_number_renders_null_for_every_numeric_token(self):
        for token in ("gravity", "temperature", "angle", "velocity", "battery", "rssi",
                      "pressure", "pourAmount", "volumeRemaining"):
            assert render_template("${%s}" % token, {token: None}) == "null", token

    def test_missing_text_renders_empty_string(self):
        for token in ("tempType", "deviceName", "batchId", "timestamp", "tapName"):
            assert render_template("[${%s}]" % token, {token: None}) == "[]", token

    def test_json_template_with_missing_values_stays_valid_json(self):
        rendered = render_template(
            '{"p":${pressure},"n":"${deviceName}"}', {"pressure": None, "deviceName": None}
        )
        assert json.loads(rendered) == {"p": None, "n": ""}

    def test_present_numbers_render_as_before_including_zero(self):
        assert render_template("${pressure}|${rssi}", {"pressure": 0.0, "rssi": 0}) == "0.0|0"
        assert render_template("${gravity}", {"gravity": 1.042}) == "1.042"

    def test_substitutes_every_key_present(self):
        rendered = render_template(
            "g=${gravity} name=${deviceName}", {"gravity": 1.05, "deviceName": "Kitchen"}
        )
        assert rendered == "g=1.05 name=Kitchen"

    def test_unrelated_text_is_untouched(self):
        rendered = render_template("api_key=XXXX&field1=${gravity}", {"gravity": 1.05})
        assert rendered == "api_key=XXXX&field1=1.05"

    def test_key_not_in_values_left_unsubstituted(self):
        rendered = render_template("x=${unknown}", {"gravity": 1.05})
        assert rendered == "x=${unknown}"

    def test_tap_keyed_values_work_the_same_as_device_keyed(self):
        """Pour's tap/vessel-shaped values dict substitutes identically to a
        device-shaped one -- render_template has no notion of subject shape."""
        rendered = render_template(
            "amount=${pourAmount} tap=${tapName}",
            {"pourAmount": 0.33, "tapName": "Tap 1"},
        )
        assert rendered == "amount=0.33 tap=Tap 1"


# ---------------------------------------------------------------------------
# get_http_client / http_post / http_get
# ---------------------------------------------------------------------------

def _client_mock(status_code=200, side_effect=None):
    resp = MagicMock()
    resp.status_code = status_code
    client = AsyncMock()
    if side_effect:
        client.post = AsyncMock(side_effect=side_effect)
        client.get = AsyncMock(side_effect=side_effect)
    else:
        client.post = AsyncMock(return_value=resp)
        client.get = AsyncMock(return_value=resp)
    return client


def test_get_http_client_returns_same_instance_across_calls():
    """get_http_client is a lazily-created module-level singleton."""
    with patch("oss.jobs._forward_common._http_client_box", []):
        first = get_http_client()
        second = get_http_client()
    assert first is second


def test_pinned_https_client_disables_idle_connection_reuse():
    """A later hostname at the same pinned IP must get a fresh TLS handshake."""
    with patch("oss.jobs._forward_common._pinned_https_client_box", []), \
         patch("oss.jobs._forward_common.httpx.AsyncClient") as client_class:
        get_pinned_https_client()
    limits = client_class.call_args.kwargs["limits"]
    assert limits.max_keepalive_connections == 0


class TestHttpPost:
    """Tests for the http_post helper."""

    @pytest.mark.asyncio
    async def test_success_returns_true(self):
        with patch("oss.jobs._forward_common.get_http_client", return_value=_client_mock(200)):
            assert await http_post("http://192.168.1.5/", {"a": 1}, "subj1", "label") is True

    @pytest.mark.asyncio
    async def test_non_200_returns_false(self):
        with patch("oss.jobs._forward_common.get_http_client", return_value=_client_mock(500)):
            assert await http_post("http://192.168.1.5/", {"a": 1}, "subj1", "label") is False

    @pytest.mark.asyncio
    async def test_read_timeout_returns_false(self):
        client = _client_mock(side_effect=httpx.ReadTimeout(""))
        with patch("oss.jobs._forward_common.get_http_client", return_value=client):
            assert await http_post("http://192.168.1.5/", {}, "subj1", "label") is False

    @pytest.mark.asyncio
    async def test_connect_error_returns_false(self):
        client = _client_mock(side_effect=httpx.ConnectError(""))
        with patch("oss.jobs._forward_common.get_http_client", return_value=client):
            assert await http_post("http://192.168.1.5/", {}, "subj1", "label") is False

    @pytest.mark.asyncio
    async def test_none_payload_sends_raw_text(self):
        """custom_forward's non-JSON template falls back to a raw text body."""
        client = _client_mock(200)
        with patch("oss.jobs._forward_common.get_http_client", return_value=client):
            ok = await http_post("http://192.168.1.5/", None, "subj1", "label", raw="plain text")
        assert ok is True
        _, kwargs = client.post.call_args
        assert kwargs["content"] == "plain text"

    @pytest.mark.asyncio
    async def test_json_payload_uses_json_content_type_by_default(self):
        client = _client_mock(200)
        with patch("oss.jobs._forward_common.get_http_client", return_value=client):
            await http_post("http://192.168.1.5/", {"a": 1}, "subj1", "label")
        _, kwargs = client.post.call_args
        assert kwargs["headers"]["Content-Type"] == "application/json"


class TestHttpGet:
    """Tests for the http_get helper (custom_forward with method=GET)."""

    @pytest.mark.asyncio
    async def test_appends_query_params(self):
        client = _client_mock(200)
        with patch("oss.jobs._forward_common.get_pinned_https_client", return_value=client), \
             patch("oss.jobs._forward_common._pinned_request", return_value=(
                 "https://203.0.113.1/update", {"Host": "api.thingspeak.com"},
                 {"sni_hostname": "api.thingspeak.com"},
             )):
            ok = await http_get("https://api.thingspeak.com/update", "api_key=X&field1=1.05",
                                {}, "subj1", "label")
        assert ok is True
        called_url = client.get.call_args[0][0]
        assert called_url == "https://203.0.113.1/update"
        assert client.get.call_args.kwargs["headers"]["Host"] == "api.thingspeak.com"

    @pytest.mark.asyncio
    async def test_existing_query_string_uses_ampersand(self):
        client = _client_mock(200)
        with patch("oss.jobs._forward_common.get_pinned_https_client", return_value=client), \
             patch("oss.jobs._forward_common._pinned_request", return_value=(
                 "https://203.0.113.1/hook?a=1&b=2", {"Host": "x.example"},
                 {"sni_hostname": "x.example"},
             )):
            await http_get("https://x.example/hook?a=1", "b=2", {}, "subj1", "label")
        called_url = client.get.call_args[0][0]
        assert "?a=1&b=2" in called_url

    @pytest.mark.asyncio
    async def test_read_timeout_returns_false(self):
        client = _client_mock(side_effect=httpx.ReadTimeout(""))
        with patch("oss.jobs._forward_common.get_http_client", return_value=client):
            assert await http_get("http://192.168.1.5/", "a=1", {}, "subj1", "label") is False


# ---------------------------------------------------------------------------
# deliver_custom
# ---------------------------------------------------------------------------

class TestDeliverCustom:
    """Tests for deliver_custom's SSRF guard, template rendering, and
    GET/POST dispatch -- the shared custom_forward path all four forwarding
    jobs use."""

    @pytest.mark.asyncio
    async def test_blocked_url_returns_blocked_without_retry(self):
        """A loopback/link-local URL is 'blocked', distinct from 'delivered' --
        both count as 'don't retry the item', but only 'delivered' resets the
        per-target consecutive_failures counter (see apply_delivery_outcome)."""
        config = {"url": "http://127.0.0.1/hook", "template": "x=${gravity}"}
        result = await deliver_custom(config, {"gravity": 1.05}, "subj1", "label")
        assert result == "blocked"

    @pytest.mark.asyncio
    async def test_post_with_valid_json_template(self):
        config = {"url": "http://8.8.8.8/hook", "method": "POST", "template": '{"g": ${gravity}}'}
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True) as mock_post:
            await deliver_custom(config, {"gravity": 1.05}, "subj1", "label")
        payload = mock_post.call_args[0][1]
        assert payload == {"g": 1.05}

    @pytest.mark.asyncio
    async def test_post_with_non_json_template_sends_raw(self):
        config = {"url": "http://8.8.8.8/hook", "method": "POST", "template": "gravity=${gravity}"}
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True) as mock_post:
            await deliver_custom(config, {"gravity": 1.05}, "subj1", "label")
        args, kwargs = mock_post.call_args
        assert args[1] is None  # not valid JSON
        assert kwargs["raw"] == "gravity=1.05"

    @pytest.mark.asyncio
    async def test_get_method_dispatches_to_http_get(self):
        config = {"url": "http://8.8.8.8/hook", "method": "GET", "template": "field1=${gravity}"}
        with patch("oss.jobs._forward_common.http_get", new_callable=AsyncMock,
                   return_value=True) as mock_get:
            await deliver_custom(config, {"gravity": 1.05}, "subj1", "label")
        mock_get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_default_method_is_post(self):
        config = {"url": "http://8.8.8.8/hook", "template": "x=${gravity}"}
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True) as mock_post:
            await deliver_custom(config, {"gravity": 1.05}, "subj1", "label")
        mock_post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_headers_passed_through(self):
        config = {
            "url": "http://8.8.8.8/hook", "method": "POST", "template": "x=${gravity}",
            "headers": {"X-Api-Key": "secret"},
        }
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True) as mock_post:
            await deliver_custom(config, {"gravity": 1.05}, "subj1", "label")
        _, kwargs = mock_post.call_args
        assert kwargs["headers"] == {"X-Api-Key": "secret"}

    @pytest.mark.asyncio
    async def test_works_with_a_tap_keyed_values_dict(self):
        """Pour's values dict carries no device tokens at all -- deliver_custom
        has no notion of the subject's shape, only the values dict's keys."""
        config = {
            "url": "http://8.8.8.8/hook", "method": "POST",
            "template": '{"tap": "${tapName}", "amount": ${pourAmount}}',
        }
        values = {"tapName": "Tap 1", "pourAmount": 0.33}
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True) as mock_post:
            await deliver_custom(config, values, "tap-1", "pour_forward custom_forward")
        payload = mock_post.call_args[0][1]
        assert payload == {"tap": "Tap 1", "amount": 0.33}

    @pytest.mark.asyncio
    async def test_successful_post_returns_delivered(self):
        config = {"url": "http://8.8.8.8/hook", "method": "POST", "template": "x=${gravity}"}
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=True):
            result = await deliver_custom(config, {"gravity": 1.05}, "subj1", "label")
        assert result == "delivered"

    @pytest.mark.asyncio
    async def test_failed_post_returns_failed(self):
        config = {"url": "http://8.8.8.8/hook", "method": "POST", "template": "x=${gravity}"}
        with patch("oss.jobs._forward_common.http_post", new_callable=AsyncMock,
                   return_value=False):
            result = await deliver_custom(config, {"gravity": 1.05}, "subj1", "label")
        assert result == "failed"

    @pytest.mark.asyncio
    async def test_successful_get_returns_delivered(self):
        config = {"url": "http://8.8.8.8/hook", "method": "GET", "template": "field1=${gravity}"}
        with patch("oss.jobs._forward_common.http_get", new_callable=AsyncMock,
                   return_value=True):
            result = await deliver_custom(config, {"gravity": 1.05}, "subj1", "label")
        assert result == "delivered"

    @pytest.mark.asyncio
    async def test_failed_get_returns_failed(self):
        config = {"url": "http://8.8.8.8/hook", "method": "GET", "template": "field1=${gravity}"}
        with patch("oss.jobs._forward_common.http_get", new_callable=AsyncMock,
                   return_value=False):
            result = await deliver_custom(config, {"gravity": 1.05}, "subj1", "label")
        assert result == "failed"


# ---------------------------------------------------------------------------
# apply_delivery_outcome
# ---------------------------------------------------------------------------

class _Target:  # pylint: disable=too-few-public-methods
    """Minimal stand-in for an Integration ORM row -- a plain object (not a
    MagicMock) so integer arithmetic on consecutive_failures behaves like the
    real int column instead of MagicMock's auto-mocked magic methods."""

    def __init__(self, consecutive_failures=0, enabled=True, name="Target", id_="tgt-1"):
        self.consecutive_failures = consecutive_failures
        self.enabled = enabled
        self.name = name
        self.id = id_  # pylint: disable=invalid-name


class TestApplyDeliveryOutcome:
    """Tests for apply_delivery_outcome's per-target consecutive_failures
    tracking and auto-disable-at-3 safeguard. apply_delivery_outcome is
    async solely so it can await an async on_disable -- a caller's callback
    may need to await its own I/O (a DB write, a notification, ...)."""

    @pytest.mark.asyncio
    async def test_delivered_resets_a_nonzero_counter(self):
        target = _Target(consecutive_failures=2)
        with patch("oss.jobs._forward_common.system_log_scheduler") as mock_log:
            await apply_delivery_outcome(target, "delivered")
        assert target.consecutive_failures == 0
        assert target.enabled is True
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_skipped_leaves_every_counter_alone(self):
        target = _Target(consecutive_failures=2)
        with patch("oss.jobs._forward_common.system_log_scheduler") as mock_log:
            await apply_delivery_outcome(target, "skipped")
        assert target.consecutive_failures == 2
        assert target.enabled is True
        assert not hasattr(target, "last_success_at")
        assert not hasattr(target, "last_failure_at")
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_increments_counter(self):
        target = _Target(consecutive_failures=0)
        with patch("oss.jobs._forward_common.system_log_scheduler") as mock_log:
            await apply_delivery_outcome(target, "failed")
        assert target.consecutive_failures == 1
        assert target.enabled is True
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocked_increments_counter_same_as_failed(self):
        target = _Target(consecutive_failures=0)
        with patch("oss.jobs._forward_common.system_log_scheduler") as mock_log:
            await apply_delivery_outcome(target, "blocked")
        assert target.consecutive_failures == 1
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_third_consecutive_failure_auto_disables_and_resets_counter(self):
        target = _Target(consecutive_failures=2, name="Brewfather")
        with patch("oss.jobs._forward_common.system_log_scheduler") as mock_log:
            await apply_delivery_outcome(target, "failed")
        assert target.enabled is False
        assert target.consecutive_failures == 0
        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        assert "Brewfather" in args[0]
        assert kwargs["level"] == LogLevel.WARNING


# ---------------------------------------------------------------------------
# Worker lifecycle and database recovery
# ---------------------------------------------------------------------------

class TestWorkerLifecycle:
    """Shared worker cleanup keeps the next queue item independent of the last."""

    @pytest.mark.asyncio
    async def test_close_http_client_closes_and_removes_shared_client(self, monkeypatch):
        client = AsyncMock()
        https_client = AsyncMock()
        monkeypatch.setattr(forward_common, "_http_client_box", [client])
        monkeypatch.setattr(forward_common, "_pinned_https_client_box", [https_client])

        await close_http_client()

        client.aclose.assert_awaited_once_with()
        https_client.aclose.assert_awaited_once_with()
        assert not getattr(forward_common, "_http_client_box")
        assert not getattr(forward_common, "_pinned_https_client_box")

    def test_recover_forwarding_error_rolls_back_before_retrying_item(self):
        session_factory = MagicMock()
        retry = MagicMock()
        log = MagicMock()
        item = {"deviceId": "device-1"}
        raw = b"queued-item"

        recover_forwarding_error(
            session_factory,
            label="gravity_forward",
            subject_id="device-1",
            item=item,
            raw=raw,
            retry=retry,
            log=log,
            exc=RuntimeError("database unavailable"),
        )

        session_factory.return_value.rollback.assert_called_once_with()
        retry.assert_called_once_with(item, raw)

    @pytest.mark.asyncio
    async def test_on_disable_awaited_only_when_auto_disabling(self):
        target = _Target(consecutive_failures=2)
        on_disable = AsyncMock()
        with patch("oss.jobs._forward_common.system_log_scheduler"):
            await apply_delivery_outcome(target, "failed", on_disable)
        on_disable.assert_awaited_once_with(target)

    @pytest.mark.asyncio
    async def test_on_disable_not_called_below_threshold(self):
        target = _Target(consecutive_failures=0)
        on_disable = AsyncMock()
        await apply_delivery_outcome(target, "failed", on_disable)
        on_disable.assert_not_called()

    @pytest.mark.asyncio
    async def test_mixed_failures_across_three_separate_calls_disable(self):
        """3 consecutive failures, whether from one item's retries or three
        separate items, disable the target the same way."""
        target = _Target(consecutive_failures=0)
        with patch("oss.jobs._forward_common.system_log_scheduler") as mock_log:
            await apply_delivery_outcome(target, "blocked")
            await apply_delivery_outcome(target, "failed")
            await apply_delivery_outcome(target, "failed")
        assert target.enabled is False
        assert target.consecutive_failures == 0
        mock_log.assert_called_once()
