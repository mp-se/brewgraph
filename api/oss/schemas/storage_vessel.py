# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""StorageVessel Pydantic schemas."""
import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.enums import VesselStatus, VesselType
from oss.precision import quantise, quantised
from oss.schemas._camel import to_camel


def _check_vessel_quantities(
    total_volume: Optional[float],
    volume_remaining: Optional[float],
    bottle_count: Optional[int],
    bottles_remaining: Optional[int],
) -> None:
    """Cross-field invariant shared by StorageVesselBase and StorageVesselUpdate.

    `StorageVesselUpdate` does not inherit `StorageVesselBase` (every field is
    optional there for partial updates), so the check is a free function both
    can call rather than being duplicated. Only checks fields present together
    in the same payload -- a partial update supplying just one side of either
    pair is validated against the persisted row by the DB CHECK constraint on
    `storage_vessel`, not here.
    """
    if (
        total_volume is not None
        and volume_remaining is not None
        and volume_remaining > total_volume
    ):
        raise ValueError("volumeRemaining must not exceed totalVolume")
    if (
        bottle_count is not None
        and bottles_remaining is not None
        and bottles_remaining > bottle_count
    ):
        raise ValueError("bottlesRemaining must not exceed bottleCount")


class StorageVesselBase(BaseModel):
    """Shared fields for all storage vessel schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    batch_id: Optional[uuid.UUID] = None
    vessel_number: Optional[int] = None
    vessel_type: VesselType
    name: str = Field(max_length=60)
    fill_date: date
    total_volume: float = Field(ge=0)
    volume_remaining: float = Field(ge=0)
    bottle_volume: Optional[float] = None
    bottle_count: Optional[int] = Field(default=None, ge=0)
    bottles_remaining: Optional[int] = Field(default=None, ge=0)
    status: VesselStatus = VesselStatus.FILLED
    location: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=200)

    _quantise_volumes = quantised(
        "total_volume", "volume_remaining", "bottle_volume", quantity="volume"
    )

    @model_validator(mode="after")
    def _check_quantities(self) -> "StorageVesselBase":
        _check_vessel_quantities(
            self.total_volume, self.volume_remaining, self.bottle_count, self.bottles_remaining
        )
        return self


class StorageVesselCreate(StorageVesselBase):
    """Fields required to create a storage vessel.

    serving_temp_* / conditioning / priming / keg_identifier are left unset (None)
    here; when unset the service may derive style-based defaults.
    """

    batch_id: Optional[uuid.UUID] = None
    tap_id: Optional[uuid.UUID] = None
    fill_date: Optional[date] = None
    total_volume: Optional[float] = Field(default=None, ge=0)
    volume_remaining: Optional[float] = Field(default=None, ge=0)
    serving_temp_alert_enabled: Optional[bool] = None
    serving_temp_min: Optional[float] = None
    serving_temp_max: Optional[float] = None
    conditioning_days: Optional[int] = None
    priming_sugar_type: Optional[str] = Field(default=None, max_length=20)
    priming_sugar_amount: Optional[float] = None
    conditioning_temp: Optional[float] = None
    carbonation_volumes_target: Optional[float] = None
    keg_identifier: Optional[str] = Field(default=None, max_length=60)

    _quantise_temps = quantised(
        "serving_temp_min", "serving_temp_max", "conditioning_temp", quantity="temperature"
    )
    _quantise_priming_sugar = quantised("priming_sugar_amount", quantity="mass")

    @model_validator(mode="after")
    def _derive_defaults(self) -> "StorageVesselCreate":
        if self.fill_date is None:
            self.fill_date = date.today()
        # fill_date/total_volume/volume_remaining are NOT NULL on the shared model, so every
        # one of them has to be derived here rather than reaching the DB unset.
        if self.total_volume is None:
            if self.vessel_type == VesselType.BOTTLES and self.bottle_count and self.bottle_volume:
                self.total_volume = quantise(self.bottle_count * self.bottle_volume, "volume")
            else:
                self.total_volume = 0.0
        if self.volume_remaining is None:
            if self.vessel_type == VesselType.BOTTLES and self.bottle_count and self.bottle_volume:
                self.volume_remaining = quantise(
                    self.bottle_count * self.bottle_volume, "volume"
                )
            else:
                self.volume_remaining = self.total_volume
        # Re-check after derivation: a caller can supply volume_remaining without
        # total_volume (or vice versa), in which case the base validator above ran
        # before either default was filled in and had nothing to compare.
        _check_vessel_quantities(
            self.total_volume, self.volume_remaining, self.bottle_count, self.bottles_remaining
        )
        return self


class StorageVesselUpdate(BaseModel):
    """Partial-update payload for a storage vessel."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    # batch_id and tap_id replaced the dedicated assign-batch/assign-tap endpoints.
    # For both, an explicit null is a *command* — "empty the keg", "release from the
    # tap" — and is not the same as omitting the field. The service therefore keys off
    # `model_dump(exclude_unset=True)`, never `is None`; see StorageVesselService.update.
    batch_id: Optional[uuid.UUID] = None
    tap_id: Optional[uuid.UUID] = None
    vessel_number: Optional[int] = None
    name: Optional[str] = Field(default=None, max_length=60)
    fill_date: Optional[date] = None
    total_volume: Optional[float] = Field(default=None, ge=0)
    volume_remaining: Optional[float] = Field(default=None, ge=0)
    bottle_volume: Optional[float] = None
    bottle_count: Optional[int] = Field(default=None, ge=0)
    bottles_remaining: Optional[int] = Field(default=None, ge=0)
    status: Optional[VesselStatus] = None
    location: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=200)
    serving_temp_alert_enabled: Optional[bool] = None
    serving_temp_min: Optional[float] = None
    serving_temp_max: Optional[float] = None
    conditioning_days: Optional[int] = None
    priming_sugar_type: Optional[str] = Field(default=None, max_length=20)
    priming_sugar_amount: Optional[float] = None
    conditioning_temp: Optional[float] = None
    carbonation_volumes_target: Optional[float] = None
    keg_identifier: Optional[str] = Field(default=None, max_length=60)

    _quantise_volumes = quantised(
        "total_volume", "volume_remaining", "bottle_volume", quantity="volume"
    )
    _quantise_temps = quantised(
        "serving_temp_min", "serving_temp_max", "conditioning_temp", quantity="temperature"
    )
    _quantise_priming_sugar = quantised("priming_sugar_amount", quantity="mass")

    @model_validator(mode="after")
    def _check_quantities(self) -> "StorageVesselUpdate":
        _check_vessel_quantities(
            self.total_volume, self.volume_remaining, self.bottle_count, self.bottles_remaining
        )
        return self


