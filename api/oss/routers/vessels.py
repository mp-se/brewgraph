# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Storage vessel lifecycle: CRUD, listing, soft-delete/restore, and predictions.

Pour events live in `vessel_pours.py`; temperature and pressure readings live in
`vessel_readings.py`, both mounted on the same `/api/vessels` prefix, mirroring how
`batches.py` splits gravity/pressure/temp readings out into `batch_readings.py`.
Predictions stay here since it's a single small endpoint, not a cluster of related
operations — the same reasoning `batches.py` gives for keeping its own predictions
endpoint alongside batch CRUD.

The list endpoint's cross-entity enrichment (pour count, denormalised batch name) lives
in `StorageVesselService.list_page_with_summary`, so this router does not import
`PourEventService`/`BatchService` itself to build that response — that orchestration
stays in the service layer rather than the router.
"""
import logging
import math
import uuid
from typing import Any, Optional

from fastapi import BackgroundTasks, Depends, Query, Request
from fastapi.routing import APIRouter
from starlette.exceptions import HTTPException

import oss.schemas.storage_vessel  # noqa: F401,W0611 — side-effect: triggers self-registration  # pylint: disable=unused-import
from core.events import notify_clients
from core.middleware.auth import AuthContext, check_quota
from core.openapi_tags import VESSELS
from core.schemas.errors import NOT_FOUND_RESPONSES, ErrorResponse
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.extensions.tenant import DEFAULT_TENANT_ID
from oss.schemas._page import CursorPage, Page, encode_cursor, parse_cursor
from oss.schemas.prediction import PredictionResponse
from oss.schemas.registry import get as _s
from oss.services import get_prediction_service, get_vessel_service
from oss.services.prediction import PredictionService
from oss.services.storage_vessel import StorageVesselService

StorageVesselCreate       = _s("StorageVesselCreate")
StorageVesselUpdate       = _s("StorageVesselUpdate")
StorageVesselResponse     = _s("StorageVesselResponse")
StorageVesselListResponse = _s("StorageVesselListResponse")


logger = logging.getLogger(__name__)


def _active_vessel(
    request: Request,
    vessel_id: Optional[uuid.UUID] = None,
    vessel_service: StorageVesselService = Depends(get_vessel_service),
):
    """Reject nested reading access for missing or soft-deleted vessels.

    Router-level, so it applies to every route below including the vessel's own
    CRUD — except `/restore`, whose entire purpose is to act on a vessel that
    IS soft-deleted. Rejecting it here would make restore permanently
    unreachable the moment a vessel is deleted, which is the one case this
    dependency must not gate.

    Duplicated verbatim in `vessel_pours.py` and `vessel_readings.py` — each of those
    modules' `APIRouter` needs the identical guard at its own mount point, the same way
    `batch_readings.py` duplicates `_active_batch` rather than sharing one definition
    across router modules. `update_vessel` below has no deleted-at check of its own —
    this dependency is the only thing stopping a PATCH on a soft-deleted vessel, so it
    cannot be dropped from any router that mounts under `/api/vessels/{vessel_id}`.
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


@router.get(
    "",
    tags=[VESSELS],
    response_model=Page[StorageVesselListResponse],
    dependencies=[Depends(api_key_auth)],
)
async def list_vessels(
    batch_id: Optional[uuid.UUID] = Query(None, alias="batchId"),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200, alias="pageSize"),
    vessel_service: StorageVesselService = Depends(get_vessel_service),
) -> Any:
    """List storage vessels (paginated), optionally filtered by batch or status."""
    logger.info("Endpoint GET /vessels/?batchId=%s&status=%s&page=%d&pageSize=%d",
                batch_id, status, page, page_size)
    items, total = vessel_service.list_page_with_summary(
        page=page, page_size=page_size, batch_id=batch_id, status=status
    )
    return Page(items=items, total=total, page=page, page_size=page_size,
                pages=max(1, math.ceil(total / page_size)))


