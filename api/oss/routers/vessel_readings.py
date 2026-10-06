# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Temperature and pressure reading sub-resources of a storage vessel.

Split out of `vessels.py` (was 613 lines importing six services across vessel
lifecycle, pours, readings, and predictions) — mirrors `batch_readings.py`'s split of
the same gravity/pressure/temperature cluster out of `batches.py`. Vessels carry no
gravity sub-resource (kegs and bottles don't take a gravity reading), so this module
holds pressure and temperature only.

Mounted on the same `/api/vessels` prefix, so the URL layout is unchanged.
"""
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, List, Literal, Optional

from fastapi import BackgroundTasks, Body, Depends, Query, Request
from fastapi.routing import APIRouter
from starlette.exceptions import HTTPException

from core.events import notify_clients
from core.openapi_tags import VESSELS_PRESSURE, VESSELS_TEMPERATURE
from core.schemas.errors import NOT_FOUND_RESPONSES, ErrorResponse
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.extensions.retention import \
    oss_retention_provider as get_retention_cutoff
from oss.extensions.tenant import DEFAULT_TENANT_ID
from oss.schemas._page import CursorPage, encode_cursor, parse_cursor
from oss.schemas.pressure_reading import (PressureChartPoint,
                                          PressureReadingCreate,
                                          PressureReadingResponse,
                                          PressureReadingUpdate)
from oss.schemas.temp_reading import (TempChartPoint, TempReadingCreate,
                                      TempReadingResponse, TempReadingUpdate)
from oss.services import (get_pressure_service, get_temp_service,
                          get_vessel_service)
from oss.services.pressure import PressureService
from oss.services.storage_vessel import StorageVesselService
from oss.services.temp_reading import TempService

logger = logging.getLogger(__name__)


def _active_vessel(
    request: Request,
    vessel_id: Optional[uuid.UUID] = None,
    vessel_service: StorageVesselService = Depends(get_vessel_service),
):
    """Reject nested reading access for missing or soft-deleted vessels.

    Duplicated verbatim from `vessels.py` — see that module for the full rationale.
    Each split-out router needs the identical guard at its own mount point, the same
    way `batch_readings.py` duplicates `_active_batch` rather than sharing one
    definition across router modules.
    """
    if vessel_id is None or request.url.path.endswith("/restore"):
        return None
    vessel = vessel_service.get(vessel_id)
    if vessel is None or vessel.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return vessel


router = APIRouter(
    prefix="/api/vessels", dependencies=[Depends(api_key_auth), Depends(_active_vessel)]
)


# ---------------------------------------------------------------------------
# Temperature sub-resource
# ---------------------------------------------------------------------------

@router.get(
    "/{vessel_id}/temp",
    tags=[VESSELS_TEMPERATURE],
    response_model=CursorPage[TempReadingResponse],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def list_vessel_temp(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    vessel_id: uuid.UUID,
    limit: int = Query(500, ge=1, le=2000),
    cursor: Optional[str] = Query(None),
    include_excluded: bool = Query(False, alias="includeExcluded"),
    temp_service: TempService = Depends(get_temp_service),
    retention_cutoff: Optional[datetime] = Depends(get_retention_cutoff),
) -> Any:
    """List temperature readings for a vessel (cursor-paginated, oldest-first)."""
    logger.info("Endpoint GET /vessels/%s/temp limit=%d cursor=%s", vessel_id, limit, cursor)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    items, has_more = temp_service.search_by_vessel_id_cursor(
        vessel_id, limit=limit, cursor=cursor_dt,
        include_excluded=include_excluded, retention_cutoff=retention_cutoff,
    )
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.get(
    "/{vessel_id}/temp/chart",
    tags=[VESSELS_TEMPERATURE],
    response_model=List[TempChartPoint],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def vessel_temp_chart(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    vessel_id: uuid.UUID,
    resolution: Literal["raw", "hourly", "daily"] = Query("raw"),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    temp_service: TempService = Depends(get_temp_service),
    retention_cutoff: Optional[datetime] = Depends(get_retention_cutoff),
) -> Any:
    """Return temperature chart data for a vessel."""
    logger.info("Endpoint GET /vessels/%s/temp/chart", vessel_id)
    effective_from = from_dt or retention_cutoff
    return temp_service.chart_data_for_vessel(
        vessel_id, resolution=resolution, from_dt=effective_from, to_dt=to_dt
    )


@router.post(
    "/{vessel_id}/temp",
    tags=[VESSELS_TEMPERATURE],
    response_model=TempReadingResponse,
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def create_vessel_temp_reading(
    vessel_id: uuid.UUID,
    body: TempReadingCreate,
    background_tasks: BackgroundTasks,
    temp_service: TempService = Depends(get_temp_service),
) -> Any:
    """Log a single manual temperature reading on a storage vessel (no device required)."""
    logger.info("Endpoint POST /vessels/%s/temp", vessel_id)
    body.vessel_id = vessel_id
    body.batch_id = None
    body.device_id = None
    if body.created_at is None:
        body.created_at = datetime.now(UTC)
    reading = temp_service.create(body)
    background_tasks.add_task(notify_clients, "vessel", "create", vessel_id,
                                   DEFAULT_TENANT_ID, source="temperature")
    return reading


@router.post(
    "/{vessel_id}/temp/bulk",
    tags=[VESSELS_TEMPERATURE],
    response_model=List[TempReadingResponse],
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def bulk_insert_vessel_temp(
    vessel_id: uuid.UUID,
    readings: List[TempReadingCreate] = Body(..., max_length=1000),
    temp_service: TempService = Depends(get_temp_service),
) -> List[Any]:
    """Bulk insert temperature readings for a vessel (e.g. for restore)."""
    logger.info("Endpoint POST /vessels/%s/temp/bulk (%d records)", vessel_id, len(readings))
    now = datetime.now(UTC)
    for r in readings:
        r.vessel_id = vessel_id
        r.batch_id = None
        r.device_id = None
        if r.created_at is None:
            r.created_at = now
    return temp_service.create_list(readings)


@router.patch(
    "/{vessel_id}/temp/{reading_id}",
    tags=[VESSELS_TEMPERATURE],
    response_model=TempReadingResponse,
    responses={404: {"model": ErrorResponse, "description": "Reading not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def update_vessel_temp_reading(
    vessel_id: uuid.UUID,
    reading_id: int,
    update: TempReadingUpdate,
    temp_service: TempService = Depends(get_temp_service),
) -> Any:
    """Update a single vessel temperature reading."""
    logger.info("Endpoint PATCH /vessels/%s/temp/%s", vessel_id, reading_id)
    updated = temp_service.update_for_vessel(vessel_id, reading_id, update)
    if updated is None:
        raise HTTPException(status_code=404, detail="Temp reading not found")
    return updated


# ---------------------------------------------------------------------------
# Pressure sub-resource
# ---------------------------------------------------------------------------

@router.get(
    "/{vessel_id}/pressure",
    tags=[VESSELS_PRESSURE],
    response_model=CursorPage[PressureReadingResponse],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def list_vessel_pressure(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    vessel_id: uuid.UUID,
    limit: int = Query(500, ge=1, le=2000),
    cursor: Optional[str] = Query(None),
    include_excluded: bool = Query(False, alias="includeExcluded"),
    pressure_service: PressureService = Depends(get_pressure_service),
    retention_cutoff: Optional[datetime] = Depends(get_retention_cutoff),
) -> Any:
    """List pressure readings for a vessel (cursor-paginated, oldest-first)."""
    logger.info("Endpoint GET /vessels/%s/pressure limit=%d cursor=%s", vessel_id, limit, cursor)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    items, has_more = pressure_service.search_by_vessel_id_cursor(
        vessel_id, limit=limit, cursor=cursor_dt,
        include_excluded=include_excluded, retention_cutoff=retention_cutoff,
    )
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.get(
    "/{vessel_id}/pressure/chart",
    tags=[VESSELS_PRESSURE],
    response_model=List[PressureChartPoint],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def vessel_pressure_chart(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    vessel_id: uuid.UUID,
    resolution: str = Query("raw"),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    pressure_service: PressureService = Depends(get_pressure_service),
    retention_cutoff: Optional[datetime] = Depends(get_retention_cutoff),
) -> Any:
    """Return pressure chart data scoped to a vessel (serving pressure history)."""
    logger.info("Endpoint GET /vessels/%s/pressure/chart", vessel_id)
    effective_from = from_dt or retention_cutoff
    return pressure_service.chart_data_by_vessel(
        vessel_id, resolution=resolution, from_dt=effective_from, to_dt=to_dt
    )


@router.post(
    "/{vessel_id}/pressure",
    tags=[VESSELS_PRESSURE],
    response_model=PressureReadingResponse,
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def create_vessel_pressure_reading(
    vessel_id: uuid.UUID,
    body: PressureReadingCreate,
    background_tasks: BackgroundTasks,
    pressure_service: PressureService = Depends(get_pressure_service),
) -> Any:
    """Log a single manual pressure reading on a storage vessel (no device required)."""
    logger.info("Endpoint POST /vessels/%s/pressure", vessel_id)
    body.vessel_id = vessel_id
    body.batch_id = None
    body.device_id = None
    if body.created_at is None:
        body.created_at = datetime.now(UTC)
    reading = pressure_service.create(body)
    background_tasks.add_task(notify_clients, "vessel", "create", vessel_id,
                                   DEFAULT_TENANT_ID, source="pressure")
    return reading


@router.post(
    "/{vessel_id}/pressure/bulk",
    tags=[VESSELS_PRESSURE],
    response_model=List[PressureReadingResponse],
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def bulk_insert_vessel_pressure(
    vessel_id: uuid.UUID,
    readings: List[PressureReadingCreate] = Body(..., max_length=1000),
    pressure_service: PressureService = Depends(get_pressure_service),
) -> List[Any]:
    """Bulk insert pressure readings for a vessel (e.g. for restore)."""
    logger.info("Endpoint POST /vessels/%s/pressure/bulk (%d records)", vessel_id, len(readings))
    now = datetime.now(UTC)
    for r in readings:
        r.vessel_id = vessel_id
        r.batch_id = None
        r.device_id = None
        if r.created_at is None:
            r.created_at = now
    return pressure_service.create_list(readings)


@router.patch(
    "/{vessel_id}/pressure/{reading_id}",
    tags=[VESSELS_PRESSURE],
    response_model=PressureReadingResponse,
    responses={404: {"model": ErrorResponse, "description": "Reading not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def update_vessel_pressure_reading(
    vessel_id: uuid.UUID,
    reading_id: int,
    update: PressureReadingUpdate,
    pressure_service: PressureService = Depends(get_pressure_service),
) -> Any:
    """Update a single vessel pressure reading."""
    logger.info("Endpoint PATCH /vessels/%s/pressure/%s", vessel_id, reading_id)
    updated = pressure_service.update_for_owner(reading_id, "vessel_id", vessel_id, update)
    if updated is None:
        raise HTTPException(status_code=404, detail="Pressure reading not found")
    return updated
