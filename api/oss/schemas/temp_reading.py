# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""TempReading Pydantic schemas."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from core.enums import TempType
from oss.precision import quantised
from oss.schemas._camel import to_camel


class TempReadingCreate(BaseModel):
    """Used when creating a temperature reading."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    vessel_id: Optional[uuid.UUID] = None
    batch_id: Optional[uuid.UUID] = None
    device_id: Optional[uuid.UUID] = None
    temperature: float = Field(..., ge=-270.0, le=200.0)
    # battery is volts, not a percentage — nullable because the one device type
    # writing this table today (chamber_controller) is mains-powered and sends none.
    battery: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    rssi: Optional[float] = Field(default=None, ge=-200, le=0)
    # Validated against the enum, stored as a string -- same pattern as device_type,
    # so a new placement needs no migration.
    temp_type: TempType = Field(default=TempType.BEER)
    is_aggregate: bool = False
    excluded: bool = Field(default=False)
    created_at: Optional[datetime] = None

    _quantise_temperature = quantised("temperature", quantity="temperature")
    _quantise_battery = quantised("battery", quantity="battery")
    _quantise_rssi = quantised("rssi", quantity="signal")


class TempReadingUpdate(BaseModel):
    """Used when updating a temperature reading.

    Every field optional: a PATCH that only flips `excluded` must not have to
    resend the measurement.
    """

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    temperature: Optional[float] = Field(default=None, ge=-270.0, le=200.0)
    battery: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    rssi: Optional[float] = Field(default=None, ge=-200, le=0)
    temp_type: Optional[TempType] = None
    excluded: Optional[bool] = None

    _quantise_temperature = quantised("temperature", quantity="temperature")
    _quantise_battery = quantised("battery", quantity="battery")
    _quantise_rssi = quantised("rssi", quantity="signal")


class TempReadingResponse(TempReadingCreate):
    """Full temperature reading response including DB-assigned fields."""

    id: int


class TempChartPoint(BaseModel):
    """Minimal projection for temperature chart endpoints.

    Deliberately terse keys (``t``, ``temp``) — this is a chart series, repeated
    once per point. ``tempType`` still follows the camelCase wire contract; it
    was the one field here that didn't, because the schema had no alias generator.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    t: datetime
    temp: float
    temp_type: TempType