@router.get(
    "/{vessel_id}",
    tags=[VESSELS],
    response_model=StorageVesselResponse,
    responses={404: {"model": ErrorResponse, "description": "Vessel not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def get_vessel(
    vessel_id: uuid.UUID,
    vessel_service: StorageVesselService = Depends(get_vessel_service),
) -> Any:
    """Get a storage vessel by ID."""
    logger.info("Endpoint GET /vessels/%s", vessel_id)
    vessel = vessel_service.get(vessel_id)
    if vessel is None or vessel.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return vessel


@router.post(
    "",
    tags=[VESSELS],
    response_model=StorageVesselResponse,
    status_code=201,
)
async def create_vessel(
    vessel: StorageVesselCreate,
    background_tasks: BackgroundTasks,
    vessel_service: StorageVesselService = Depends(get_vessel_service),
    auth: AuthContext = Depends(api_key_auth),
) -> Any:
    """Create a new storage vessel."""
    logger.info("Endpoint POST /vessels/")
    check_quota(vessel_service.count(), auth, "vessels")
    created = vessel_service.create(vessel)
    background_tasks.add_task(notify_clients, "vessel", "create", created.id,
                                   DEFAULT_TENANT_ID, source="vessel")
    return StorageVesselResponse.model_validate(created)


@router.patch(
    "/{vessel_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[VESSELS],
    response_model=StorageVesselResponse,
    dependencies=[Depends(api_key_auth)],
)
async def update_vessel(
    vessel_id: uuid.UUID,
    vessel: StorageVesselUpdate,
    background_tasks: BackgroundTasks,
    vessel_service: StorageVesselService = Depends(get_vessel_service),
) -> Any:
    """Update a storage vessel by ID."""
    logger.info("Endpoint PATCH /vessels/%s", vessel_id)
    updated = vessel_service.update(vessel_id, vessel)
    if updated is None:
        raise HTTPException(status_code=404, detail="Vessel not found")
    background_tasks.add_task(notify_clients, "vessel", "update", vessel_id,
                                   DEFAULT_TENANT_ID, source="vessel")
    return updated


@router.delete("/{vessel_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[VESSELS], status_code=204, dependencies=[Depends(api_key_auth)])
async def delete_vessel(
    vessel_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    vessel_service: StorageVesselService = Depends(get_vessel_service),
) -> None:
    """Soft-delete a storage vessel."""
    logger.info("Endpoint DELETE /vessels/%s", vessel_id)
    vessel = vessel_service.get(vessel_id)
    if vessel is None or vessel.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Vessel not found")
    vessel_service.soft_delete(vessel_id)
    background_tasks.add_task(notify_clients, "vessel", "delete", vessel_id,
                                   DEFAULT_TENANT_ID, source="vessel")


# ---------------------------------------------------------------------------
# Predictions sub-resource
# ---------------------------------------------------------------------------

@router.get(
    "/{vessel_id}/predictions",
    response_model=CursorPage[PredictionResponse],
    tags=["predictions"],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def get_vessel_predictions(
    vessel_id: uuid.UUID,
    limit: int = Query(200, ge=1, le=1000),
    cursor: Optional[str] = Query(None),
    prediction_service: PredictionService = Depends(get_prediction_service),
) -> Any:
    """Return prediction history for a vessel, newest first (cursor-paginated)."""
    logger.info("Endpoint GET /vessels/%s/predictions", vessel_id)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    items, has_more = prediction_service.history_cursor(
        "vessel_id", vessel_id, limit=limit, cursor=cursor_dt
    )
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


# ---------------------------------------------------------------------------
# Restore soft-deleted vessel
# ---------------------------------------------------------------------------

@router.post(
    "/{vessel_id}/restore",
    tags=[VESSELS],
    response_model=StorageVesselResponse,
    responses={404: {"model": ErrorResponse, "description": "Not found or not deleted"}},
    dependencies=[Depends(api_key_auth)],
)
async def restore_vessel(
    vessel_id: uuid.UUID,
    vessel_service: StorageVesselService = Depends(get_vessel_service),
) -> Any:
    """Undo a soft delete, until the grace-window purge removes the row.

    Only what was deleted here comes back — a child soft-deleted in its own right
    stays deleted, so restoring is not a way to undo every deletion that ever
    touched this vessel.
    """
    logger.info("Endpoint POST /vessels/%s/restore", vessel_id)
    if not vessel_service.restore(vessel_id):
        raise HTTPException(status_code=404, detail="Vessel not found or not deleted")
    return vessel_service.get(vessel_id)
