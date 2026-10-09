# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Redis cache management for storing temporary data and session information."""
import logging
import time
from threading import RLock

import redis

from core.config import get_settings

logger = logging.getLogger(__name__)

logger.info(
    "Creating connection pool to redis using redis://%s:6379.", get_settings().redis_host
)

pool = None

# Redis is the shared fast path. This bounded process-local fallback preserves
# abuse controls during a Redis outage instead of silently treating every
# counter as zero. It deliberately does not claim cross-replica coordination.
_fallback_values: dict[str, tuple[str, float]] = {}
_fallback_lock = RLock()
_MAX_FALLBACK_KEYS = 10_000
# Keep this list aligned with every anti-abuse key actually emitted by callers.
# It is deliberately narrow: ordinary cache and queue keys must retain their
# documented fail-open behaviour when Redis is unavailable.
_FALLBACK_PREFIXES = (
    "auth:",
    "ingest:",
    "ingest_rl_device:",
    "ingest_throttle_",
    "integration_test:",
    "public_display:rate:",
)

if get_settings().cache_enabled:
    pool = redis.ConnectionPool(
        host=get_settings().redis_host,
        port=6379,
        db=0,
        password=get_settings().redis_password.get_secret_value() or None,
    )


def _fallback_key(key: str | bytes) -> str:
    """Normalise Redis-compatible byte keys for the local fallback."""
    return key.decode() if isinstance(key, bytes) else key


def _uses_local_fallback(key: str | bytes) -> bool:
    """Limit the local store to anti-abuse controls, not general cache data."""
    return _fallback_key(key).startswith(_FALLBACK_PREFIXES)


def _fallback_get(key: str | bytes) -> str | None:
    """Read a non-expired fallback value."""
    normalised = _fallback_key(key)
    with _fallback_lock:
        entry = _fallback_values.get(normalised)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at <= time.monotonic():
            _fallback_values.pop(normalised, None)
            return None
        return value


def _fallback_prune() -> None:
    """Discard expired local entries before allocating another fallback key."""
    now = time.monotonic()
    for key, (_, expires_at) in list(_fallback_values.items()):
        if expires_at <= now:
            _fallback_values.pop(key, None)


def _fallback_set(key: str | bytes, value: str, ttl: int, *, nx: bool = False) -> bool:
    """Write one fallback value, optionally only when no live value exists."""
    normalised = _fallback_key(key)
    with _fallback_lock:
        _fallback_prune()
        if nx and _fallback_get(normalised) is not None:
            return False
        if normalised not in _fallback_values and len(_fallback_values) >= _MAX_FALLBACK_KEYS:
            return False
        _fallback_values[normalised] = (value, time.monotonic() + ttl)
        return True


def _fallback_delete(key: str | bytes) -> None:
    """Remove one fallback value."""
    with _fallback_lock:
        _fallback_values.pop(_fallback_key(key), None)


def _fallback_increment(key: str, ttl: int) -> int:
    """Increment one fallback counter with a fixed first-write TTL."""
    with _fallback_lock:
        current = _fallback_get(key)
        if current is None:
            if not _fallback_set(key, "1", ttl):
                # Deny new work rather than allow an attacker to evade every
                # local counter by exhausting fallback storage.
                return 2 ** 31 - 1
            return 1
        value, expires_at = _fallback_values[key]
        count = int(value) + 1
        _fallback_values[key] = (str(count), expires_at)
        return count


def _fallback_ttl(key: str | bytes) -> int | None:
    """Return a live fallback TTL in seconds, if one exists."""
    normalised = _fallback_key(key)
    with _fallback_lock:
        if _fallback_get(normalised) is None:
            return None
        _, expires_at = _fallback_values[normalised]
        return max(0, int(expires_at - time.monotonic()))


def delete_key(key: str | bytes) -> None:
    """Delete a key from the Redis cache."""
    if pool is None:
        _fallback_delete(key)
        return

    logger.info("Removing %s.", key)
    try:
        r = redis.Redis(connection_pool=pool)
        r.delete(key)
    except redis.exceptions.ConnectionError as e:
        logger.error("Failed to connect with redis %s.", e)
        _fallback_delete(key)


def find_key(key: str, *, limit: int = 500) -> list[bytes]:
    """Find up to ``limit`` cache keys without blocking Redis with ``KEYS``."""
    if pool is None:
        return []

    logger.info("Searching key %s.", key)
    try:
        r = redis.Redis(connection_pool=pool)
        keys = []
        for found in r.scan_iter(match=key, count=min(limit, 100)):
            keys.append(found)
            if len(keys) >= limit:
                break
        return keys
    except redis.exceptions.ConnectionError as e:
        logger.error("Failed to connect with redis %s.", e)
    return []


