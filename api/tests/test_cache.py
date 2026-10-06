# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

# pylint: disable=attribute-defined-outside-init
"""Tests for core/cache.py — covers both pool=None fast-paths and Redis operation paths."""
from unittest.mock import MagicMock, patch

import redis

import core.cache as cache_mod

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pool():
    """Return a sentinel pool object (not None) so the Redis branches execute."""
    return MagicMock()


def _mock_redis(_pool, **method_returns):
    """Patch redis.Redis so it returns a mock with the given method behaviours."""
    mock_r = MagicMock()
    for method, val in method_returns.items():
        getattr(mock_r, method).return_value = val
    return patch("redis.Redis", return_value=mock_r)


# ---------------------------------------------------------------------------
# pool=None fast-paths (cache disabled)
# ---------------------------------------------------------------------------

class TestCacheDisabled:
    """When pool is None every function must return quickly without touching Redis."""

    def setup_method(self):
        """Save and replace the pool with None to simulate disabled cache."""
        self._orig_pool = cache_mod.pool
        cache_mod.pool = None

    def teardown_method(self):
        """Restore the original pool after each test."""
        cache_mod.pool = self._orig_pool

    def test_delete_key_returns_none(self):
        """delete_key returns None when pool is not configured."""
        assert cache_mod.delete_key("k") is None

    def test_find_key_returns_empty_list(self):
        """find_key returns an empty list when pool is not configured."""
        assert not cache_mod.find_key("*")

    def test_write_key_returns_true(self):
        """write_key returns True (no-op success) when pool is not configured."""
        assert cache_mod.write_key("k", "v", 60) is True

    def test_read_key_returns_none(self):
        """read_key returns None when pool is not configured."""
        assert cache_mod.read_key("k") is None

    def test_exist_key_returns_false(self):
        """exist_key returns False when pool is not configured."""
        assert cache_mod.exist_key("k") is False

    def test_acquire_lock_returns_true(self):
        """acquire_lock fails open when pool is not configured.

        Note this is the opposite polarity to exist_key above: an unconfigured
        cache means "no locking", not "locked", so callers proceed.
        """
        assert cache_mod.acquire_lock("lock:k", 60) is True

    def test_set_key_if_absent_returns_true(self):
        """set_key_if_absent fails open when pool is not configured, same as acquire_lock."""
        assert cache_mod.set_key_if_absent("k", "v", 60) is True


# ---------------------------------------------------------------------------
# Redis operation paths (pool is not None)
# ---------------------------------------------------------------------------

