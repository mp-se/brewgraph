# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the in-process anti-abuse fallback used when Redis is unavailable."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from core import cache
from core.middleware.auth import api_key_auth

SHIPPED_CAPACITY = cache._MAX_FALLBACK_KEYS  # read before the fixture shrinks it


@pytest.fixture(autouse=True)
def local_fallback(monkeypatch):
    """No Redis pool, an empty fallback store, and a small capacity."""
    monkeypatch.setattr(cache, "pool", None)
    monkeypatch.setattr(cache, "_fallback_values", {})
    monkeypatch.setattr(cache, "_MAX_FALLBACK_KEYS", 3)
    # conftest stubs these names in the auth module; these tests need the real ones.
    for name in ("exist_key", "increment_key", "delete_key"):
        monkeypatch.setattr(f"core.middleware.auth.{name}", getattr(cache, name))


class TestFallbackCounters:
    """The fallback counts, expires and blocks like the Redis path."""

    def test_counter_increments_and_reports_ttl(self):
        """Repeated increments count up and the key has a live TTL."""
        assert [cache.increment_key("auth:failures:1.1.1.1", 60) for _ in range(3)] == [1, 2, 3]
        assert 0 < cache.key_ttl("auth:failures:1.1.1.1") <= 60
        assert cache.exist_key("auth:failures:1.1.1.1")

    def test_expiry_removes_the_key(self):
        """A key past its TTL no longer exists and restarts from one."""
        with patch("core.cache.time.monotonic", return_value=1000.0):
            cache.increment_key("auth:blocked:2.2.2.2", 5)
        with patch("core.cache.time.monotonic", return_value=1006.0):
            assert not cache.exist_key("auth:blocked:2.2.2.2")
            assert cache.increment_key("auth:blocked:2.2.2.2", 5) == 1

    def test_delete_clears_counter(self):
        """delete_key resets a counter."""
        cache.increment_key("auth:failures:3.3.3.3", 60)
        cache.delete_key("auth:failures:3.3.3.3")
        assert cache.increment_key("auth:failures:3.3.3.3", 60) == 1

    def test_non_abuse_keys_stay_fail_open(self):
        """Ordinary cache keys are not held in the fallback."""
        assert cache.increment_key("some:cache:key", 60) == 0
        assert not cache.exist_key("some:cache:key")


class TestFallbackCapacity:
    """At capacity new keys are refused as over-limit; existing keys keep working."""

    def test_full_store_denies_new_counters(self):
        """A new key at capacity reports an over-limit count and is not stored."""
        for i in range(3):
            assert cache.increment_key(f"auth:failures:10.0.0.{i}", 60) == 1
        assert cache.increment_key("auth:failures:10.0.0.99", 60) >= 2 ** 31 - 1
        assert len(cache._fallback_values) == 3

    def test_existing_counter_still_increments_when_full(self):
        """A key already stored keeps counting at capacity."""
        for i in range(3):
            cache.increment_key(f"auth:failures:10.0.0.{i}", 60)
        assert cache.increment_key("auth:failures:10.0.0.0", 60) == 2

    def test_expired_entries_free_capacity(self):
        """Expired keys are pruned so capacity returns."""
        with patch("core.cache.time.monotonic", return_value=1000.0):
            for i in range(3):
                cache.increment_key(f"auth:failures:10.0.0.{i}", 5)
        with patch("core.cache.time.monotonic", return_value=1010.0):
            assert cache.increment_key("auth:failures:10.0.0.99", 5) == 1

    def test_production_capacity_is_ten_thousand(self):
        """The shipped limit is 10,000 keys."""
        assert SHIPPED_CAPACITY == 10_000


def _settings():
    s = MagicMock()
    s.api_key = SecretStr("goodkey")
    s.trust_proxy_headers = False
    s.auth_max_failures = 5
    s.auth_block_seconds = 300
    return s


def _request(host):
    req = MagicMock()
    req.headers = {}
    req.client = MagicMock()
    req.client.host = host
    req.url.path = "/api/x"
    return req


class TestAuthWithExhaustedFallback:
    """Brute-force protection holds when the fallback store is full."""

    def test_wrong_key_from_new_ip_is_denied(self):
        """With the store full, a failed attempt from a new IP gets 429, not 401."""
        for i in range(3):
            cache.increment_key(f"auth:failures:10.0.0.{i}", 60)
        with patch("core.middleware.auth.get_settings", return_value=_settings()), \
             patch("core.middleware.auth.system_log_security"):
            with pytest.raises(HTTPException) as exc:
                api_key_auth(_request("203.0.113.9"), api_key="wrong")
        assert exc.value.status_code == 429

    def test_blocking_works_without_redis(self):
        """Five bad keys block the IP, and the correct key is then refused."""
        with patch("core.middleware.auth.get_settings", return_value=_settings()), \
             patch("core.middleware.auth.system_log_security"):
            codes = []
            for _ in range(5):
                with pytest.raises(HTTPException) as exc:
                    api_key_auth(_request("203.0.113.9"), api_key="wrong")
                codes.append(exc.value.status_code)
            with pytest.raises(HTTPException) as blocked:
                api_key_auth(_request("203.0.113.9"), api_key="goodkey")
        assert codes == [401, 401, 401, 401, 429]
        assert blocked.value.status_code == 429
