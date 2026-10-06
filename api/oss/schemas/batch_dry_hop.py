# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""BatchDryHop Pydantic schemas."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.enums import DryHopTriggerMethod
from oss.precision import quantised
from oss.schemas._camel import to_camel


class BatchDryHopCreate(BaseModel):
    """Used when creating one or more dry hops."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    name: str = Field(..., max_length=60)
    amount: float = Field(..., gt=0)
    trigger_method: DryHopTriggerMethod = Field(
        default=DryHopTriggerMethod.HOURS_BEFORE_COMPLETION
    )
    trigger_gravity: Optional[float] = Field(default=None)
    trigger_hours_before: Optional[int] = Field(default=24)

    _quantise_amount = quantised("amount", quantity="mass")
    _quantise_trigger_gravity = quantised("trigger_gravity", quantity="gravity")

    @model_validator(mode="after")
    def validate_trigger_fields(self) -> "BatchDryHopCreate":
        """Require the trigger field matching trigger_method; clear the other."""
        if self.trigger_method == DryHopTriggerMethod.GRAVITY_LEVEL:
            if self.trigger_gravity is None:
                raise ValueError("trigger_gravity is required when trigger_method is gravity_level")
            self.trigger_hours_before = None
        else:
            if self.trigger_hours_before is None:
                raise ValueError(
                    "trigger_hours_before is required when trigger_method is "
                    "hours_before_completion"
                )
            self.trigger_gravity = None
        return self


class BatchDryHopUpdate(BaseModel):
    """Partial-update payload for a dry hop.

    Replaces `POST /dry-hops/{id}/complete`, which was a one-way idempotent stamp: a hop
    marked done by mistake could not be un-marked through the API at all. `completedAt`
    is an ordinary nullable field here, so clearing it is just another PATCH.

    Deliberately narrow. The trigger fields (`trigger_method`/`trigger_gravity`/
    `trigger_hours_before`) interlock — Create enforces that the field matching the
    method is set and the other cleared — and that rule cannot be checked against a
    partial payload without reading the stored row. Editing a trigger therefore still
    means delete-and-recreate until that interlock is redesigned; a half-validated
    partial update would be worse than not offering one.
    """

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    name: Optional[str] = Field(default=None, max_length=60)
    amount: Optional[float] = Field(default=None, gt=0)
    completed_at: Optional[datetime] = None

    _quantise_amount = quantised("amount", quantity="mass")


class BatchDryHopResponse(BatchDryHopCreate):
    """Full dry hop response including DB-assigned fields."""

    id: uuid.UUID
    batch_id: uuid.UUID
    triggered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


from oss.schemas.registry import register  # noqa: E402  # pylint: disable=wrong-import-position

register("BatchDryHopCreate", BatchDryHopCreate)
register("BatchDryHopResponse", BatchDryHopResponse)
