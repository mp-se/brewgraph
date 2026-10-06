# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""In-process SSE fan-out for broadcasting real-time events to connected clients.

An in-memory list of per-client `asyncio.Queue` instances is sufficient here:
this app is single-container, so there is no need for a Redis-backed pub/sub
layer. `notify_clients` sends every event as one JSON envelope:
{"method", "table", "source", "id"}.

The default in-memory `EventBroadcaster` below can be swapped out via
`register_transport()` for any other object implementing `EventTransport`
(publish + subscribe) — this keeps the module usable as-is while leaving the
wiring open for a different fan-out mechanism.
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import AsyncGenerator, Protocol

logger = logging.getLogger(__name__)

# SSE heartbeat: a comment line keeps proxies/browsers from closing idle connections.
_HEARTBEAT_SECS = 25

# Per-subscriber queue bound. Events are small JSON envelopes (~100 bytes), so this
# caps a stalled connection at roughly 100 KB rather than letting it grow without
# limit. The queue MUST stay bounded: with the default unbounded asyncio.Queue the
# QueueFull branch in broadcast() below is unreachable, so a client that stops
# reading accumulates every event for the lifetime of the connection.
_MAX_QUEUED_EVENTS = 1000


class EventBroadcaster:
    """Manage active SSE subscriber queues and fan out events to matching tenants."""

    def __init__(self) -> None:
        self._subscribers: dict[asyncio.Queue, object] = {}

    def subscribe(self, tenant_id: object) -> asyncio.Queue:
        """Register a new subscriber queue for *tenant_id* and return it."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUED_EVENTS)
        self._subscribers[queue] = tenant_id
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        self._subscribers.pop(queue, None)

    async def broadcast(self, tenant_id: object, message: str) -> None:
        """Put *message* onto every subscriber queue registered for *tenant_id*.

        Each subscriber's queue is isolated: if one is full, that subscriber
        misses the message but the fan-out continues for the rest.
        """
        for queue, sub_tenant_id in list(self._subscribers.items()):
            if sub_tenant_id != tenant_id:
                continue
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning(
                    "dropping event for slow subscriber: queue full (%d events)",
                    _MAX_QUEUED_EVENTS,
                )

    def subscriber_count(self) -> int:
        """Return the number of currently registered subscriber queues."""
        return len(self._subscribers)


event_broadcaster = EventBroadcaster()


@dataclass(frozen=True)
class EventEnvelope:
    """A single data-change event, addressed to one tenant."""

    table: str
    method: str
    record_id: object
    tenant_id: object
    source: str = "unknown"


class EventTransport(Protocol):
    """Pluggable transport for publishing and subscribing to change events."""

    async def publish(self, envelope: EventEnvelope) -> None:
        """Deliver *envelope* to all subscribers of `envelope.tenant_id`."""

    def subscribe(
        self, tenant_id: object, request_disconnected: asyncio.Event
    ) -> AsyncGenerator[str, None]:
        """Return an SSE-formatted async generator scoped to *tenant_id*."""


class _InMemoryEventTransport:
    """Default transport: fans out over the in-process `event_broadcaster`."""

    async def publish(self, envelope: EventEnvelope) -> None:
        """Deliver *envelope* via `event_broadcaster.broadcast`."""
        await event_broadcaster.broadcast(
            envelope.tenant_id,
            json.dumps({"method": envelope.method, "table": envelope.table,
                        "source": envelope.source, "id": str(envelope.record_id)}),
        )

    async def subscribe(
        self, tenant_id: object, request_disconnected: asyncio.Event
    ) -> AsyncGenerator[str, None]:
        """Async generator that yields SSE-formatted strings for a connected client.

        Yields:
            ``data: {...}\\n\\n``  for real events.
            ``: heartbeat\\n\\n``  every HEARTBEAT_SECS seconds (SSE comment).

        Stops when *request_disconnected* is set.
        """
        queue = event_broadcaster.subscribe(tenant_id)
        try:
            while not request_disconnected.is_set():
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECS)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            event_broadcaster.unsubscribe(queue)


# Single-element list used as a mutable cell so register_transport() can swap the
# active transport without a `global` rebind.
_transport_holder: list[EventTransport] = [_InMemoryEventTransport()]


def register_transport(transport: EventTransport) -> None:
    """Replace the active event transport."""
    _transport_holder[0] = transport


async def notify_clients(
    table: str, method: str, record_id: object, tenant_id: object, source: str = "unknown"
) -> None:
    """Broadcast a data-change event to all connected UI clients for *tenant_id*.

    Args:
        table:     Entity type that changed (e.g. "batch", "device", "gravity").
        method:    Operation: "create", "update", or "delete".
        record_id: Primary key of the affected record (UUID or int).
        tenant_id: Tenant the event belongs to; only its subscribers receive it.
        source:    Why the entity changed (e.g. "batch", "pour", "temperature").
    """
    await _transport_holder[0].publish(
        EventEnvelope(table=table, method=method, record_id=record_id,
                      tenant_id=tenant_id, source=source)
    )


def subscribe(
    tenant_id: object, request_disconnected: asyncio.Event
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted strings for a connected client.

    Delegates to the currently-registered transport's `subscribe(...)`.
    """
    return _transport_holder[0].subscribe(tenant_id, request_disconnected)
