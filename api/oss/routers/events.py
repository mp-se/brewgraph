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

from fastapi import Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRouter

from core.events import subscribe
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.extensions.tenant import oss_tenant_provider

logger = logging.getLogger(__name__)

# `api_key_auth` is declared here explicitly. It is NOT inherited from the system
# router any more — dropping it would silently make the stream anonymous.
router = APIRouter(tags=["events"], dependencies=[Depends(api_key_auth)])


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
    disconnected = asyncio.Event()

    async def _check_disconnect() -> None:
        while not disconnected.is_set():
            if await request.is_disconnected():
                disconnected.set()
                break
            await asyncio.sleep(1)

    asyncio.create_task(_check_disconnect())

    return StreamingResponse(
        subscribe(tenant_id, disconnected),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
