# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Batch Pydantic schemas."""
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from pydantic import (BaseModel, ConfigDict, Field, computed_field,
                       field_serializer, field_validator)

from core.enums import BatchStatus
from oss.precision import quantise, quantised
from oss.schemas._camel import to_camel
from oss.schemas.batch_dry_hop import BatchDryHopCreate, BatchDryHopResponse  # noqa: F401


class BatchBase(BaseModel):
    """Fields shared by all batch schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    name: str = Field(default="", max_length=60)
    description: Optional[str] = Field(default=None, max_length=200)
    accept_ingest: bool = Field(default=True)
    brew_date: Optional[date] = Field(default=None)
    style: Optional[str] = Field(default=None, max_length=60)
    brewer: Optional[str] = Field(default=None, max_length=60)
    og: Optional[float] = Field(default=None)
    fg: Optional[float] = Field(default=None)
    abv: Optional[float] = Field(default=None)
    ebc: Optional[float] = Field(default=None)
    ibu: Optional[float] = Field(default=None)
    carbonation_volumes: Optional[float] = Field(default=None)
    brewfather_batch_id: Optional[str] = Field(default=None, max_length=40)
    volume: Optional[float] = Field(default=None)
    package_date: Optional[date] = Field(default=None)
    conditioning_days: Optional[int] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    yeast: Optional[str] = Field(default=None, max_length=100)
    yeast_product_id: Optional[str] = Field(default=None, max_length=40)
    gravity_device_id: Optional[uuid.UUID] = Field(default=None)
    pressure_device_id: Optional[uuid.UUID] = Field(default=None)
    temp_device_id: Optional[uuid.UUID] = Field(default=None)
    recipe_cost: Optional[Decimal] = Field(default=None)
    cost_currency: Optional[str] = Field(default=None, max_length=3)
    status: BatchStatus = Field(default=BatchStatus.FERMENTING)

    _quantise_gravity = quantised("og", "fg", quantity="gravity")
    _quantise_abv = quantised("abv", quantity="percent")
    _quantise_volume = quantised("volume", quantity="volume")

    @field_serializer("recipe_cost")
    def serialize_recipe_cost(self, value: Optional[Decimal]) -> Optional[float]:
        """Emit `recipe_cost` as a JSON number, not Pydantic's Decimal-as-string default.

        `Decimal` is right for currency in the column and in Python; it is wrong on the
        wire. Without this, Pydantic serialises the field as a *string* and declares it
        `type: string` in the OpenAPI schema — while `cost_per_liter`, computed from it,
        is a plain number. A client could not divide one by the other.

        The default bites regardless of backend, because the annotation coerces a float
        to `Decimal` on the way in: SQLite hands back a float and the output is still
        `"12.34"`. That is why no test caught it — nothing asserted the JSON *type*.

        `web/src/modules/backup/exportDocument.ts` declares `recipeCost: number | null`
        and copies the API's value straight into a `brewgraph-batch-export-v1` document,
        where the schema requires a number. So the string reached the export too.
        """
        return float(value) if value is not None else None

    @computed_field
    @property
    def cost_per_liter(self) -> Optional[float]:
        """Recipe cost per litre, derived from recipe_cost / volume.

        Not a column: storing both invited drift — edit volume after import and
        a persisted cost_per_liter goes stale while this stays correct. Returns
        None if either input is missing, or volume is zero (never divide by it).
        Quantised to 2dp: a per-litre ratio, not an amount payable, so currency
        minor units don't apply — see the "money" entry in precision.py.
        """
        if self.recipe_cost is None or not self.volume:
            return None
        return quantise(float(self.recipe_cost) / self.volume, "money")


class BatchCreate(BatchBase):
    """Used when creating a new batch."""

    dry_hops: Optional[List["BatchDryHopCreate"]] = Field(default=None)


class BatchUpdate(BatchBase):
    """Used when updating a batch."""

    og_measured: Optional[float] = Field(default=None)
    fg_measured: Optional[float] = Field(default=None)
    rating: Optional[int] = Field(default=None)

    _quantise_measured_gravity = quantised("og_measured", "fg_measured", quantity="gravity")

    @field_validator("rating")
    @classmethod
    def _validate_rating(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= 5:
            raise ValueError("rating must be between 1 and 5")
        return v


class BatchResponse(BatchCreate):
    """Full batch response."""

    id: uuid.UUID
    version: int = 1
    created_at: datetime
    updated_at: datetime
    chamber_control_active: bool = False
    og_measured: Optional[float] = Field(default=None)
    fg_measured: Optional[float] = Field(default=None)
    rating: Optional[int] = Field(default=None)

    _quantise_measured_gravity = quantised("og_measured", "fg_measured", quantity="gravity")

    # Reads Batch.active_dry_hops (filtered), not the raw cascade-managed
    # `dry_hops` relationship — see oss/models/batch.py.
    dry_hops: List["BatchDryHopResponse"] = Field(
        default_factory=list, validation_alias="active_dry_hops"
    )

    @computed_field
    @property
    def ready_date(self) -> Optional[date]:
        """Estimated ready-to-serve date: package_date + conditioning_days."""
        if self.package_date and self.conditioning_days:
            return self.package_date + timedelta(days=self.conditioning_days)
        return None


class BatchListResponse(BatchResponse):
    """Batch list view with reading counts."""

    gravity_count: int = 0
    pressure_count: int = 0
    temperature_count: int = 0


from oss.schemas.registry import \
    register  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

register("BatchCreate", BatchCreate)
register("BatchUpdate", BatchUpdate)
register("BatchResponse", BatchResponse)
register("BatchListResponse", BatchListResponse)
