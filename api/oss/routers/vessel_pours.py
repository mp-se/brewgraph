# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Pour event sub-resource of a storage vessel.

Split out of `vessels.py` (was 613 lines importing six services across vessel
lifecycle, pours, readings, and predictions) — pours are a five-endpoint
cluster of their own, the same shape as the gravity/pressure/temp readings
split out of `batches.py` into `batch_readings.py`.

Mounted on the same `/api/vessels` prefix, so the URL layout is unchanged.
"""
import logging
import uuid
from typing import Any, List, Optional

from fastapi import BackgroundTasks, Body, Depends, Query, Request
from fastapi.routing import APIRouter
from starlette.exceptions import HTTPException

import oss.schemas.pour_event  # noqa: F401,W0611 — side-effect: triggers self-registration  # pylint: disable=unused-import
from core.events import notify_clients
from core.openapi_tags import VESSELS_POURS
from core.schemas.errors import NOT_FOUND_RESPONSES
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.extensions.tenant import DEFAULT_TENANT_ID
from oss.schemas._page import CursorPage, encode_cursor, parse_cursor
from oss.schemas.registry import get as _s
from oss.services import get_pour_service, get_vessel_service
from oss.services.pour_event import PourEventService
from oss.services.storage_vessel import StorageVesselService

BottlePourCreate    = _s("BottlePourCreate")
PourEventBulkCreate = _s("PourEventBulkCreate")
PourEventCreate     = _s("PourEventCreate")
PourEventResponse   = _s("PourEventResponse")


logger = logging.getLogger(__name__)


def _active_vessel(
    request: Request,
    vessel_id: Optional[uuid.UUID] = None,
    vessel_service: StorageVesselService = Depends(get_vessel_service),
):
    """Reject nested pour access for missing or soft-deleted vessels.

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


@router.get(
    "/{vessel_id}/pours",
    tags=[VESSELS_POURS],
    response_model=CursorPage[PourEventResponse],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def list_pours(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    vessel_id: uuid.UUID,
    limit: int = Query(200, ge=1, le=1000),
    cursor: Optional[str] = Query(None),
    all_fills: bool = Query(False, alias="allFills"),
    pour_service: PourEventService = Depends(get_pour_service),
) -> Any:
    """List pour events for a vessel, oldest first (cursor-paginated).

    Scoped to the vessel's current batch by default: a keg holds one beer at a time,
    and mixing the pours of everything it has ever held makes the list meaningless.
    `allFills=true` returns the vessel's whole history.
    """
    logger.info("Endpoint GET /vessels/%s/pours limit=%d cursor=%s", vessel_id, limit, cursor)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    items, has_more = pour_service.list_for_vessel_cursor(
        vessel_id, limit=limit, cursor=cursor_dt, current_fill_only=not all_fills
    )
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.post(
    "/{vessel_id}/pours",
    tags=[VESSELS_POURS],
    response_model=PourEventResponse,
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def record_pour(
    vessel_id: uuid.UUID,
    pour: PourEventCreate,
    background_tasks: BackgroundTasks,
    pour_service: PourEventService = Depends(get_pour_service),
) -> Any:
    """Record a pour from a keg and atomically decrement volume_remaining."""
    logger.info("Endpoint POST /vessels/%s/pours", vessel_id)
    result = pour_service.record_pour(vessel_id, pour.pour_amount, pour.created_at)
    background_tasks.add_task(notify_clients, "vessel", "update", vessel_id,
                                   DEFAULT_TENANT_ID, source="vessel")
    return result


@router.post(
    "/{vessel_id}/pours/bottles",
    tags=[VESSELS_POURS],
    response_model=PourEventResponse,
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def record_bottle_pour(
    vessel_id: uuid.UUID,
    pour: BottlePourCreate,
    background_tasks: BackgroundTasks,
    pour_service: PourEventService = Depends(get_pour_service),
) -> Any:
    """Record consuming one or more bottles and decrement bottles_remaining."""
    logger.info("Endpoint POST /vessels/%s/pours/bottles count=%d", vessel_id, pour.bottle_count)
    result = pour_service.record_bottle_pour(vessel_id, pour.bottle_count, pour.created_at)
    background_tasks.add_task(notify_clients, "vessel", "update", vessel_id,
                                   DEFAULT_TENANT_ID, source="vessel")
    return result


@router.post(
    "/{vessel_id}/pours/bulk",
    tags=[VESSELS_POURS],
    response_model=List[PourEventResponse],
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def bulk_insert_pours(
    vessel_id: uuid.UUID,
    rows: List[PourEventBulkCreate] = Body(..., max_length=1000),
    pour_service: PourEventService = Depends(get_pour_service),
) -> Any:
    """Bulk-insert pour history for a vessel (restore use-case; skips volume decrement)."""
    logger.info("Endpoint POST /vessels/%s/pours/bulk (%d records)", vessel_id, len(rows))
    return pour_service.bulk_insert(vessel_id, rows)


@router.patch(
    "/{vessel_id}/pours/{pour_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[VESSELS_POURS],
    response_model=PourEventResponse,
    dependencies=[Depends(api_key_auth)],
)
async def toggle_pour_excluded(
    vessel_id: uuid.UUID,
    pour_id: uuid.UUID,
    pour_service: PourEventService = Depends(get_pour_service),
) -> Any:
    """Toggle the excluded flag on a pour event."""
    logger.info("Endpoint PATCH /vessels/%s/pours/%s", vessel_id, pour_id)
    return pour_service.toggle_excluded(vessel_id, pour_id)
