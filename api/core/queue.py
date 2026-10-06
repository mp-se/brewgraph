# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Reliable Redis-backed queue primitives: list-based push/pop, a pop-into-processing
+ reclaim-sweep pattern for at-least-once delivery, and a renewable distributed lock.

`core/cache.py` only provides get/set operations; this module adds the list and
sorted-set primitives a background-job queue needs, sharing its connection pool
rather than opening a second one to the same Redis instance. Domain-agnostic —
nothing here knows what a "gravity forward" is; see `oss/jobs/gravity_forward.py`
for the one caller today.
"""
import logging
import time
import uuid
from typing import Optional

import redis

from core.cache import pool

logger = logging.getLogger(__name__)


def queue_push(queue: str, value: str) -> bool:
    """Push a value onto the left of a Redis list (LPUSH)."""
    if pool is None:
        return False
    try:
        redis.Redis(connection_pool=pool).lpush(queue, value)
        return True
    except redis.exceptions.RedisError as exc:
        logger.error("queue_push %s failed: %s", queue, exc)
    return False


def queue_len(queue: str) -> int:
    """Return the current length of a Redis list."""
    if pool is None:
        return 0
    try:
        return redis.Redis(connection_pool=pool).llen(queue)
    except redis.exceptions.RedisError as exc:
        logger.error("queue_len %s failed: %s", queue, exc)
    return 0


def queue_lrem(queue: str, value) -> None:
    """Remove one occurrence of value from queue (ack after successful processing)."""
    if pool is None:
        return
    try:
        redis.Redis(connection_pool=pool).lrem(queue, 1, value)
    except redis.exceptions.RedisError as exc:
        logger.error("queue_lrem %s failed: %s", queue, exc)


_POP_TO_PROCESSING_SCRIPT = (
    'local raw = redis.call("rpoplpush", KEYS[1], KEYS[2]) '
    'if raw then redis.call("zadd", KEYS[3], ARGV[1], raw) end '
    'return raw'
)


def queue_pop_to_processing(src: str, processing: str, processing_ts: str):
    """Non-blocking reliable-queue pop: RPOPLPUSH src -> processing, recording the
    current time as this item's score in the processing_ts sorted set — in the
    same Lua script, so a crash between the move and the timestamp write can't
    happen.

    A plain list has no per-item timestamp, which a staleness-reclaim sweep needs
    in order to tell how long an item has sat in `processing`. Returns None when
    src is empty or Redis is unavailable.
    """
    if pool is None:
        return None
    try:
        return redis.Redis(connection_pool=pool).eval(
            _POP_TO_PROCESSING_SCRIPT, 3, src, processing, processing_ts, time.time()
        )
    except redis.exceptions.RedisError as exc:
        logger.error("queue_pop_to_processing %s->%s failed: %s", src, processing, exc)
    return None


def queue_zrem(key: str, member) -> None:
    """Remove member from a sorted set (companion cleanup alongside queue_lrem)."""
    if pool is None:
        return
    try:
        redis.Redis(connection_pool=pool).zrem(key, member)
    except redis.exceptions.RedisError as exc:
        logger.error("queue_zrem %s failed: %s", key, exc)


def queue_zrangebyscore(key: str, max_score: float) -> list:
    """Return sorted-set members scored at or below max_score (a staleness cutoff)."""
    if pool is None:
        return []
    try:
        return redis.Redis(connection_pool=pool).zrangebyscore(key, "-inf", max_score)
    except redis.exceptions.RedisError as exc:
        logger.error("queue_zrangebyscore %s failed: %s", key, exc)
    return []


_RECLAIM_SCRIPT = (
    'local removed = redis.call("lrem", KEYS[1], 1, ARGV[1]) '
    'redis.call("zrem", KEYS[2], ARGV[1]) '
    'if removed == 1 then redis.call("lpush", KEYS[3], ARGV[1]) end '
    'return removed'
)


def queue_reclaim_stale(processing: str, processing_ts: str, dest_queue: str, member) -> bool:
    """Atomically move `member` out of `processing` back onto `dest_queue` for
    retry, clearing its `processing_ts` entry either way.

    Guards against double-requeuing: if the drain loop already acked and removed
    `member` from `processing` a moment before the sweep runs — its processing_ts
    entry can outlive the list entry, since the two acks aren't themselves atomic
    with each other — the LREM here removes 0 and no LPUSH happens; only the now-
    stale timestamp entry is cleaned up.
    """
    if pool is None:
        return False
    try:
        return bool(
            redis.Redis(connection_pool=pool).eval(
                _RECLAIM_SCRIPT, 3, processing, processing_ts, dest_queue, member
            )
        )
    except redis.exceptions.RedisError as exc:
        logger.error("queue_reclaim_stale %s->%s failed: %s", processing, dest_queue, exc)
    return False


_RELEASE_QUEUE_LOCK_SCRIPT = (
    'if redis.call("get", KEYS[1]) == ARGV[1] then '
    'return redis.call("del", KEYS[1]) else return 0 end'
)

_RENEW_QUEUE_LOCK_SCRIPT = (
    'if redis.call("get", KEYS[1]) == ARGV[1] then '
    'return redis.call("expire", KEYS[1], ARGV[2]) else return 0 end'
)


def queue_acquire_lock(name: str, ttl: int) -> Optional[str]:
    """Acquire a renewable distributed lock via SET NX EX. Returns an ownership
    token, or None when already held.

    Distinct from `core.cache.acquire_lock`: that one is fire-and-let-expire, for
    a job whose whole run fits inside one fixed TTL. A queue drain loop's runtime
    scales with queue depth, so it needs to prove ownership again on every
    renewal (`queue_renew_lock`) rather than pick one TTL upfront long enough for
    a worst case that keeps growing.

    Fails open (returns a token unconditionally) when Redis is unavailable —
    single-scheduler deployments must keep working without Redis; the lock only
    guards the multi-scheduler-replica case.
    """
    if pool is None:
        return uuid.uuid4().hex
    token = uuid.uuid4().hex
    try:
        if redis.Redis(connection_pool=pool).set(name, token, nx=True, ex=ttl):
            return token
        return None
    except redis.exceptions.RedisError as exc:
        logger.error("queue_acquire_lock %s failed: %s", name, exc)
    return uuid.uuid4().hex


def queue_renew_lock(name: str, token: str, ttl: int) -> bool:
    """Extend a held lock's TTL, but only if `token` still owns it.

    Returns False when this caller no longer owns the lock — its TTL already
    lapsed and another worker acquired it — meaning the caller must stop work
    rather than assume it still holds exclusivity. Fails open (returns True) when
    Redis is unavailable, matching queue_acquire_lock's single-scheduler
    behaviour.
    """
    if pool is None:
        return True
    try:
        return bool(
            redis.Redis(connection_pool=pool).eval(_RENEW_QUEUE_LOCK_SCRIPT, 1, name, token, ttl)
        )
    except redis.exceptions.RedisError as exc:
        logger.error("queue_renew_lock %s failed: %s", name, exc)
    return True


def queue_release_lock(name: str, token: str) -> None:
    """Release a distributed lock, but only if `token` still owns it.

    Compare-and-delete via a Lua script executed atomically on the Redis server.
    An unconditional DELETE would let a caller whose lock outlived its TTL (e.g. a
    slow drain) delete a different worker's live lock — this closes that window.
    """
    if pool is None:
        return
    try:
        redis.Redis(connection_pool=pool).eval(_RELEASE_QUEUE_LOCK_SCRIPT, 1, name, token)
    except redis.exceptions.RedisError as exc:
        logger.error("queue_release_lock %s failed: %s", name, exc)
