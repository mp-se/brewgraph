# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Pressure ingestion — PressureMon payloads."""
from fastapi.responses import Response
from starlette.exceptions import HTTPException

from core.enums import IngestionErrorReason
from core.events import notify_clients
from oss.extensions.tenant import DEFAULT_TENANT_ID
from oss.jobs.pressure_forward import enqueue_forward

from ._shared import IngestContext, _check_device_request_quota


async def _process_pressure(payload: dict, ctx: IngestContext) -> Response:
    """Core pressure processing logic (shared across endpoints)."""
    token = payload.get("token") or None
    _check_device_request_quota(token)
    device = ctx.ingestion_svc.resolve_device(token, payload.get("id"), "pressuremon")
    if device is None:
        ctx.ingestion_svc.log_ingestion_error(
            ctx.client_ip, "pressuremon", IngestionErrorReason.UNKNOWN_TOKEN,
            "Token and compatible device ID not found — device not registered",
        )
        raise HTTPException(status_code=401, detail="Device not registered")

    try:
        with ctx.throttle_budget(device.id, ctx.auth.ingest_interval_seconds):
            ctx.ingestion_svc.ingest_pressure(device, payload)
    except HTTPException as exc:
        if exc.status_code == 429:
            # Synchronous for the same reason as gravity.py's _process_gravity twin above.
            ctx.ingestion_svc.log_ingestion_error(
                ctx.client_ip, "pressuremon", IngestionErrorReason.RATE_LIMITED_DEVICE,
                "Reading dropped — device is inside its throttle interval",
                None, device,
            )
        raise

    # A pressuremon is mounted on either a vessel or a batch — report whichever
    # entity the reading actually landed on, so clients refresh just that one.
    if device.vessel_id is not None:
        ctx.background_tasks.add_task(notify_clients, "vessel", "create", device.vessel_id,
                                       DEFAULT_TENANT_ID, source="pressure")
    else:
        ctx.background_tasks.add_task(notify_clients, "batch", "create", device.batch_id,
                                       DEFAULT_TENANT_ID, source="pressure")
    ctx.background_tasks.add_task(enqueue_forward, device.id, DEFAULT_TENANT_ID)
    return Response(content="", status_code=200)