class TestCacheEnabled:
    """When pool is set the functions delegate to Redis."""

    def setup_method(self):
        """Save pool and replace it with a mock so Redis branches execute."""
        self._orig_pool = cache_mod.pool
        cache_mod.pool = _mock_pool()

    def teardown_method(self):
        """Restore the original pool after each test."""
        cache_mod.pool = self._orig_pool

    # delete_key
    def test_delete_key_calls_redis_delete(self):
        """delete_key calls redis.delete with the given key."""
        with _mock_redis(cache_mod.pool) as mock_cls:
            cache_mod.delete_key("mykey")
        mock_cls.return_value.delete.assert_called_once_with("mykey")

    def test_delete_key_connection_error_is_handled(self):
        """delete_key swallows ConnectionError without raising."""
        with _mock_redis(cache_mod.pool) as mock_cls:
            mock_cls.return_value.delete.side_effect = redis.exceptions.ConnectionError("down")
            cache_mod.delete_key("mykey")  # must not raise

    # find_key
    def test_find_key_returns_redis_keys(self):
        """find_key scans matching keys and bounds broad patterns."""
        with _mock_redis(
            cache_mod.pool, scan_iter=[b"key1", b"key2", b"key3"]
        ) as mock_cls:
            result = cache_mod.find_key("key*", limit=2)
        assert result == [b"key1", b"key2"]
        mock_cls.return_value.scan_iter.assert_called_once_with(match="key*", count=2)

    def test_find_key_connection_error_returns_empty(self):
        """find_key returns an empty list when Redis raises ConnectionError."""
        with _mock_redis(cache_mod.pool) as mock_cls:
            mock_cls.return_value.scan_iter.side_effect = redis.exceptions.ConnectionError("down")
            result = cache_mod.find_key("key*")
        assert not result

    # write_key
    def test_write_key_calls_redis_set_and_returns_true(self):
        """write_key calls redis.set with the correct arguments and returns True."""
        with _mock_redis(cache_mod.pool) as mock_cls:
            result = cache_mod.write_key("k", "v", 120)
        mock_cls.return_value.set.assert_called_once_with(name="k", value="v", ex=120)
        assert result is True

    def test_write_key_connection_error_returns_false(self):
        """write_key returns False when Redis raises ConnectionError."""
        with _mock_redis(cache_mod.pool) as mock_cls:
            mock_cls.return_value.set.side_effect = redis.exceptions.ConnectionError("down")
            result = cache_mod.write_key("k", "v", 60)
        assert result is False

    # read_key
    def test_read_key_returns_bytes(self):
        """read_key returns the raw bytes value from Redis."""
        with _mock_redis(cache_mod.pool, get=b"hello"):
            result = cache_mod.read_key("k")
        assert result == b"hello"

    def test_read_key_connection_error_returns_none(self):
        """read_key returns None when Redis raises ConnectionError."""
        with _mock_redis(cache_mod.pool) as mock_cls:
            mock_cls.return_value.get.side_effect = redis.exceptions.ConnectionError("down")
            result = cache_mod.read_key("k")
        assert result is None

    # exist_key
    def test_exist_key_returns_true_when_present(self):
        """exist_key returns a truthy value when the key exists in Redis."""
        with _mock_redis(cache_mod.pool, exists=1):
            result = cache_mod.exist_key("k")
        assert result == 1

    def test_exist_key_connection_error_returns_false(self):
        """exist_key returns False when Redis raises ConnectionError."""
        with _mock_redis(cache_mod.pool) as mock_cls:
            mock_cls.return_value.exists.side_effect = redis.exceptions.ConnectionError("down")
            result = cache_mod.exist_key("k")
        assert result is False

    # acquire_lock
    def test_acquire_lock_returns_true_when_set_succeeds(self):
        """Winning the SET NX means the caller holds the lock."""
        with _mock_redis(cache_mod.pool, set=True):
            assert cache_mod.acquire_lock("lock:k", 60) is True

    def test_acquire_lock_returns_false_when_key_exists(self):
        """redis-py returns None from a SET NX that lost; that must read as False."""
        with _mock_redis(cache_mod.pool, set=None):
            assert cache_mod.acquire_lock("lock:k", 60) is False

    def test_acquire_lock_uses_nx_and_ex(self):
        """Atomicity depends on NX, and bounded holding on EX — neither may be dropped.

        Without nx a loser would overwrite the winner's lock; without ex a crashed
        holder would block the key forever.
        """
        with _mock_redis(cache_mod.pool, set=True) as mock_cls:
            cache_mod.acquire_lock("lock:k", 60)
        kwargs = mock_cls.return_value.set.call_args.kwargs
        assert kwargs["nx"] is True
        assert kwargs["ex"] == 60

    def test_acquire_lock_connection_error_fails_open(self):
        """An unreachable Redis must not stop the caller from doing its work."""
        with _mock_redis(cache_mod.pool) as mock_cls:
            mock_cls.return_value.set.side_effect = redis.exceptions.ConnectionError("down")
            assert cache_mod.acquire_lock("lock:k", 60) is True

    # set_key_if_absent
    def test_set_key_if_absent_returns_true_when_set_succeeds(self):
        """Winning the SET NX means the caller claimed the key."""
        with _mock_redis(cache_mod.pool, set=True):
            assert cache_mod.set_key_if_absent("ingest_throttle_dev", "1", 60) is True

    def test_set_key_if_absent_returns_false_when_key_exists(self):
        """redis-py returns None from a SET NX that lost; that must read as False.

        This is the atomicity §8 fixes: a concurrent second claim for the same
        device must lose deterministically, not observe a stale absence via a
        separate GET.
        """
        with _mock_redis(cache_mod.pool, set=None):
            assert cache_mod.set_key_if_absent("ingest_throttle_dev", "1", 60) is False

    def test_set_key_if_absent_uses_nx_and_ex(self):
        """Atomicity depends on NX, and bounded holding on EX — neither may be dropped.

        Without nx two concurrent first-ingest requests could both observe the key
        absent and both pass, which is the exact race this helper closes.
        """
        with _mock_redis(cache_mod.pool, set=True) as mock_cls:
            cache_mod.set_key_if_absent("ingest_throttle_dev", "1", 60)
        kwargs = mock_cls.return_value.set.call_args.kwargs
        assert kwargs["nx"] is True
        assert kwargs["ex"] == 60

    def test_set_key_if_absent_connection_error_fails_open(self):
        """An unreachable Redis must not stop ingest from proceeding."""
        with _mock_redis(cache_mod.pool) as mock_cls:
            mock_cls.return_value.set.side_effect = redis.exceptions.ConnectionError("down")
            assert cache_mod.set_key_if_absent("ingest_throttle_dev", "1", 60) is True
