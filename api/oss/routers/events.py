# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Real-time event stream endpoint.

Mounted with **no prefix**: this stream lives at `GET /events`, outside `/api`, and
the frontend fetches that path directly. nginx must proxy `/events` (with buffering
off), not `/api/events`.
"""
import asyncio
import logging

from collections import Counter

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from fastapi.routing import APIRouter

from core.config import get_settings
from core.events import subscribe
from core.utils import get_client_ip
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.extensions.tenant import oss_tenant_provider

logger = logging.getLogger(__name__)

# `api_key_auth` is declared here explicitly. It is NOT inherited from the system
# router any more — dropping it would silently make the stream anonymous.
router = APIRouter(tags=["events"], dependencies=[Depends(api_key_auth)])


# Open SSE connections by client IP. The event loop is single-threaded, so plain
# counter updates between awaits need no lock. Limits are per process, like the
# subscriber registry they protect.
_open_by_ip: Counter = Counter()


def _acquire_slot(client_ip: str) -> None:
    """Reserve a connection slot, or raise 429 when the per-IP or total limit is reached."""
    settings = get_settings()
    per_ip, total = settings.sse_max_connections_per_ip, settings.sse_max_connections
    if (per_ip and _open_by_ip[client_ip] >= per_ip) or (
            total and sum(_open_by_ip.values()) >= total):
        logger.warning("Rejected /events connection from %s: too many open streams", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many open event streams",
            headers={"Retry-After": "30"},
        )
    _open_by_ip[client_ip] += 1


def _release_slot(client_ip: str) -> None:
    """Free a slot reserved by `_acquire_slot`."""
    _open_by_ip[client_ip] -= 1
    if _open_by_ip[client_ip] <= 0:
        del _open_by_ip[client_ip]


@router.get(
    "/events",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": (
                "Server-Sent Events stream. Each event is a JSON object "
                "`{method, table, source, id}`; the connection stays open."
            ),
        }
    },
)
async def event_stream(
    request: Request,
    tenant_id=Depends(oss_tenant_provider),
) -> StreamingResponse:
    """Real-time event stream. Clients receive {method, table, source, id} on every change.

    Uses Server-Sent Events (text/event-stream) over a plain authenticated GET
    request instead of a WebSocket, so the same `api_key_auth` header check used
    by every other endpoint applies here too.
    """
    client_ip = get_client_ip(request)
    _acquire_slot(client_ip)
    released = False

    def release() -> None:
        nonlocal released
        if not released:
            released = True
            _release_slot(client_ip)

    disconnected = asyncio.Event()

    async def _check_disconnect() -> None:
        while not disconnected.is_set():
            if await request.is_disconnected():
                disconnected.set()
                break
            await asyncio.sleep(1)

    asyncio.create_task(_check_disconnect())

    async def stream():
        try:
            async for chunk in subscribe(tenant_id, disconnected):
                yield chunk
        finally:
            release()

    return StreamingResponse(
        stream(),
        background=BackgroundTask(release),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
