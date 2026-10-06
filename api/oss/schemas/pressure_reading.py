# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""PressureReading Pydantic schemas."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from oss.precision import quantised
from oss.schemas._camel import to_camel


class PressureReadingBase(BaseModel):
    """Fields shared by all pressure reading schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    temperature: Optional[float] = Field(default=None)
    pressure: float
    battery: Optional[float] = Field(default=None)
    rssi: Optional[float] = Field(default=None)
    run_time: Optional[float] = Field(default=None)
    excluded: bool = Field(default=False)

    _quantise_temperature = quantised("temperature", quantity="temperature")
    _quantise_pressure = quantised("pressure", quantity="pressure")
    _quantise_battery = quantised("battery", quantity="battery")
    _quantise_rssi = quantised("rssi", quantity="signal")


class PressureReadingCreate(PressureReadingBase):
    """Used when creating a pressure reading."""

    batch_id: Optional[uuid.UUID] = None
    vessel_id: Optional[uuid.UUID] = None
    device_id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None


class PressureReadingUpdate(PressureReadingBase):
    """Used when updating a pressure reading."""


class PressureReadingResponse(PressureReadingCreate):
    """Full pressure reading response."""

    id: int


class PressureChartPoint(BaseModel):
    """Minimal projection for pressure chart endpoints."""

    t: datetime
    p: float
    temp: Optional[float] = None


from oss.schemas.registry import \
    register  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

register("PressureReadingCreate", PressureReadingCreate)
register("PressureReadingUpdate", PressureReadingUpdate)
register("PressureReadingResponse", PressureReadingResponse)
