# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""FermentationStep Pydantic schemas."""
import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from oss.schemas._camel import to_camel


class FermentationStepBase(BaseModel):
    """Fields shared by all fermentation step schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    order: int = Field(default=0)
    type: str = Field(default="", max_length=30)
    name: str = Field(default="", max_length=30)
    temp: float = Field(default=0.0)
    days: int = Field(default=0)
    date: Optional[datetime.date] = None
    control: str = Field(default="", max_length=10)
    trigger_type: str = Field(default="day_offset", max_length=20)
    triggered_at: Optional[datetime.datetime] = None


class FermentationStepCreate(FermentationStepBase):
    """Used when creating a fermentation step."""

    batch_id: uuid.UUID
    device_id: Optional[uuid.UUID] = None


class FermentationStepUpdate(FermentationStepBase):
    """Used when updating a fermentation step."""

    order: Optional[int] = None
    type: Optional[str] = Field(default=None, max_length=30)
    name: Optional[str] = Field(default=None, max_length=30)
    temp: Optional[float] = None
    days: Optional[int] = None
    date: Optional[datetime.date] = None
    control: Optional[str] = Field(default=None, max_length=10)
    trigger_type: Optional[str] = Field(default=None, max_length=20)
    triggered_at: Optional[datetime.datetime] = None
    device_id: Optional[uuid.UUID] = None


class FermentationStepResponse(FermentationStepCreate):
    """Full fermentation step response including DB-assigned fields."""

    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime


# Auto-suggest defaults for a step template's trigger_type, keyed by the
# step's display name. Not wired into any auto-creation flow today —
# exported for future callers (e.g. a batch-creation flow or frontend
# defaults) to use.
STEP_NAME_TO_TRIGGER_TYPE = {
    "Primary": "terminal_gravity",
    "Diacetyl rest": "day_offset",
    "Cold crash": "day_offset",
}


def suggest_trigger_type(name: str) -> str:
    """Suggest a trigger_type for a fermentation step template name.

    Falls back to "day_offset" for any name not in STEP_NAME_TO_TRIGGER_TYPE.
    """
    return STEP_NAME_TO_TRIGGER_TYPE.get(name, "day_offset")
