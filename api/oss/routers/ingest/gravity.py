# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Gravity ingestion — GravityMon and iSpindel payloads."""
from fastapi.responses import Response
from starlette.exceptions import HTTPException

from core.enums import IngestionErrorReason
from core.events import notify_clients
from oss.extensions.tenant import DEFAULT_TENANT_ID
from oss.jobs.gravity_forward import enqueue_forward

from ._shared import IngestContext, _check_device_request_quota


async def _process_gravity(
    payload: dict,
    ctx: IngestContext,
    device_type: str = "gravitymon",
) -> Response:
    """Core gravity processing logic (shared across endpoints)."""
    token = payload.get("token") or None
    _check_device_request_quota(token)
    device_id = payload.get("ID") if device_type == "ispindel" else payload.get("id")
    device = ctx.ingestion_svc.resolve_device(
        token, str(device_id) if device_id is not None else None, device_type
    )
    if device is None:
        ctx.ingestion_svc.log_ingestion_error(
            ctx.client_ip, device_type, IngestionErrorReason.UNKNOWN_TOKEN,
            "Token and compatible device ID not found — device not registered",
        )
        raise HTTPException(status_code=401, detail="Device not registered")

    try:
        with ctx.throttle_budget(device.id, ctx.auth.ingest_interval_seconds):
            batch, reading = ctx.ingestion_svc.ingest_gravity(device, device_type, payload)
    except HTTPException as exc:
        if exc.status_code == 429:
            # Called synchronously (not via background_tasks): this except re-raises,
            # and the app's global HTTPException handler builds a fresh JSONResponse
            # with no background tasks attached, so anything queued here would never
            # actually run — see the same fix's twin in pressure.py's _process_pressure.
            ctx.ingestion_svc.log_ingestion_error(
                ctx.client_ip, device_type, IngestionErrorReason.RATE_LIMITED_DEVICE,
                "Reading dropped — device is inside its throttle interval",
                None, device,
            )
        raise
    # Evaluate dry hop triggers on every new gravity reading
    ctx.background_tasks.add_task(
        ctx.ingestion_svc.trigger_dry_hops, batch.id, reading.gravity
    )
    ctx.background_tasks.add_task(notify_clients, "batch", "create", batch.id,
                                   DEFAULT_TENANT_ID, source="gravity")
    ctx.background_tasks.add_task(enqueue_forward, device.id, DEFAULT_TENANT_ID)
    return Response(content="", status_code=200)
