# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Platform Pydantic schemas (TenantSettings, SystemLog, IngestionLog)."""
import uuid
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from core.enums import (GravityFormat, IngestionSource, PressureFormat,
                        TemperatureFormat, VolumeFormat)
from oss.schemas._camel import to_camel

# ---------------------------------------------------------------------------
# TenantSettings
# ---------------------------------------------------------------------------

class TenantSettingsBase(BaseModel):
    """Fields shared by all TenantSettings schemas."""
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    temperature_format: TemperatureFormat = TemperatureFormat.CELSIUS
    gravity_format: GravityFormat = GravityFormat.SG
    pressure_format: PressureFormat = PressureFormat.KPA
    volume_format: VolumeFormat = VolumeFormat.METRIC
    brewery_name: Optional[str] = Field(default=None, max_length=100)
    logo_url: Optional[str] = Field(default=None, max_length=2048)
    theme: Literal["dark", "light", "chalkboard", "minimal"] = "dark"
    primary_color: Optional[str] = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )


class TenantSettingsCreate(TenantSettingsBase):
    """Used when creating TenantSettings."""


class TenantSettingsUpdate(TenantSettingsBase):
    """Used when updating TenantSettings."""


class TenantSettingsResponse(TenantSettingsBase):
    """Full TenantSettings response with id.

    `precision` is read-only metadata sourced from `oss.precision.DECIMALS` at
    response time -- it is never present on `TenantSettingsBase`/`*Update`, so
    it cannot be PATCHed.
    """
    id: uuid.UUID
    backup_source_id: uuid.UUID
    precision: Dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# SystemLog
# ---------------------------------------------------------------------------

class SystemLogBase(BaseModel):
    """Fields shared by all SystemLog schemas."""
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    level: str = Field(default="INFO", max_length=10)
    event: str = Field(max_length=80)
    message: str = Field(max_length=500)


class SystemLogCreate(SystemLogBase):
    """Used when creating a SystemLog entry."""


class SystemLogResponse(SystemLogBase):
    """Full SystemLog response with id and timestamp."""
    id: int
    created_at: datetime


class SystemLogPaginatedResponse(BaseModel):
    """Paginated response wrapper for SystemLog."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    total: int
    skip: int
    limit: int
    data: List[SystemLogResponse]


# ---------------------------------------------------------------------------
# IngestionLog
# ---------------------------------------------------------------------------

class IngestionLogBase(BaseModel):
    """Fields shared by all IngestionLog schemas."""
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    device_id: uuid.UUID | None = Field(default=None)
    source_type: IngestionSource
    device_type: str = Field(default="", max_length=12)
    ip_address: str = Field(max_length=45)
    reason: str = Field(max_length=30)
    error_detail: str | None = Field(default=None, max_length=200)
    payload: str | None = Field(default=None, max_length=4096)


class IngestionLogCreate(IngestionLogBase):
    """Used when creating an IngestionLog entry."""


class IngestionLogResponse(IngestionLogBase):
    """Full IngestionLog response with id and timestamp."""
    id: int
    created_at: datetime
    # Overrides the base's `str` (default="") — Oracle silently stores an inserted empty
    # string as NULL for VARCHAR2 columns (a longstanding Oracle-specific behavior, absent
    # on SQLite/Postgres), so a row written with device_type="" reads back as None here.
    # The column is nullable=True already; this just makes the response schema honest
    # about it instead of rejecting a value the database itself produced.
    device_type: str | None = Field(default=None, max_length=12)


class IngestionLogPaginatedResponse(BaseModel):
    """Paginated response wrapper for IngestionLog."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    total: int
    skip: int
    limit: int
    data: List[IngestionLogResponse]


class SchedulerJobStatus(BaseModel):
    """One scheduled job and when it next runs."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str
    next_run_in: Optional[int] = Field(
        default=None,
        description="Seconds until the next run, or null when the job has none scheduled.",
    )


class MdnsDevice(BaseModel):
    """A device discovered on the local network by the mDNS sidecar.

    Deliberately permissive: the payload is whatever the sidecar cached, and this
    schema documents the fields it is known to publish without rejecting a record
    that carries more.
    """

    model_config = ConfigDict(extra="allow", alias_generator=to_camel, populate_by_name=True)

    name: Optional[str] = None
    host: Optional[str] = None
    address: Optional[str] = None
    port: Optional[int] = None


class IngestEndpointResponse(BaseModel):
    """One ingest endpoint, as advertised to a device-configuration UI."""

    model_config = ConfigDict(extra="allow", alias_generator=to_camel, populate_by_name=True)

    device: Optional[str] = None
    path: Optional[str] = None
    method: Optional[str] = None


class HealthResponse(BaseModel):
    """Liveness answer for the deploy pipeline's health probe."""

    status: str
