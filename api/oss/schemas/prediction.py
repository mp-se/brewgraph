# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Prediction Pydantic schemas."""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from core.enums import PredictionOutcome, PredictionType
from oss.schemas._camel import to_camel


class PredictionBase(BaseModel):
    """Shared fields for all prediction schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    batch_id: Optional[uuid.UUID] = None
    device_id: Optional[uuid.UUID] = None
    vessel_id: Optional[uuid.UUID] = None
    tap_id: Optional[uuid.UUID] = None
    prediction_type: PredictionType = PredictionType.FERMENTATION_PROGRESS
    outcome: PredictionOutcome
    hours_left: Optional[float] = None
    confidence: Optional[float] = None
    # Type-specific payload in the standard envelope. Consumers must ignore keys
    # they do not recognise rather than rejecting the response.
    details: Dict[str, Any] = Field(default_factory=dict)


class PredictionCreate(PredictionBase):
    """Used when creating a prediction entry."""


class PredictionResponse(PredictionBase):
    """Full prediction response with server-assigned id and timestamp."""

    id: int
    created_at: datetime
