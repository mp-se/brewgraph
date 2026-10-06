# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Predictions API — tenant-wide listing with optional filters."""
import logging
import uuid
from typing import Any, List, Optional

from fastapi import Depends, HTTPException, Query
from fastapi.routing import APIRouter

from core.schemas.errors import ErrorResponse
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.schemas.prediction import PredictionResponse
from oss.services import get_prediction_service
from oss.services.prediction import PredictionService

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/predictions", tags=["predictions"], dependencies=[Depends(api_key_auth)]
)


@router.get(
    "",
    response_model=List[PredictionResponse],
    dependencies=[Depends(api_key_auth)],
)
async def list_predictions(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    batch_id: Optional[uuid.UUID] = Query(None, alias="batchId"),
    device_id: Optional[uuid.UUID] = Query(None, alias="deviceId"),
    vessel_id: Optional[uuid.UUID] = Query(None, alias="vesselId"),
    tap_id: Optional[uuid.UUID] = Query(None, alias="tapId"),
    prediction_type: Optional[str] = Query(None, alias="type"),
    limit: int = Query(200, ge=1, le=1000),
    prediction_service: PredictionService = Depends(get_prediction_service),
) -> Any:
    """List predictions, optionally filtered by batch, device, vessel, or type."""
    logger.info(
        "Endpoint GET /predictions batchId=%s deviceId=%s vesselId=%s tapId=%s type=%s",
        batch_id, device_id, vessel_id, tap_id, prediction_type,
    )
    return prediction_service.list_all(
        batch_id=batch_id,
        device_id=device_id,
        vessel_id=vessel_id,
        tap_id=tap_id,
        prediction_type=prediction_type,
        limit=limit,
    )


@router.delete(
    "/{prediction_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse, "description": "Prediction not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def delete_prediction(
    prediction_id: int,
    prediction_service: PredictionService = Depends(get_prediction_service),
) -> None:
    """Dismiss a prediction the brewer knows is wrong.

    Soft delete: the row stops appearing anywhere the UI reads, and the purge job
    removes it once the grace window elapses. There is no PATCH — every field is
    model output, and editing one would claim the model said something it did not.
    """
    logger.info("Endpoint DELETE /predictions/%s", prediction_id)
    if not prediction_service.soft_delete(prediction_id):
        raise HTTPException(status_code=404, detail="Prediction not found")


@router.post(
    "/{prediction_id}/restore",
    response_model=PredictionResponse,
    responses={404: {"model": ErrorResponse, "description": "Prediction not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def restore_prediction(
    prediction_id: int,
    prediction_service: PredictionService = Depends(get_prediction_service),
) -> Any:
    """Undo a dismissal, putting the prediction back in every read path.

    An action endpoint rather than a field write: predictions have no PATCH, because
    every other field is model output. Only available until the grace-window purge
    removes the row.
    """
    logger.info("Endpoint POST /predictions/%s/restore", prediction_id)
    restored = prediction_service.restore(prediction_id)
    if restored is None:
        raise HTTPException(status_code=404, detail="Prediction not found or not dismissed")
    return restored
