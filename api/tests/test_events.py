# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for core/events.py — EventBroadcaster, notify_clients, and subscribe."""
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from core.events import EventBroadcaster, notify_clients, subscribe

# ---------------------------------------------------------------------------
# EventBroadcaster
# ---------------------------------------------------------------------------

class TestEventBroadcaster:
    """Tests for EventBroadcaster subscribe/unsubscribe/broadcast."""

    def _broadcaster(self):
        return EventBroadcaster()

    def test_subscribe_registers_queue(self):
        """subscribe() returns a queue that is tracked internally."""
        b = self._broadcaster()
        b.subscribe(uuid.uuid4())
        assert b.subscriber_count() == 1

    def test_unsubscribe_removes_queue(self):
        """unsubscribe() removes a previously registered queue."""
        b = self._broadcaster()
        queue = b.subscribe(uuid.uuid4())
        b.unsubscribe(queue)
        assert b.subscriber_count() == 0

    def test_unsubscribe_unknown_queue_is_noop(self):
        """unsubscribe() on an unregistered queue does not raise."""
        b = self._broadcaster()
        b.unsubscribe(asyncio.Queue())  # must not raise

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_subscribers_of_same_tenant(self):
        """broadcast() puts the message onto every subscriber queue for that tenant."""
        b = self._broadcaster()
        tenant_id = uuid.uuid4()
        q1, q2 = b.subscribe(tenant_id), b.subscribe(tenant_id)
        await b.broadcast(tenant_id, "hello")
        assert q1.get_nowait() == "hello"
        assert q2.get_nowait() == "hello"

    @pytest.mark.asyncio
    async def test_broadcast_isolates_by_tenant(self):
        """broadcast() only delivers to subscribers registered for the matching tenant_id."""
        b = self._broadcaster()
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        assert tenant_a != tenant_b

        queue_a = b.subscribe(tenant_a)
        queue_b = b.subscribe(tenant_b)

        await b.broadcast(tenant_a, "hello-a")

        assert queue_a.get_nowait() == "hello-a"
        with pytest.raises(asyncio.QueueEmpty):
            queue_b.get_nowait()

    @pytest.mark.asyncio
    async def test_broadcast_empty_subscribers_does_nothing(self):
        """broadcast() completes without error when there are no subscribers."""
        b = self._broadcaster()
        await b.broadcast(uuid.uuid4(), "msg")  # must not raise

    @pytest.mark.asyncio
    async def test_broadcast_isolates_full_subscriber_queue(self):
        """A full subscriber queue is skipped without blocking the rest of the fan-out."""
        b = self._broadcaster()
        tenant_id = uuid.uuid4()
        full_subscriber = b.subscribe(tenant_id)
        full_subscriber.put_nowait = lambda _msg: (_ for _ in ()).throw(asyncio.QueueFull())
        healthy = b.subscribe(tenant_id)

        await b.broadcast(tenant_id, "hello")  # must not raise despite the full queue

        assert healthy.get_nowait() == "hello"

    def test_subscriber_queue_is_bounded(self):
        """Subscriber queues must have a maxsize.

        With an unbounded queue (asyncio.Queue()'s default) the QueueFull branch in
        broadcast() is dead code and a stalled client accumulates events forever.
        """
        b = self._broadcaster()
        queue = b.subscribe(uuid.uuid4())
        assert queue.maxsize > 0

    @pytest.mark.asyncio
    async def test_slow_subscriber_drops_events_instead_of_growing(self):
        """A subscriber that never reads stops at maxsize; others keep receiving.

        Exercises the real queue rather than a monkeypatched put_nowait, so this
        fails if the bound is ever removed.
        """
        b = self._broadcaster()
        tenant_id = uuid.uuid4()
        stalled = b.subscribe(tenant_id)
        healthy = b.subscribe(tenant_id)

        for _ in range(stalled.maxsize + 50):
            await b.broadcast(tenant_id, "event")
            healthy.get_nowait()  # healthy client keeps draining

        assert stalled.qsize() == stalled.maxsize
        assert healthy.qsize() == 0


# ---------------------------------------------------------------------------
# notify_clients
# ---------------------------------------------------------------------------

class TestNotifyClients:
    """Tests for the notify_clients helper."""

    @pytest.mark.asyncio
    async def test_broadcasts_json_payload(self):
        """notify_clients broadcasts a JSON-encoded payload via event_broadcaster."""
        tenant_id = uuid.uuid4()
        with patch("core.events.event_broadcaster") as mock_broadcaster:
            mock_broadcaster.broadcast = _async_mock()
            await notify_clients("batch", "create", 42, tenant_id, source="batch")

        mock_broadcaster.broadcast.assert_awaited_once()
        call_tenant_id, payload_str = mock_broadcaster.broadcast.call_args.args
        assert call_tenant_id == tenant_id
        payload = json.loads(payload_str)
        assert payload == {"method": "create", "table": "batch", "source": "batch", "id": "42"}

    @pytest.mark.asyncio
    async def test_broadcasts_non_string_record_id_as_string(self):
        """notify_clients coerces non-string record_id values (e.g. UUID) to str."""
        tenant_id = uuid.uuid4()
        with patch("core.events.event_broadcaster") as mock_broadcaster:
            mock_broadcaster.broadcast = _async_mock()
            await notify_clients("device", "delete", uuid.uuid4(), tenant_id, source="device")

        payload = json.loads(mock_broadcaster.broadcast.call_args.args[1])
        assert payload["method"] == "delete"
        assert isinstance(payload["id"], str)

    @pytest.mark.asyncio
    async def test_source_defaults_to_unknown(self):
        """notify_clients defaults source to 'unknown' when the caller omits it."""
        tenant_id = uuid.uuid4()
        with patch("core.events.event_broadcaster") as mock_broadcaster:
            mock_broadcaster.broadcast = _async_mock()
            await notify_clients("tap", "update", 1, tenant_id)

        payload = json.loads(mock_broadcaster.broadcast.call_args.args[1])
        assert payload["source"] == "unknown"


def _async_mock(*, side_effect=None):
    return AsyncMock(side_effect=side_effect)


# ---------------------------------------------------------------------------
# subscribe
# ---------------------------------------------------------------------------

class TestSubscribe:
    """Tests for the subscribe() SSE generator."""

    @pytest.mark.asyncio
    async def test_yields_data_event_for_broadcast_message(self):
        """subscribe() yields an SSE data: line for a broadcast message."""
        tenant_id = uuid.uuid4()
        disconnected = asyncio.Event()
        gen = subscribe(tenant_id, disconnected)

        anext_task = asyncio.ensure_future(gen.__anext__())
        await asyncio.sleep(0)  # let the generator run up to queue.get() and register
        await notify_clients("batch", "update", "1", tenant_id, source="batch")
        chunk = await anext_task

        assert chunk.startswith("data: ")
        payload = json.loads(chunk[len("data: "):].strip())
        assert payload == {"method": "update", "table": "batch", "source": "batch", "id": "1"}

        disconnected.set()
        await gen.aclose()

    @pytest.mark.asyncio
    async def test_stops_when_disconnected_is_set(self):
        """subscribe() generator terminates once request_disconnected is set."""
        disconnected = asyncio.Event()
        disconnected.set()
        gen = subscribe(uuid.uuid4(), disconnected)

        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()
