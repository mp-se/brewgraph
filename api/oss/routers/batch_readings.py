# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Reading sub-resources of a batch: gravity, pressure and temperature.

Split out of `batches.py`, which had grown past what one module should carry
(~990 lines bundling ~8 sub-resource concerns). The seam follows the OpenAPI
grouping — these are the `batches - gravity`, `batches - pressure` and
`batches - temperature` operations — and they share one shape: list, chart,
create, bulk-insert, patch, all keyed on a batch id.

Mounted on the same `/api/batches` prefix, so the URL layout is unchanged.
"""
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, List, Literal, Optional

from fastapi import BackgroundTasks, Body, Depends, Query, Request
from fastapi.routing import APIRouter
from starlette.exceptions import HTTPException

from core.enums import BatchStatus
from core.events import notify_clients
from core.openapi_tags import (BATCHES_GRAVITY, BATCHES_PRESSURE,
                               BATCHES_TEMPERATURE)
from core.schemas.errors import NOT_FOUND_RESPONSES, ErrorResponse
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.extensions.retention import \
    oss_retention_provider as get_retention_cutoff
from oss.extensions.tenant import DEFAULT_TENANT_ID
from oss.schemas._page import CursorPage, encode_cursor, parse_cursor
from oss.schemas.gravity_reading import GravityChartPoint
from oss.schemas.pressure_reading import PressureChartPoint
from oss.schemas.registry import get as _s
from oss.schemas.temp_reading import (TempChartPoint, TempReadingCreate,
                                      TempReadingResponse, TempReadingUpdate)
from oss.services import (BatchService, GravityService, PressureService,
                          get_batch_service, get_gravity_service,
                          get_pressure_service, get_temp_service)
from oss.services.temp_reading import TempService

GravityReadingCreate   = _s("GravityReadingCreate")
GravityReadingUpdate   = _s("GravityReadingUpdate")
GravityReadingResponse = _s("GravityReadingResponse")
PressureReadingCreate   = _s("PressureReadingCreate")
PressureReadingUpdate   = _s("PressureReadingUpdate")
PressureReadingResponse = _s("PressureReadingResponse")


logger = logging.getLogger(__name__)


def _active_batch(
    request: Request,
    batch_id: uuid.UUID,
    batch_service: BatchService = Depends(get_batch_service),
):
    """Reject nested reading access for missing or soft-deleted batches, and writes to archived ones.

    An archived batch keeps its history: its readings stay listable and chartable, which is also
    what lets a backup export them. Archived is otherwise read-only, so reading writes are rejected
    through this parent, matching `BaseService._validate_batch_exists`, which the manual/bulk
    create paths also route through.
    """
    batch = batch_service.get(batch_id)
    archived_write = (
        request.method not in ("GET", "HEAD")
        and batch is not None
        and batch.status == BatchStatus.ARCHIVED.value
    )
    if batch is None or batch.deleted_at is not None or archived_write:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


router = APIRouter(
    prefix="/api/batches", dependencies=[Depends(api_key_auth), Depends(_active_batch)]
)


# ---------------------------------------------------------------------------
# Gravity sub-resource
# ---------------------------------------------------------------------------

@router.get(
    "/{batch_id}/gravity",
    tags=[BATCHES_GRAVITY],
    response_model=CursorPage[GravityReadingResponse],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def list_gravity(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    batch_id: uuid.UUID,
    limit: int = Query(500, ge=1, le=2000),
    cursor: Optional[str] = Query(None),
    include_excluded: bool = Query(False, alias="includeExcluded"),
    gravity_service: GravityService = Depends(get_gravity_service),
    retention_cutoff: Optional[datetime] = Depends(get_retention_cutoff),
) -> Any:
    """List gravity readings for a batch (cursor-paginated, oldest-first)."""
    logger.info("Endpoint GET /batches/%s/gravity limit=%d cursor=%s", batch_id, limit, cursor)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    items, has_more = gravity_service.search_by_batch_id_cursor(
        batch_id, limit=limit, cursor=cursor_dt,
        include_excluded=include_excluded, retention_cutoff=retention_cutoff,
    )
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.get(
    "/{batch_id}/gravity/chart",
    tags=[BATCHES_GRAVITY],
    response_model=List[GravityChartPoint],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def gravity_chart(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    batch_id: uuid.UUID,
    resolution: Literal["raw", "hourly", "daily"] = Query("raw"),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    gravity_service: GravityService = Depends(get_gravity_service),
    retention_cutoff: Optional[datetime] = Depends(get_retention_cutoff),
) -> List[Any]:
    """Return chart data for a batch's gravity readings."""
    logger.info("Endpoint GET /batches/%s/gravity/chart", batch_id)
    effective_from = from_dt or retention_cutoff
    return gravity_service.chart_data(
        batch_id, resolution=resolution, from_dt=effective_from, to_dt=to_dt
    )


