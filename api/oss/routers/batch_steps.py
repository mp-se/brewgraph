# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Fermentation-schedule sub-resources of a batch: steps, notes, and dry hops.

Split out of `batches.py`, which had grown past what one module should carry
(~990 lines bundling ~8 sub-resource concerns). These three share a lifecycle
theme distinct from readings: they track/annotate progress through a batch's
fermentation schedule rather than recording sensor data.

Mounted on the same `/api/batches` prefix, so the URL layout is unchanged.
"""
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, List, Optional

from fastapi import Body, Depends, Query
from fastapi.routing import APIRouter
from starlette.exceptions import HTTPException

from core.enums import BatchStatus
from core.openapi_tags import BATCHES_DRY_HOPS, BATCHES_NOTES, BATCHES_STEPS
from core.schemas.errors import NOT_FOUND_RESPONSES, ErrorResponse
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.schemas._page import CursorPage, encode_cursor, parse_cursor
from oss.schemas.batch_dry_hop import (BatchDryHopCreate, BatchDryHopResponse,
                                       BatchDryHopUpdate)
from oss.schemas.batch_note import (BatchNoteCreate, BatchNoteResponse,
                                    BatchNoteUpdate)
from oss.schemas.fermentation_step import (FermentationStepCreate,
                                           FermentationStepResponse)
from oss.services import (BatchDryHopService, BatchNoteService, BatchService,
                          FermentationStepService, get_batch_note_service,
                          get_batch_service, get_dry_hop_service,
                          get_fermentation_step_service)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/batches", dependencies=[Depends(api_key_auth)])


# ---------------------------------------------------------------------------
# Fermentation steps sub-resource
# ---------------------------------------------------------------------------

@router.get(
    "/{batch_id}/fermentation-steps",
    tags=[BATCHES_STEPS],
    response_model=List[FermentationStepResponse],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def list_fermentation_steps(
    batch_id: uuid.UUID,
    step_service: FermentationStepService = Depends(get_fermentation_step_service),
) -> List[Any]:
    """List all fermentation steps for a batch ordered by step order."""
    logger.info("Endpoint GET /batches/%s/steps", batch_id)
    return step_service.search_by_batch_id(batch_id)


@router.post(
    "/{batch_id}/fermentation-steps",
    tags=[BATCHES_STEPS],
    response_model=List[FermentationStepResponse],
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def create_fermentation_steps(
    batch_id: uuid.UUID,
    steps: List[FermentationStepCreate] = Body(..., max_length=1000),
    step_service: FermentationStepService = Depends(get_fermentation_step_service),
) -> List[Any]:
    """Import a fermentation step list for a batch (e.g. from Brewfather).

    Replaces any existing steps for the batch — delete + create in one transaction.
    """
    logger.info("Endpoint POST /batches/%s/steps (%d steps)", batch_id, len(steps))
    for step in steps:
        step.batch_id = batch_id
    return step_service.replace_for_batch(batch_id, steps)


@router.delete(
    "/{batch_id}/fermentation-steps",
    tags=[BATCHES_STEPS],
    status_code=204,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def delete_fermentation_steps(
    batch_id: uuid.UUID,
    step_service: FermentationStepService = Depends(get_fermentation_step_service),
) -> None:
    """Soft-delete all fermentation steps for a batch."""
    logger.info("Endpoint DELETE /batches/%s/steps", batch_id)
    step_service.delete_by_batch_id(batch_id)


@router.post(
    "/{batch_id}/fermentation-steps/activate",
    tags=[BATCHES_STEPS],
    response_model=List[FermentationStepResponse],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def activate_fermentation_steps(
    batch_id: uuid.UUID,
    step_service: FermentationStepService = Depends(get_fermentation_step_service),
) -> List[Any]:
    """Activate temperature control for a batch's fermentation step list.

    Computes each step's absolute start date cascading from today and marks the
    batch as under active chamber control. Re-activating recomputes all step dates from the
    current day, discarding any previous schedule.
    """
    logger.info("Endpoint POST /batches/%s/steps/activate", batch_id)
    return step_service.activate(batch_id)


@router.post(
    "/{batch_id}/fermentation-steps/deactivate",
    tags=[BATCHES_STEPS],
    status_code=204,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def deactivate_fermentation_steps(
    batch_id: uuid.UUID,
    step_service: FermentationStepService = Depends(get_fermentation_step_service),
) -> None:
    """End temperature control for a batch before its schedule would otherwise
    expire on its own. Subsequent chamber polls for this batch's steps return
    mode R."""
    logger.info("Endpoint POST /batches/%s/steps/deactivate", batch_id)
    step_service.deactivate(batch_id)


@router.post(
    "/{batch_id}/fermentation-steps/advance",
    tags=[BATCHES_STEPS],
    response_model=FermentationStepResponse,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def advance_fermentation_step(
    batch_id: uuid.UUID,
    step_service: FermentationStepService = Depends(get_fermentation_step_service),
) -> Any:
    """Manually end the batch's currently-active fermentation step early and move
    on to whichever step's date range takes over next, without waiting for that
    step's own end condition. Raises 400 if the batch is not under active chamber
    control, or there is no current step to advance past."""
    logger.info("Endpoint POST /batches/%s/steps/advance", batch_id)
    return step_service.advance_step(batch_id)


@router.delete(
    "/{batch_id}/fermentation-steps/{step_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[BATCHES_STEPS],
    status_code=204,
    dependencies=[Depends(api_key_auth)],
)
async def delete_fermentation_step(
    batch_id: uuid.UUID,
    step_id: uuid.UUID,
    step_service: FermentationStepService = Depends(get_fermentation_step_service),
) -> None:
    """Soft-delete a single fermentation step by ID."""
    logger.info("Endpoint DELETE /batches/%s/steps/%s", batch_id, step_id)
    step_service.delete_by_id(batch_id, step_id)


# ---------------------------------------------------------------------------
# Notes sub-resource
# ---------------------------------------------------------------------------

@router.get(
    "/{batch_id}/notes",
    tags=[BATCHES_NOTES],
    response_model=CursorPage[BatchNoteResponse],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def list_batch_notes(
    batch_id: uuid.UUID,
    limit: int = Query(200, ge=1, le=1000),
    cursor: Optional[str] = Query(None),
    note_service: BatchNoteService = Depends(get_batch_note_service),
) -> Any:
    """List notes for a batch, oldest first (cursor-paginated)."""
    logger.info("Endpoint GET /batches/%s/notes", batch_id)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    items, has_more = note_service.list_by_batch_cursor(batch_id, limit=limit, cursor=cursor_dt)
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.post(
    "/{batch_id}/notes",
    tags=[BATCHES_NOTES],
    response_model=BatchNoteResponse,
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def create_batch_note(
    batch_id: uuid.UUID,
    note: BatchNoteCreate,
    batch_service: BatchService = Depends(get_batch_service),
    note_service: BatchNoteService = Depends(get_batch_note_service),
    step_service: FermentationStepService = Depends(get_fermentation_step_service),
) -> Any:
    """Create a note on a batch."""
    logger.info("Endpoint POST /batches/%s/notes", batch_id)
    batch = batch_service.get(batch_id)
    if not batch or batch.deleted_at is not None or batch.status == BatchStatus.ARCHIVED.value:
        raise HTTPException(status_code=404, detail="Batch not found")
    if note.created_at is not None:
        # A timezone-naive created_at (Pydantic accepts one — the schema has no offset
        # constraint) can't be compared to the timezone-aware `now` below without this:
        # naive-vs-aware comparison raises TypeError, surfacing as an unhandled 500
        # rather than the 422 this validation intends. Same idiom as
        # _chart_window.bounded_chart_window/tap_reminder._days_overdue/
        # device.status_for_all — treat a naive value as UTC.
        if note.created_at.tzinfo is None:
            note.created_at = note.created_at.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        if note.created_at > now:
            raise HTTPException(status_code=422, detail="created_at cannot be in the future")
        if batch.brew_date and note.created_at.date() < batch.brew_date:
            raise HTTPException(status_code=422, detail="created_at cannot be before brew_date")
    created = note_service.create_for_batch(
        batch_id=batch_id,
        content=note.content,
        created_at=note.created_at,
        meta={"note_type": note.note_type, "test_result": note.test_result},
    )
    if created.note_type == "diacetyl_test" and created.test_result == "pass":
        step_service.confirm_diacetyl_pass(batch_id)
    return created


@router.patch(
    "/{batch_id}/notes/{note_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[BATCHES_NOTES],
    response_model=BatchNoteResponse,
    dependencies=[Depends(api_key_auth)],
)
async def update_batch_note(
    batch_id: uuid.UUID,
    note_id: uuid.UUID,
    payload: BatchNoteUpdate,
    note_service: BatchNoteService = Depends(get_batch_note_service),
    step_service: FermentationStepService = Depends(get_fermentation_step_service),
) -> Any:
    """Edit the content of an existing note."""
    logger.info("Endpoint PATCH /batches/%s/notes/%s", batch_id, note_id)
    existing = note_service.get_for_batch(batch_id, note_id)
    old_test_result = existing.test_result if existing is not None else None
    updated = note_service.update_note(
        batch_id=batch_id,
        note_id=note_id,
        content=payload.content,
        note_type=payload.note_type,
        test_result=payload.test_result,
    )
    if (
        updated.note_type == "diacetyl_test"
        and updated.test_result == "pass"
        and old_test_result != "pass"
    ):
        step_service.confirm_diacetyl_pass(batch_id)
    return updated


@router.delete(
    "/{batch_id}/notes/{note_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[BATCHES_NOTES],
    status_code=204,
    dependencies=[Depends(api_key_auth)],
)
async def delete_batch_note(
    batch_id: uuid.UUID,
    note_id: uuid.UUID,
    note_service: BatchNoteService = Depends(get_batch_note_service),
) -> None:
    """Soft-delete a note from a batch."""
    logger.info("Endpoint DELETE /batches/%s/notes/%s", batch_id, note_id)
    note_service.delete_note(batch_id, note_id)


@router.post(
    "/{batch_id}/notes/{note_id}/restore",
    tags=[BATCHES_NOTES],
    response_model=BatchNoteResponse,
    responses={404: {"model": ErrorResponse, "description": "Not found or not deleted"}},
    dependencies=[Depends(api_key_auth)],
)
async def restore_batch_note(
    batch_id: uuid.UUID,
    note_id: uuid.UUID,
    note_service: BatchNoteService = Depends(get_batch_note_service),
) -> Any:
    """Undo a note deletion, until the grace-window purge removes the row."""
    logger.info("Endpoint POST /batches/%s/notes/%s/restore", batch_id, note_id)
    if not note_service.restore_note(batch_id, note_id):
        raise HTTPException(status_code=404, detail="Note not found or not deleted")
    return note_service.get_for_batch(batch_id, note_id)


# ---------------------------------------------------------------------------
# Dry hops sub-resource
# ---------------------------------------------------------------------------

@router.post(
    "/{batch_id}/dry-hops",
    tags=[BATCHES_DRY_HOPS],
    response_model=List[BatchDryHopResponse],
    status_code=201,
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def create_dry_hops(
    batch_id: uuid.UUID,
    hops: List[BatchDryHopCreate] = Body(..., max_length=1000),
    batch_service: BatchService = Depends(get_batch_service),
    dry_hop_service: BatchDryHopService = Depends(get_dry_hop_service),
) -> List[Any]:
    """Bulk-add dry hops to a batch."""
    logger.info("Endpoint POST /batches/%s/dry-hops (%d hops)", batch_id, len(hops))
    batch = batch_service.get(batch_id)
    if batch is None or batch.deleted_at is not None or batch.status == BatchStatus.ARCHIVED.value:
        raise HTTPException(status_code=404, detail="Batch not found")
    return dry_hop_service.create_list_for_batch(batch_id, hops)


@router.patch(
    "/{batch_id}/dry-hops/{hop_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[BATCHES_DRY_HOPS],
    response_model=BatchDryHopResponse,
    dependencies=[Depends(api_key_auth)],
)
async def update_dry_hop(
    batch_id: uuid.UUID,
    hop_id: uuid.UUID,
    hop_update: BatchDryHopUpdate,
    dry_hop_service: BatchDryHopService = Depends(get_dry_hop_service),
) -> Any:
    """Update a dry hop, including marking it complete or clearing that.

    Replaces POST /dry-hops/{id}/complete — completion is a timestamp column, so the
    ordinary PATCH carries it, and unlike the old endpoint this one can undo it.
    """
    logger.info("Endpoint PATCH /batches/%s/dry-hops/%s", batch_id, hop_id)
    hop = dry_hop_service.update_hop(batch_id, hop_id, hop_update)
    if hop is None:
        raise HTTPException(status_code=404, detail="Dry hop not found")
    return hop


@router.delete(
    "/{batch_id}/dry-hops/{hop_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[BATCHES_DRY_HOPS],
    status_code=204,
    dependencies=[Depends(api_key_auth)],
)
async def delete_dry_hop(
    batch_id: uuid.UUID,
    hop_id: uuid.UUID,
    dry_hop_service: BatchDryHopService = Depends(get_dry_hop_service),
) -> None:
    """Soft-delete a dry hop entry."""
    logger.info("Endpoint DELETE /batches/%s/dry-hops/%s", batch_id, hop_id)
    if not dry_hop_service.delete_hop(batch_id, hop_id):
        raise HTTPException(status_code=404, detail="Dry hop not found")
