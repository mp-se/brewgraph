# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""PourEvent Pydantic schemas."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from oss.precision import quantised
from oss.schemas._camel import to_camel


class PourEventBulkCreate(BaseModel):
    """One row in a bulk pour-history import (volume_remaining is explicit).

    Exists as a separate schema (unlike gravity/pressure which reuse their Create schemas for bulk)
    because the normal PourEventCreate service path decrements volume_remaining on the vessel as a
    side effect. For restore, the correct values are already known, so this schema bypasses that
    logic. Consider replacing with a flag on the service method to consolidate.
    """

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    pour_amount: float = Field(ge=0)
    volume_remaining: float
    is_manual: bool = False
    created_at: Optional[datetime] = None

    _quantise_volumes = quantised("pour_amount", "volume_remaining", quantity="volume")


class PourEventCreate(BaseModel):
    """Fields required to record a keg pour against a vessel."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    pour_amount: float = Field(gt=0)
    # When the pour happened; the time of the request when omitted.
    created_at: Optional[datetime] = None

    _quantise_pour_amount = quantised("pour_amount", quantity="volume")


class BottlePourCreate(BaseModel):
    """Fields required to record consuming one or more bottles from a bottle vessel."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    bottle_count: int = Field(1, ge=1)
    # When the bottles were taken; the time of the request when omitted.
    created_at: Optional[datetime] = None


class PourEventResponse(BaseModel):
    """Full pour event response with computed volume remaining."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID
    vessel_id: uuid.UUID
    batch_id: Optional[uuid.UUID] = None
    pour_amount: float
    volume_remaining: float
    is_manual: bool
    excluded: bool
    created_at: datetime

    _quantise_volumes = quantised("pour_amount", "volume_remaining", quantity="volume")


from oss.schemas.registry import \
    register  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

register("PourEventCreate", PourEventCreate)
register("PourEventBulkCreate", PourEventBulkCreate)
register("BottlePourCreate", BottlePourCreate)
register("PourEventResponse", PourEventResponse)
