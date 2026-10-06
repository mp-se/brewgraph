# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Sanitized anonymous public-display response schemas."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from oss.schemas._camel import to_camel


class _PublicDisplayModel(BaseModel):
    """Base configuration for the public-display wire contract."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class PublicDisplayContextResponse(_PublicDisplayModel):
    """Low-churn venue presentation settings for the public display."""

    brewery_name: Optional[str] = None
    logo_url: Optional[str] = None
    theme: Literal["dark", "light", "chalkboard", "minimal"] = "dark"
    primary_color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class PublicLastPour(_PublicDisplayModel):
    """The latest public-safe pour for a currently served keg."""

    at: datetime
    amount: float
    volume_remaining: float


class PublicServing(_PublicDisplayModel):
    """Current, bounded serving snapshot for one keg; never history."""

    serving_since: datetime
    total_volume: float
    volume_remaining: float
    volume_poured: float
    temperature: Optional[float] = None
    temperature_at: Optional[datetime] = None
    pressure: Optional[float] = None
    pressure_at: Optional[datetime] = None
    last_pour: Optional[PublicLastPour] = None


class PublicTapItem(_PublicDisplayModel):
    """One tap position, with recipe fields absent while it is empty."""

    tap_name: str
    beer_name: Optional[str] = None
    style: Optional[str] = None
    abv: Optional[float] = None
    ibu: Optional[float] = None
    ebc: Optional[float] = None
    # Required-with-null: empty tap cards need an explicit null rather than an
    # absent property so the client has one stable serving-state branch.
    serving: Optional[PublicServing]

    @model_serializer(mode="wrap")
    def _omit_empty_recipe_fields(self, handler, _info):
        """Omit unavailable recipe data while retaining ``serving: null``."""
        return {
            key: value
            for key, value in handler(self).items()
            if value is not None or key == "serving"
        }


class PublicBottleItem(_PublicDisplayModel):
    """One public packaged-bottle inventory item."""

    beer_name: str
    style: Optional[str] = None
    abv: Optional[float] = None
    ibu: Optional[float] = None
    ebc: Optional[float] = None
    bottle_volume: float
    bottles_remaining: int
    total_bottle_count: int
    availability: Literal["available"] = "available"

    @model_serializer(mode="wrap")
    def _omit_empty_recipe_fields(self, handler, _info):
        """Keep optional recipe values out of the public wire when unknown."""
        return {key: value for key, value in handler(self).items() if value is not None}


from oss.schemas.registry import register  # noqa: E402  # pylint: disable=wrong-import-position

register("PublicDisplayContextResponse", PublicDisplayContextResponse)
register("PublicTapItem", PublicTapItem)
register("PublicBottleItem", PublicBottleItem)
