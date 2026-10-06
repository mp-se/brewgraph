# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Chamber/temp ingestion — chamber controller payloads and setpoint response.

`__init__.py`'s dedicated `/ingest/chamber` route (`ingest_temp`) delegates straight
into `_process_chamber` below, the same core logic `/ingest/dispatch` uses for
chamber payloads. The two used to be near-duplicate bodies, and only the dispatch
path called `_check_device_request_quota` before writing — a device could get an
unthrottled write simply by using `/ingest/chamber` instead. Collapsing `ingest_temp`
onto `_process_chamber` closed that gap by construction: there is now only one body,
and it always throttles.
"""
from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from core.enums import IngestionErrorReason
from core.events import notify_clients
from oss.extensions.tenant import DEFAULT_TENANT_ID
from oss.jobs.temp_forward import enqueue_forward

from ._shared import IngestContext, _check_device_request_quota


def _notify_temp(background_tasks: BackgroundTasks, device) -> None:
    """Emit the temperature event for whichever entity the chamber reading landed on.

    A chamber controller is attached to either a storage vessel or a batch. Every
    event carries the affected entity and its ID (see the `{method, table, source,
    id}` shape documented on the event stream router), so resolve that here rather
    than broadcasting an ID-less event clients must guess at.
    """
    if getattr(device, "vessel_id", None) is not None:
        background_tasks.add_task(notify_clients, "vessel", "create", device.vessel_id,
                                   DEFAULT_TENANT_ID, source="temperature")
    elif getattr(device, "batch_id", None) is not None:
        background_tasks.add_task(notify_clients, "batch", "create", device.batch_id,
                                   DEFAULT_TENANT_ID, source="temperature")


def _parse_temp(value, unit: str) -> float:
    """Parse and convert a temperature value to Celsius."""
    try:
        t = float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="temperature must be a number") from exc
    if unit.upper() == "F":
        t = (t - 32) * 5 / 9
    return t


async def _process_chamber(payload: dict, ctx: IngestContext) -> Response:
    """Core chamber/temp processing logic (shared across endpoints)."""
    token = payload.get("token") or None
    _check_device_request_quota(token)
    temp_unit = payload.get("temp_units", "C")

    raw_beer = payload.get("beer_temperature")
    raw_fridge = payload.get("fridge_temperature")
    temperature = _parse_temp(raw_beer, temp_unit) if raw_beer is not None else None
    fridge_temp = _parse_temp(raw_fridge, temp_unit) if raw_fridge is not None else None

    try:
        device = ctx.ingestion_svc.write_temp(
            token, temperature, fridge_temp=fridge_temp, rssi=payload.get("rssi"),
            battery=payload.get("battery"),
            device_id=payload.get("id") or None,
        )
    except HTTPException:
        ctx.ingestion_svc.log_ingestion_error(
            ctx.client_ip, "chamber", IngestionErrorReason.UNKNOWN_TOKEN,
            "Neither token nor id resolved — vessel or device not registered",
        )
        raise
    _notify_temp(ctx.background_tasks, device)
    ctx.background_tasks.add_task(enqueue_forward, device.id, DEFAULT_TENANT_ID)
    setpoint = ctx.ingestion_svc.resolve_chamber_mode(
        device, payload.get("local_timestamp"), payload.get("timezone")
    )
    return JSONResponse(content=setpoint, status_code=200)
