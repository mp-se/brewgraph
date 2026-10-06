# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tap management API endpoints."""
import logging
import math
import uuid
from typing import Any, Optional

from fastapi import BackgroundTasks, Depends, Query
from fastapi.routing import APIRouter
from starlette.exceptions import HTTPException

import oss.schemas.tap  # noqa: F401,W0611 — side-effect: triggers self-registration  # pylint: disable=unused-import
from core.events import notify_clients
from core.log import LogLevel, system_log
from core.middleware.auth import AuthContext, check_quota
from core.openapi_tags import TAPS
from core.schemas.errors import NOT_FOUND_RESPONSES, ErrorResponse
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.extensions.tenant import DEFAULT_TENANT_ID
from oss.schemas._page import CursorPage, Page, encode_cursor, parse_cursor
from oss.schemas.prediction import PredictionResponse
from oss.schemas.registry import get as _s
from oss.services import get_prediction_service, get_tap_service
from oss.services.prediction import PredictionService
from oss.services.tap import TapService

TapCreate   = _s("TapCreate")
TapUpdate   = _s("TapUpdate")
TapResponse = _s("TapResponse")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/taps", dependencies=[Depends(api_key_auth)])


@router.get(
    "",
    tags=[TAPS],
    response_model=Page[TapResponse],
    dependencies=[Depends(api_key_auth)],
)
async def list_taps(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200, alias="pageSize"),
    tap_service: TapService = Depends(get_tap_service),
) -> Any:
    """List all taps (paginated)."""
    logger.info("Endpoint GET /taps/?page=%d&pageSize=%d", page, page_size)
    items, total = tap_service.list_page(page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size,
                pages=max(1, math.ceil(total / page_size)))



@router.get(
    "/{tap_id}",
    tags=[TAPS],
    response_model=TapResponse,
    responses={404: {"model": ErrorResponse, "description": "Tap not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def get_tap(
    tap_id: uuid.UUID,
    tap_service: TapService = Depends(get_tap_service),
) -> Any:
    """Get a tap by ID."""
    logger.info("Endpoint GET /taps/%s", tap_id)
    tap = tap_service.get(tap_id)
    if tap is None or tap.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Tap not found")
    return tap


@router.post(
    "",
    tags=[TAPS],
    response_model=TapResponse,
    status_code=201,
)
async def create_tap(
    tap: TapCreate,
    background_tasks: BackgroundTasks,
    tap_service: TapService = Depends(get_tap_service),
    auth: AuthContext = Depends(api_key_auth),
) -> Any:
    """Create a new tap."""
    logger.info("Endpoint POST /taps/")
    check_quota(tap_service.count(), auth, "taps")
    created = tap_service.create(tap)
    background_tasks.add_task(notify_clients, "tap", "create", created.id,
                                   DEFAULT_TENANT_ID, source="tap")
    return created


@router.patch(
    "/{tap_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[TAPS],
    response_model=TapResponse,
    dependencies=[Depends(api_key_auth)],
)
async def update_tap(
    tap_id: uuid.UUID,
    tap: TapUpdate,
    background_tasks: BackgroundTasks,
    tap_service: TapService = Depends(get_tap_service),
) -> Any:
    """Update a tap by ID."""
    logger.info("Endpoint PATCH /taps/%s", tap_id)
    updated = tap_service.update(tap_id, tap)
    if updated is None:
        raise HTTPException(status_code=404, detail="Tap not found")
    background_tasks.add_task(notify_clients, "tap", "update", tap_id,
                                   DEFAULT_TENANT_ID, source="tap")
    return updated


@router.post(
    "/{tap_id}/token",
    tags=[TAPS],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def regenerate_token(
    tap_id: uuid.UUID,
    tap_service: TapService = Depends(get_tap_service),
) -> dict:
    """Regenerate the ingest token for a tap. Returns the new token."""
    logger.info("Endpoint POST /taps/%s/token", tap_id)
    tap = tap_service.get_active(tap_id)
    if not tap:
        raise HTTPException(status_code=404, detail="Tap not found")
    token = tap_service.generate_token(tap_id)
    system_log(
        "tap_token_regenerated",
        f"Token regenerated for tap {tap_id}",
        level=LogLevel.INFO,
    )
    return {"token": token}


@router.delete("/{tap_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[TAPS], status_code=204, dependencies=[Depends(api_key_auth)])
async def delete_tap(
    tap_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tap_service: TapService = Depends(get_tap_service),
) -> None:
    """Soft-delete a tap by ID."""
    logger.info("Endpoint DELETE /taps/%s", tap_id)
    tap = tap_service.get(tap_id)
    if tap is None or tap.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Tap not found")
    tap_service.soft_delete(tap_id)
    background_tasks.add_task(notify_clients, "tap", "delete", tap_id,
                                   DEFAULT_TENANT_ID, source="tap")


@router.get(
    "/{tap_id}/predictions",
    response_model=CursorPage[PredictionResponse],
    tags=["predictions"],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def get_tap_predictions(
    tap_id: uuid.UUID,
    limit: int = Query(200, ge=1, le=1000),
    cursor: Optional[str] = Query(None),
    prediction_service: PredictionService = Depends(get_prediction_service),
) -> Any:
    """Return prediction history for a tap, newest first (cursor-paginated)."""
    logger.info("Endpoint GET /taps/%s/predictions", tap_id)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    items, has_more = prediction_service.history_cursor(
        "tap_id", tap_id, limit=limit, cursor=cursor_dt
    )
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)

@router.post(
    "/{tap_id}/restore",
    tags=[TAPS],
    response_model=TapResponse,
    responses={404: {"model": ErrorResponse, "description": "Not found or not deleted"}},
    dependencies=[Depends(api_key_auth)],
)
async def restore_tap(
    tap_id: uuid.UUID,
    tap_service: TapService = Depends(get_tap_service),
) -> Any:
    """Undo a soft delete, until the grace-window purge removes the row.

    Only what was deleted here comes back — a child soft-deleted in its own right
    stays deleted, so restoring is not a way to undo every deletion that ever
    touched this tap.
    """
    logger.info("Endpoint POST /taps/%s/restore", tap_id)
    if not tap_service.restore(tap_id):
        raise HTTPException(status_code=404, detail="Tap not found or not deleted")
    return tap_service.get(tap_id)
