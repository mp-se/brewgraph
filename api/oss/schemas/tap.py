# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tap Pydantic schemas."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from oss.precision import quantised
from oss.schemas._camel import to_camel


class TapBase(BaseModel):
    """Shared tap fields."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    name: str = Field(max_length=60)
    tap_number: Optional[int] = None
    glass_size: Optional[float] = None
    location: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=200)

    _quantise_glass_size = quantised("glass_size", quantity="volume")


class TapCreate(TapBase):
    """Fields required to create a tap."""


class TapUpdate(BaseModel):
    """Partial-update payload for a tap."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    name: Optional[str] = Field(default=None, max_length=60)
    tap_number: Optional[int] = None
    glass_size: Optional[float] = None
    location: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=200)

    _quantise_glass_size = quantised("glass_size", quantity="volume")

    # A normal writable field rather than a stamp-on-request endpoint: the client
    # supplies the moment directly, so it can log a cleaning done yesterday or undo
    # a mis-click by writing an earlier timestamp or clearing it with null.
    last_cleaned_at: Optional[datetime] = None


class TapResponse(TapBase):
    """Full tap response including server-assigned fields.

    token_hash is intentionally excluded — it's an internal lookup hash only.
    """

    id: uuid.UUID
    version: int = 1
    token: Optional[str] = None
    last_cleaned_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TapDashboardResponse(TapResponse):
    """Tap with current vessel and batch info (populated by service join)."""
    vessel_id: Optional[uuid.UUID] = None
    vessel_name: Optional[str] = None
    vessel_type: Optional[str] = None
    volume_remaining: Optional[float] = None
    batch_name: Optional[str] = None
    batch_style: Optional[str] = None
    batch_id: Optional[uuid.UUID] = None


from oss.schemas.registry import \
    register  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

register("TapCreate", TapCreate)
register("TapUpdate", TapUpdate)
register("TapResponse", TapResponse)
