# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Batch management API endpoints: lifecycle CRUD, vessels, and predictions.

Gravity/pressure/temp readings live in `batch_readings.py`; fermentation
steps, notes, and dry hops live in `batch_steps.py` — both split out of this
module (was ~990 lines bundling ~8 sub-resource concerns) and mounted on the
same `/api/batches` prefix. Vessels and predictions stay here since they're
each a single small endpoint, not a cluster of related operations.
"""
import logging
import math
import uuid
from datetime import datetime
from typing import Any, List, Optional

from fastapi import BackgroundTasks, Depends, Query
from fastapi.routing import APIRouter
from starlette.exceptions import HTTPException

import oss.schemas.batch  # noqa: F401,W0611 — side-effect: triggers self-registration  # pylint: disable=unused-import
import oss.schemas.storage_vessel  # noqa: F401,W0611  # pylint: disable=unused-import
from core.events import notify_clients
from core.log import LogLevel, system_log
from core.middleware.auth import AuthContext, check_quota
from core.openapi_tags import BATCHES
from core.schemas.errors import NOT_FOUND_RESPONSES, ErrorResponse
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.extensions.retention import \
    oss_retention_provider as get_retention_cutoff
from oss.extensions.tenant import DEFAULT_TENANT_ID
from oss.schemas._page import CursorPage, Page, encode_cursor, parse_cursor
from oss.schemas.prediction import PredictionResponse
from oss.schemas.registry import get as _s
from oss.services import (BatchDryHopService, BatchService, get_batch_service,
                          get_dry_hop_service, get_prediction_service,
                          get_vessel_service)
from oss.services.prediction import PredictionService
from oss.services.storage_vessel import StorageVesselService

BatchCreate            = _s("BatchCreate")
BatchUpdate            = _s("BatchUpdate")
BatchResponse          = _s("BatchResponse")
BatchListResponse      = _s("BatchListResponse")
StorageVesselResponse   = _s("StorageVesselResponse")


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/batches", dependencies=[Depends(api_key_auth)])


# ---------------------------------------------------------------------------
# Batch CRUD
# ---------------------------------------------------------------------------

@router.get(
    "",
    tags=[BATCHES],
    response_model=Page[BatchListResponse],
    )
async def list_batches(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200, alias="pageSize"),
    device_id: Optional[str] = Query(None, alias="deviceId"),
    batch_service: BatchService = Depends(get_batch_service),
    retention_cutoff: Optional[datetime] = Depends(get_retention_cutoff),
) -> Any:
    """List non-deleted batches with reading counts, offset-paginated."""
    logger.info(
        "Endpoint GET /batches/?page=%d&pageSize=%d&device_id=%s", page, page_size, device_id
    )
    batches, total = batch_service.list_filtered_page(
        page=page, page_size=page_size,
        device_id=device_id, retention_cutoff=retention_cutoff,
    )

    items = []
    for b in batches:
        gravity_count = len(b.gravity_readings) if b.gravity_readings else 0
        pressure_count = len(b.pressure_readings) if b.pressure_readings else 0
        temperature_count = len(b.temp_readings) if b.temp_readings else 0
        data = BatchListResponse.model_validate(b)
        data.gravity_count = gravity_count
        data.pressure_count = pressure_count
        data.temperature_count = temperature_count
        items.append(data)

    return Page(items=items, total=total, page=page, page_size=page_size,
                pages=max(1, math.ceil(total / page_size)) if page_size else 1)




@router.get(
    "/{batch_id}",
    tags=[BATCHES],
    response_model=BatchListResponse,
    responses={404: {"model": ErrorResponse, "description": "Batch not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def get_batch_by_id(
    batch_id: uuid.UUID,
    batch_service: BatchService = Depends(get_batch_service),
) -> Any:
    """Retrieve a specific batch by ID, including reading counts."""
    logger.info("Endpoint GET /batches/%s", batch_id)
    batch = batch_service.get(batch_id)
    if batch is None or batch.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Batch not found")
    data = BatchListResponse.model_validate(batch)
    data.gravity_count = len(batch.gravity_readings) if batch.gravity_readings else 0
    data.pressure_count = len(batch.pressure_readings) if batch.pressure_readings else 0
    data.temperature_count = len(batch.temp_readings) if batch.temp_readings else 0
    return data


@router.post(
    "",
    tags=[BATCHES],
    response_model=BatchResponse,
    status_code=201,
    responses={409: {"model": ErrorResponse, "description": "Conflict Error"}},
)
async def create_batch(
    batch: BatchCreate,
    background_tasks: BackgroundTasks,
    batch_service: BatchService = Depends(get_batch_service),
    dry_hop_service: BatchDryHopService = Depends(get_dry_hop_service),
    auth: AuthContext = Depends(api_key_auth),
) -> Any:
    """Create a new batch, optionally bulk-inserting dry hops in the same transaction."""
    logger.info("Endpoint POST /batches/")
    check_quota(batch_service.count(), auth, "batches")
    dry_hops_input = batch.dry_hops or []
    created = batch_service.create(batch)
    if dry_hops_input:
        dry_hop_service.create_list_for_batch(created.id, dry_hops_input)
        batch_service.db_session.refresh(created)
    system_log("batch_created", f"Batch created: {created.name}", level=LogLevel.INFO)
    background_tasks.add_task(notify_clients, "batch", "create", created.id,
                                   DEFAULT_TENANT_ID, source="batch")
    return created


@router.patch(
    "/{batch_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[BATCHES],
    response_model=BatchResponse,
    dependencies=[Depends(api_key_auth)],
)
async def update_batch_by_id(
    batch_id: uuid.UUID,
    batch: BatchUpdate,
    background_tasks: BackgroundTasks,
    batch_service: BatchService = Depends(get_batch_service),
) -> Any:
    """Update a batch by ID."""
    logger.info("Endpoint PATCH /batches/%s", batch_id)
    updated = batch_service.update(batch_id, batch)
    if updated is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    system_log("batch_updated", f"Batch {updated.name} updated", level=LogLevel.INFO)
    background_tasks.add_task(notify_clients, "batch", "update", batch_id,
                                   DEFAULT_TENANT_ID, source="batch")
    return updated


@router.delete("/{batch_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[BATCHES], status_code=204, dependencies=[Depends(api_key_auth)])
async def delete_batch_by_id(
    batch_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    batch_service: BatchService = Depends(get_batch_service),
):
    """Soft-delete a batch by ID."""
    logger.info("Endpoint DELETE /batches/%s", batch_id)
    batch = batch_service.get(batch_id)
    if not batch or batch.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Batch not found")
    system_log("batch_deleted", f"Batch {batch.name} deleted", level=LogLevel.INFO)
    batch_service.soft_delete(batch_id)
    background_tasks.add_task(notify_clients, "batch", "delete", batch_id,
                                   DEFAULT_TENANT_ID, source="batch")


# ---------------------------------------------------------------------------
# Storage vessels sub-resource
# ---------------------------------------------------------------------------

@router.get(
    "/{batch_id}/vessels",
    tags=[BATCHES],
    response_model=List[StorageVesselResponse],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def list_batch_vessels(
    batch_id: uuid.UUID,
    vessel_service: StorageVesselService = Depends(get_vessel_service),
) -> List[Any]:
    """List all storage vessels for a batch."""
    logger.info("Endpoint GET /batches/%s/vessels", batch_id)
    return vessel_service.list_active(batch_id=batch_id)


# ---------------------------------------------------------------------------
# Predictions sub-resource
# ---------------------------------------------------------------------------

@router.get(
    "/{batch_id}/predictions",
    tags=["predictions"],
    response_model=CursorPage[PredictionResponse],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def get_batch_predictions(
    batch_id: uuid.UUID,
    limit: int = Query(200, ge=1, le=1000),
    cursor: Optional[str] = Query(None),
    prediction_service: PredictionService = Depends(get_prediction_service),
) -> Any:
    """Return prediction history for a batch, newest first (cursor-paginated)."""
    logger.info("Endpoint GET /batches/%s/predictions", batch_id)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    items, has_more = prediction_service.history_cursor(
        "batch_id", batch_id, limit=limit, cursor=cursor_dt
    )
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


# ---------------------------------------------------------------------------
# Restore soft-deleted batch
# ---------------------------------------------------------------------------

@router.post(
    "/{batch_id}/restore",
    tags=[BATCHES],
    response_model=BatchResponse,
    responses={404: {"model": ErrorResponse, "description": "Not found or not deleted"}},
    dependencies=[Depends(api_key_auth)],
)
async def restore_batch(
    batch_id: uuid.UUID,
    batch_service: BatchService = Depends(get_batch_service),
) -> Any:
    """Undo a soft delete, until the grace-window purge removes the row.

    Only what was deleted here comes back — a child soft-deleted in its own right
    stays deleted, so restoring is not a way to undo every deletion that ever
    touched this batch.
    """
    logger.info("Endpoint POST /batches/%s/restore", batch_id)
    restored = batch_service.restore(batch_id)
    if restored is None:
        raise HTTPException(status_code=404, detail="Batch not found or not deleted")
    return restored