@router.post(
    "/{batch_id}/gravity",
    tags=[BATCHES_GRAVITY],
    response_model=GravityReadingResponse,
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def create_gravity_reading(
    batch_id: uuid.UUID,
    body: GravityReadingCreate,
    background_tasks: BackgroundTasks,
    gravity_service: GravityService = Depends(get_gravity_service),
) -> Any:
    """Log a single manual gravity reading (no device required)."""
    logger.info("Endpoint POST /batches/%s/gravity", batch_id)
    body.batch_id = batch_id
    body.device_id = None
    if body.created_at is None:
        body.created_at = datetime.now(UTC)
    reading = gravity_service.create(body)
    background_tasks.add_task(notify_clients, "batch", "create", batch_id,
                                   DEFAULT_TENANT_ID, source="gravity")
    return reading


@router.post(
    "/{batch_id}/gravity/bulk",
    tags=[BATCHES_GRAVITY],
    response_model=List[GravityReadingResponse],
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def bulk_insert_gravity(
    batch_id: uuid.UUID,
    readings: List[GravityReadingCreate] = Body(..., max_length=1000),
    gravity_service: GravityService = Depends(get_gravity_service),
) -> List[Any]:
    """Bulk insert gravity readings (e.g. for restore).

    Unlike the single-reading POST above, `device_id` is not stripped here: this
    endpoint's caller is a trusted restore flow re-attaching readings to devices it
    just recreated, not a client claiming device provenance for a manual entry.
    """
    logger.info("Endpoint POST /batches/%s/gravity/bulk (%d records)", batch_id, len(readings))
    now = datetime.now(UTC)
    for r in readings:
        r.batch_id = batch_id
        if r.created_at is None:
            r.created_at = now
    return gravity_service.create_list(readings)


@router.patch(
    "/{batch_id}/gravity/{reading_id}",
    tags=[BATCHES_GRAVITY],
    response_model=GravityReadingResponse,
    responses={404: {"model": ErrorResponse, "description": "Reading not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def update_gravity_reading(
    batch_id: uuid.UUID,
    reading_id: int,
    update: GravityReadingUpdate,
    gravity_service: GravityService = Depends(get_gravity_service),
) -> Any:
    """Update a single gravity reading."""
    logger.info("Endpoint PATCH /batches/%s/gravity/%s", batch_id, reading_id)
    updated = gravity_service.update_for_batch(batch_id, reading_id, update)
    if updated is None:
        raise HTTPException(status_code=404, detail="Gravity reading not found")
    return updated


# ---------------------------------------------------------------------------
# Pressure sub-resource
# ---------------------------------------------------------------------------

@router.get(
    "/{batch_id}/pressure",
    tags=[BATCHES_PRESSURE],
    response_model=CursorPage[PressureReadingResponse],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def list_pressure(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    batch_id: uuid.UUID,
    limit: int = Query(500, ge=1, le=2000),
    cursor: Optional[str] = Query(None),
    include_excluded: bool = Query(False, alias="includeExcluded"),
    pressure_service: PressureService = Depends(get_pressure_service),
    retention_cutoff: Optional[datetime] = Depends(get_retention_cutoff),
) -> Any:
    """List pressure readings for a batch (cursor-paginated, oldest-first)."""
    logger.info("Endpoint GET /batches/%s/pressure limit=%d cursor=%s", batch_id, limit, cursor)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    items, has_more = pressure_service.search_by_batch_id_cursor(
        batch_id, limit=limit, cursor=cursor_dt,
        include_excluded=include_excluded, retention_cutoff=retention_cutoff,
    )
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.get(
    "/{batch_id}/pressure/chart",
    tags=[BATCHES_PRESSURE],
    response_model=List[PressureChartPoint],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def pressure_chart(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    batch_id: uuid.UUID,
    resolution: Literal["raw", "hourly", "daily"] = Query("raw"),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    pressure_service: PressureService = Depends(get_pressure_service),
    retention_cutoff: Optional[datetime] = Depends(get_retention_cutoff),
) -> List[Any]:
    """Return chart data for a batch's pressure readings."""
    logger.info("Endpoint GET /batches/%s/pressure/chart", batch_id)
    effective_from = from_dt or retention_cutoff
    return pressure_service.chart_data(
        batch_id, resolution=resolution, from_dt=effective_from, to_dt=to_dt
    )


@router.post(
    "/{batch_id}/pressure",
    tags=[BATCHES_PRESSURE],
    response_model=PressureReadingResponse,
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def create_pressure_reading(
    batch_id: uuid.UUID,
    body: PressureReadingCreate,
    background_tasks: BackgroundTasks,
    pressure_service: PressureService = Depends(get_pressure_service),
) -> Any:
    """Log a single manual pressure reading on a batch (no device required)."""
    logger.info("Endpoint POST /batches/%s/pressure", batch_id)
    body.batch_id = batch_id
    body.vessel_id = None
    body.device_id = None
    if body.created_at is None:
        body.created_at = datetime.now(UTC)
    reading = pressure_service.create(body)
    background_tasks.add_task(notify_clients, "batch", "create", batch_id,
                                   DEFAULT_TENANT_ID, source="pressure")
    return reading


@router.post(
    "/{batch_id}/pressure/bulk",
    tags=[BATCHES_PRESSURE],
    response_model=List[PressureReadingResponse],
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def bulk_insert_pressure(
    batch_id: uuid.UUID,
    readings: List[PressureReadingCreate] = Body(..., max_length=1000),
    pressure_service: PressureService = Depends(get_pressure_service),
) -> List[Any]:
    """Bulk insert pressure readings (e.g. for restore).

    Unlike the single-reading POST above, `device_id` is not stripped here: this
    endpoint's caller is a trusted restore flow re-attaching readings to devices it
    just recreated, not a client claiming device provenance for a manual entry.
    `vessel_id` is still cleared — restore doesn't relink it.
    """
    logger.info("Endpoint POST /batches/%s/pressure/bulk (%d records)", batch_id, len(readings))
    now = datetime.now(UTC)
    for r in readings:
        r.batch_id = batch_id
        r.vessel_id = None
        if r.created_at is None:
            r.created_at = now
    return pressure_service.create_list(readings)


@router.patch(
    "/{batch_id}/pressure/{reading_id}",
    tags=[BATCHES_PRESSURE],
    response_model=PressureReadingResponse,
    responses={404: {"model": ErrorResponse, "description": "Reading not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def update_pressure_reading(
    batch_id: uuid.UUID,
    reading_id: int,
    update: PressureReadingUpdate,
    pressure_service: PressureService = Depends(get_pressure_service),
) -> Any:
    """Update a single pressure reading."""
    logger.info("Endpoint PATCH /batches/%s/pressure/%s", batch_id, reading_id)
    updated = pressure_service.update_for_owner(reading_id, "batch_id", batch_id, update)
    if updated is None:
        raise HTTPException(status_code=404, detail="Pressure reading not found")
    return updated


# ---------------------------------------------------------------------------
# Temperature sub-resource
# ---------------------------------------------------------------------------

@router.get(
    "/{batch_id}/temp",
    tags=[BATCHES_TEMPERATURE],
    response_model=CursorPage[TempReadingResponse],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def list_temp(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    batch_id: uuid.UUID,
    limit: int = Query(500, ge=1, le=2000),
    cursor: Optional[str] = Query(None),
    include_excluded: bool = Query(False, alias="includeExcluded"),
    temp_service: TempService = Depends(get_temp_service),
    retention_cutoff: Optional[datetime] = Depends(get_retention_cutoff),
) -> Any:
    """List temperature readings for a batch (cursor-paginated, oldest-first)."""
    logger.info("Endpoint GET /batches/%s/temp limit=%d cursor=%s", batch_id, limit, cursor)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    items, has_more = temp_service.search_by_batch_id_cursor(
        batch_id, limit=limit, cursor=cursor_dt,
        include_excluded=include_excluded, retention_cutoff=retention_cutoff,
    )
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.get(
    "/{batch_id}/temp/chart",
    tags=[BATCHES_TEMPERATURE],
    response_model=List[TempChartPoint],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def batch_temp_chart(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    batch_id: uuid.UUID,
    resolution: Literal["raw", "hourly", "daily"] = Query("raw"),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    temp_service: TempService = Depends(get_temp_service),
    retention_cutoff: Optional[datetime] = Depends(get_retention_cutoff),
) -> List[Any]:
    """Return chart data for a batch's temperature readings."""
    logger.info("Endpoint GET /batches/%s/temp/chart", batch_id)
    effective_from = from_dt or retention_cutoff
    return temp_service.chart_data(
        batch_id, resolution=resolution, from_dt=effective_from, to_dt=to_dt
    )


@router.post(
    "/{batch_id}/temp",
    tags=[BATCHES_TEMPERATURE],
    response_model=TempReadingResponse,
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def create_batch_temp(
    batch_id: uuid.UUID,
    reading: TempReadingCreate,
    batch_service: BatchService = Depends(get_batch_service),
    temp_service: TempService = Depends(get_temp_service),
) -> Any:
    """Log a manual temperature reading for a batch."""
    logger.info("Endpoint POST /batches/%s/temp", batch_id)
    batch = batch_service.get(batch_id)
    if batch is None or batch.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Batch not found")
    reading.batch_id = batch_id
    reading.vessel_id = None
    reading.device_id = None
    if reading.created_at is None:
        reading.created_at = datetime.now(UTC)
    return temp_service.create(reading)


@router.post(
    "/{batch_id}/temp/bulk",
    tags=[BATCHES_TEMPERATURE],
    response_model=List[TempReadingResponse],
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def bulk_insert_temp(
    batch_id: uuid.UUID,
    readings: List[TempReadingCreate] = Body(..., max_length=1000),
    temp_service: TempService = Depends(get_temp_service),
) -> List[Any]:
    """Bulk insert temperature readings (e.g. for restore).

    Unlike the single-reading POST above, `device_id` is not stripped here: this
    endpoint's caller is a trusted restore flow re-attaching readings to devices it
    just recreated, not a client claiming device provenance for a manual entry.
    `vessel_id` is still cleared — restore doesn't relink it.
    """
    logger.info("Endpoint POST /batches/%s/temp/bulk (%d records)", batch_id, len(readings))
    now = datetime.now(UTC)
    for r in readings:
        r.batch_id = batch_id
        r.vessel_id = None
        if r.created_at is None:
            r.created_at = now
    return temp_service.create_list(readings)


@router.patch(
    "/{batch_id}/temp/{reading_id}",
    tags=[BATCHES_TEMPERATURE],
    response_model=TempReadingResponse,
    responses={404: {"model": ErrorResponse, "description": "Reading not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def update_temp_reading(
    batch_id: uuid.UUID,
    reading_id: int,
    update: TempReadingUpdate,
    temp_service: TempService = Depends(get_temp_service),
) -> Any:
    """Update a single temperature reading."""
    logger.info("Endpoint PATCH /batches/%s/temp/%s", batch_id, reading_id)
    updated = temp_service.update_for_batch(batch_id, reading_id, update)
    if updated is None:
        raise HTTPException(status_code=404, detail="Temp reading not found")
    return updated
