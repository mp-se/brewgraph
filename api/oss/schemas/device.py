# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Device Pydantic schemas."""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.enums import DeviceBatchRole, DeviceColor, DeviceStatus
from core.schemas.envelope import build_envelope, reject_if_too_large
from oss.registries.device_types import device_type_registry
from oss.schemas._camel import to_camel


class DeviceBase(BaseModel):
    """Write schema for Device (create / update)."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    batch_id: Optional[uuid.UUID] = Field(default=None)
    batch_role: Optional[DeviceBatchRole] = Field(default=None)
    vessel_id: Optional[uuid.UUID] = Field(default=None)
    name: str = Field(default="", max_length=60)
    chip_id: Optional[str] = Field(default=None, max_length=32)
    device_type: Optional[str] = Field(default=None, max_length=20)
    mdns: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = Field(default=None, max_length=200)
    chip_family: Optional[str] = Field(default=None, max_length=10)
    board: Optional[str] = Field(default=None, max_length=10)
    gyro_model: Optional[str] = Field(default=None, max_length=20)
    device_filtered: bool = Field(default=False)
    url: Optional[str] = Field(default=None, max_length=80)
    # A brewer-owned backup of the device's own configuration, stored verbatim in the
    # standard envelope. A firmware that answers `proxy_fetch` with plain text rather
    # than JSON is accepted and kept as {"raw": "..."} — the server does not interpret
    # this field, so refusing it would only lose the backup.
    config: Optional[Union[Dict[str, Any], str]] = Field(default=None)

    @field_validator("config", mode="before")
    @classmethod
    def _wrap_config(cls, value):
        """Normalise whatever the device returned into an envelope."""
        if value is None or value == "":
            return None
        payload = value if isinstance(value, dict) else {"raw": str(value)}
        if payload.get("kind") == "device-config" and "data" in payload:
            return reject_if_too_large(payload, "config")
        return reject_if_too_large(
            build_envelope("device-config", payload, source="proxy_fetch"), "config"
        )
    device_color: DeviceColor = Field(default=DeviceColor.WHITE)
    collect_logs: bool = Field(default=False)

    @field_validator("device_type")
    @classmethod
    def _device_type_must_be_registered(cls, value: Optional[str]) -> Optional[str]:
        """Reject any device_type not registered by this build."""
        if value is not None and not device_type_registry.is_registered(value):
            raise ValueError(f"unregistered device_type: {value!r}")
        return value


DeviceCreate = DeviceBase
DeviceUpdate = DeviceBase


class DeviceResponse(DeviceBase):
    """Read schema for Device (API response)."""

    id: uuid.UUID
    token: Optional[str] = None
    failed_ingest_counter: int = 0
    created_at: datetime
    updated_at: datetime


class DeviceStatusResponse(BaseModel):
    """Computed connectivity status for a single device."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    device_id: uuid.UUID
    status: DeviceStatus
    last_seen_at: Optional[datetime] = None


__all__ = ["DeviceBase", "DeviceCreate", "DeviceUpdate", "DeviceResponse", "DeviceStatusResponse"]


from oss.schemas.registry import \
    register  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

register("DeviceCreate", DeviceCreate)
register("DeviceUpdate", DeviceUpdate)
register("DeviceResponse", DeviceResponse)