class StorageVesselResponse(StorageVesselBase):
    """Full storage vessel response with server-assigned fields."""

    id: uuid.UUID
    version: int = 1
    tap_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    serving_temp_alert_enabled: bool = False
    serving_temp_min: Optional[float] = None
    serving_temp_max: Optional[float] = None
    conditioning_days: Optional[int] = None
    priming_sugar_type: Optional[str] = None
    priming_sugar_amount: Optional[float] = None
    conditioning_temp: Optional[float] = None
    carbonation_volumes_target: Optional[float] = None
    keg_identifier: Optional[str] = Field(default=None, max_length=60)
    fill_count: int = 1

    _quantise_temps = quantised(
        "serving_temp_min", "serving_temp_max", "conditioning_temp", quantity="temperature"
    )
    _quantise_priming_sugar = quantised("priming_sugar_amount", quantity="mass")


class StorageVesselListResponse(StorageVesselResponse):
    """Vessel list view with pour count and denormalised batch name."""

    pour_count: int = 0
    batch_name: Optional[str] = None


from oss.schemas.registry import \
    register  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

register("StorageVesselCreate", StorageVesselCreate)
register("StorageVesselUpdate", StorageVesselUpdate)
register("StorageVesselResponse", StorageVesselResponse)
register("StorageVesselListResponse", StorageVesselListResponse)
