# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

# pylint: disable=too-few-public-methods
"""Tests for core/middleware/auth.py — API key auth, rate limiting, quota."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from core.middleware.auth import (AuthContext, _get_client_ip, api_key_auth,
                                  check_quota, ingest_auth, record_auth_failure)


def _request(headers=None, client_host="10.0.0.1"):
    req = MagicMock()
    req.headers = headers or {}
    req.url.path = "/api/batches"
    req.client = MagicMock()
    req.client.host = client_host
    return req


def _settings(api_key="testkey", enabled=True, trust_proxy=False,
              max_failures=5, block_seconds=300):
    s = MagicMock()
    s.api_key = SecretStr(api_key)
    s.api_key_enabled = enabled
    s.trust_proxy_headers = trust_proxy
    s.auth_max_failures = max_failures
    s.auth_block_seconds = block_seconds
    return s


# ---------------------------------------------------------------------------
# check_quota
# ---------------------------------------------------------------------------

class TestCheckQuota:
    """Tests for the check_quota helper."""

    def test_unlimited_never_raises(self):
        """check_quota never raises when the limit is -1 (unlimited)."""
        check_quota(1000, AuthContext(quota_limits={"devices": -1}), "devices")

    def test_unset_resource_is_unlimited(self):
        """A resource with no entry is unlimited, which is the answer here."""
        check_quota(1000, AuthContext(), "devices")  # must not raise

    def test_below_limit_does_not_raise(self):
        """check_quota does not raise when count is below the limit."""
        check_quota(4, AuthContext(quota_limits={"devices": 5}), "devices")

    def test_at_limit_raises_403(self):
        """check_quota raises HTTP 403 when count equals the limit."""
        with pytest.raises(HTTPException) as exc:
            check_quota(5, AuthContext(quota_limits={"devices": 5}), "devices")
        assert exc.value.status_code == 403

    def test_above_limit_raises_403(self):
        """check_quota raises HTTP 403 when count exceeds the limit."""
        with pytest.raises(HTTPException) as exc:
            check_quota(10, AuthContext(quota_limits={"taps": 5}), "taps")
        assert exc.value.status_code == 403

    def test_one_resource_limit_does_not_constrain_another(self):
        """Limits are per resource — a tap cap must not block device creation."""
        auth = AuthContext(quota_limits={"taps": 1})
        check_quota(500, auth, "devices")  # must not raise


# ---------------------------------------------------------------------------
# _get_client_ip
# ---------------------------------------------------------------------------

class TestGetClientIp:
    """Tests for the _get_client_ip middleware helper."""

    def test_forwarded_for_used_when_proxy_trusted(self):
        """Uses the rightmost X-Forwarded-For entry when proxy is trusted."""
        # Rightmost entry is used: it's the IP appended by the trusted proxy
        # (nginx sets X-Forwarded-For from $remote_addr, appending the real client).
        # Taking [-1] prevents spoofing via a client-injected leading entry.
        req = _request(headers={"X-Forwarded-For": "spoofed_ip, 5.6.7.8"})
        with patch("core.config.get_settings") as mock_cfg:
            mock_cfg.return_value = _settings(trust_proxy=True)
            assert _get_client_ip(req) == "5.6.7.8"

    def test_direct_client_used_when_proxy_not_trusted(self):
        """Falls back to direct client host when proxy headers are not trusted."""
        req = _request(headers={"X-Forwarded-For": "1.2.3.4"}, client_host="10.0.0.5")
        with patch("core.config.get_settings") as mock_cfg:
            mock_cfg.return_value = _settings(trust_proxy=False)
            assert _get_client_ip(req) == "10.0.0.5"

    def test_no_forwarded_header_falls_back_to_client(self):
        """Falls back to client.host when no X-Forwarded-For header is present."""
        req = _request(client_host="192.168.1.1")
        with patch("core.config.get_settings") as mock_cfg:
            mock_cfg.return_value = _settings(trust_proxy=True)
            assert _get_client_ip(req) == "192.168.1.1"


# ---------------------------------------------------------------------------
# api_key_auth — disabled path
# ---------------------------------------------------------------------------

class TestApiKeyAuthDisabled:
    """Tests for api_key_auth when auth is disabled."""

    def test_disabled_always_returns_auth_context(self):
        """Returns a valid AuthContext for any key when auth is disabled."""
        req = _request()
        with patch("core.middleware.auth.get_settings") as mock_cfg:
            mock_cfg.return_value = _settings(enabled=False)
            ctx = api_key_auth(req, api_key="anything")
        assert ctx is not None


# ---------------------------------------------------------------------------
# api_key_auth — blocked IP
# ---------------------------------------------------------------------------

class TestApiKeyAuthBlocked:
    """Tests for api_key_auth when the source IP is blocked."""

    def test_blocked_ip_raises_429(self):
        """Raises HTTP 429 when the requesting IP is in the block list."""
        req = _request()
        with patch("core.middleware.auth.get_settings") as mock_cfg, \
             patch("core.middleware.auth.exist_key", return_value=True), \
             patch("core.middleware.auth.delete_key"), \
             patch("core.middleware.auth.hmac.compare_digest", return_value=False):
            mock_cfg.return_value = _settings()
            with pytest.raises(HTTPException) as exc:
                api_key_auth(req, api_key="wrongkey")
        assert exc.value.status_code == 429


# ---------------------------------------------------------------------------
# api_key_auth — failure accumulation and IP block
# ---------------------------------------------------------------------------

class TestApiKeyAuthFailures:
    """Tests for api_key_auth failure accumulation and IP blocking."""

    def test_below_max_failures_raises_401(self):
        """Raises HTTP 401 when failure count is below the configured maximum."""
        req = _request()
        with patch("core.middleware.auth.get_settings") as mock_cfg, \
             patch("core.middleware.auth.exist_key", return_value=False), \
             patch("core.middleware.auth.increment_key", return_value=1), \
             patch("core.middleware.auth.delete_key"), \
             patch("core.middleware.auth.hmac.compare_digest", return_value=False):
            mock_cfg.return_value = _settings(max_failures=5)
            with pytest.raises(HTTPException) as exc:
                api_key_auth(req, api_key="bad")
        assert exc.value.status_code == 401

    def test_at_max_failures_raises_429_and_blocks(self):
        """Raises HTTP 429 and blocks the IP when failures reach the configured maximum."""
        req = _request()
        with patch("core.middleware.auth.get_settings") as mock_cfg, \
             patch("core.middleware.auth.exist_key", return_value=False), \
             patch("core.middleware.auth.increment_key", return_value=5), \
             patch("core.middleware.auth.delete_key"), \
             patch("core.middleware.auth.hmac.compare_digest", return_value=False), \
             patch("core.middleware.auth.system_log_security"):
            mock_cfg.return_value = _settings(max_failures=5)
            with pytest.raises(HTTPException) as exc:
                api_key_auth(req, api_key="bad")
        assert exc.value.status_code == 429


# ---------------------------------------------------------------------------
# record_auth_failure
# ---------------------------------------------------------------------------

class TestRecordAuthFailure:
    """Tests for the record_auth_failure helper."""

    def test_below_threshold_does_not_block(self):
        """IP is not blocked when the failure count is below the maximum."""
        with patch("core.middleware.auth.get_settings") as mock_cfg, \
             patch("core.middleware.auth.increment_key", return_value=2) as mock_inc, \
             patch("core.middleware.auth.delete_key"):
            mock_cfg.return_value = _settings(max_failures=5)
            record_auth_failure("10.0.0.1")
        mock_inc.assert_called_once()

    def test_at_threshold_blocks_ip(self):
        """IP is blocked when the failure count reaches the maximum."""
        with patch("core.middleware.auth.get_settings") as mock_cfg, \
             patch("core.middleware.auth.increment_key", return_value=5), \
             patch("core.middleware.auth.delete_key") as mock_del, \
             patch("core.middleware.auth.system_log_security"):
            mock_cfg.return_value = _settings(max_failures=5)
            record_auth_failure("10.0.0.1")
        mock_del.assert_called_once()

    def test_at_threshold_logs_truncated_ip_not_full_ip(self):
        """The security log message carries a truncated IP, never the full address."""
        with patch("core.middleware.auth.get_settings") as mock_cfg, \
             patch("core.middleware.auth.increment_key", return_value=5), \
             patch("core.middleware.auth.delete_key"), \
             patch("core.middleware.auth.system_log_security") as mock_log:
            mock_cfg.return_value = _settings(max_failures=5)
            record_auth_failure("203.0.113.77")
        message = mock_log.call_args[0][0]
        assert "203.0.113.0" in message
        assert "203.0.113.77" not in message


# ---------------------------------------------------------------------------
# ingest_auth
# ---------------------------------------------------------------------------


class TestIngestAuth:
    """Tests for the ingest_auth rate-limit security log message."""

    def test_rate_limited_logs_truncated_ip_not_full_ip(self):
        """The ingest rate-limit security log message carries a truncated IP."""
        req = _request(client_host="203.0.113.77")
        throttle = MagicMock(pre_auth_per_minute=1)
        with patch("core.middleware.auth.get_settings") as mock_cfg, \
             patch("core.middleware.auth.exist_key", return_value=False), \
             patch("core.middleware.auth.increment_key", return_value=999), \
             patch("core.middleware.auth.system_log_security") as mock_log:
            mock_cfg.return_value = _settings()
            with pytest.raises(HTTPException):
                ingest_auth(req, throttle)
        message = mock_log.call_args[0][0]
        assert "203.0.113.0" in message
        assert "203.0.113.77" not in message