def write_key(key: str, value: str, ttl: int) -> bool:
    """Write a key-value pair to Redis cache with optional TTL."""
    if pool is None:
        return True

    logger.info("Writing key %s = %s ttl:%s.", key, value, ttl)
    try:
        r = redis.Redis(connection_pool=pool)
        r.set(name=key, value=str(value), ex=ttl)
        return True
    except redis.exceptions.ConnectionError as e:
        logger.error("Failed to connect with redis %s.", e)
    return False


def set_key_if_absent(key: str, value: str, ttl: int) -> bool:
    """Atomically set a key with TTL only when it does not already exist."""
    if pool is None:
        return _fallback_set(key, value, ttl, nx=True) if _uses_local_fallback(key) else True
    try:
        r = redis.Redis(connection_pool=pool)
        return bool(r.set(name=key, value=str(value), nx=True, ex=ttl))
    except redis.exceptions.ConnectionError as e:
        logger.error("Failed to connect with redis %s.", e)
    return _fallback_set(key, value, ttl, nx=True) if _uses_local_fallback(key) else True


def read_key(key: str | bytes) -> bytes | None:
    """Read a value from Redis cache by key."""
    if pool is None:
        return None

    logger.info("Reading key %s.", key)
    try:
        r = redis.Redis(connection_pool=pool)
        return r.get(name=key)
    except redis.exceptions.ConnectionError as e:
        logger.error("Failed to connect with redis %s.", e)

    return None


def key_ttl(key: str | bytes) -> int | None:
    """Return the remaining TTL of `key` in whole seconds, or None if unknown.

    None covers every case where a caller cannot state a wait honestly: Redis
    unavailable, key absent, or key present with no expiry. Callers use this to set
    `Retry-After` on a 429 — and a `Retry-After` guessed from a nominal interval is
    worse than none, because a client that trusts it retries early and is throttled
    again.
    """
    if pool is None:
        return _fallback_ttl(key) if _uses_local_fallback(key) else None
    try:
        r = redis.Redis(connection_pool=pool)
        remaining = r.ttl(name=key)
        # redis-py: -2 = no such key, -1 = key exists with no expiry.
        return int(remaining) if remaining is not None and remaining >= 0 else None
    except redis.exceptions.ConnectionError as e:
        logger.error("Failed to connect with redis %s.", e)
    return _fallback_ttl(key) if _uses_local_fallback(key) else None


def increment_key(key: str, ttl: int) -> int:
    """Increment a counter key, setting TTL on first creation. Returns new value."""
    if pool is None:
        return _fallback_increment(key, ttl) if _uses_local_fallback(key) else 0

    logger.info("Incrementing key %s ttl:%s.", key, ttl)
    try:
        r = redis.Redis(connection_pool=pool)
        count = r.incr(key)
        if count == 1:
            r.expire(key, ttl)
        return count
    except redis.exceptions.ConnectionError as e:
        logger.error("Failed to connect with redis %s.", e)
    return _fallback_increment(key, ttl) if _uses_local_fallback(key) else 0


def acquire_lock(key: str, ttl: int) -> bool:
    """Try to claim `key` as a mutual-exclusion lock for `ttl` seconds.

    `SET key <ts> NX EX ttl` — atomic on the Redis server, so exactly one caller
    across every process and container wins, and the loser gets False.

    There is deliberately no matching release: locks are meant to expire. A caller
    that released on completion would re-open the window it exists to close — a
    fast job would free the lock before a peer whose clock is a second behind even
    fires, and both would run. Choose a TTL shorter than the interval you want to
    deduplicate and let it lapse on its own; a crashed holder then costs at most
    one skipped cycle rather than a stuck lock.

    Fails open when Redis is unavailable. Redis is the only safe way to
    coordinate this lock across replicas, and background work must continue if
    the cache is unavailable.
    """
    if pool is None:
        return True

    try:
        r = redis.Redis(connection_pool=pool)
        return bool(r.set(name=key, value=str(time.time()), nx=True, ex=ttl))
    except redis.exceptions.ConnectionError as e:
        logger.error("Failed to connect with redis %s.", e)
    return True


def exist_key(key: str | bytes) -> bool:
    """Check if a key exists in Redis cache."""
    if pool is None:
        return _fallback_get(key) is not None if _uses_local_fallback(key) else False

    logger.info("Check key %s.", key)
    try:
        r = redis.Redis(connection_pool=pool)
        return r.exists(key)
    except redis.exceptions.ConnectionError as e:
        logger.error("Failed to connect with redis %s.", e)

    return _fallback_get(key) is not None if _uses_local_fallback(key) else False
