# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""TenantSettings model (singleton settings row)."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Enum, String, Uuid
from sqlalchemy.orm import mapped_column

from core.enums import GravityFormat, PressureFormat, TemperatureFormat, VolumeFormat
from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model


class TenantSettings(Base):
    """Single-row application settings."""

    __tablename__ = "tenant_settings"

    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Random instance provenance for portable backups; never derived from host/customer data.
    backup_source_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=uuid.uuid4)
    temperature_format = mapped_column(
        Enum(TemperatureFormat, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=TemperatureFormat.CELSIUS,
    )
    gravity_format = mapped_column(
        Enum(GravityFormat, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=GravityFormat.SG,
    )
    pressure_format = mapped_column(
        Enum(PressureFormat, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=PressureFormat.KPA,
    )
    volume_format = mapped_column(
        Enum(VolumeFormat, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=VolumeFormat.METRIC,
    )
    # Presentation settings for the anonymous, deployment-exposed display.
    # They are deliberately not an enablement control: a self-hosted instance
    # decides reachability at its reverse proxy or network boundary.
    brewery_name = mapped_column(String(100), nullable=True, default=None)
    logo_url = mapped_column(String(2048), nullable=True, default=None)
    theme = mapped_column(String(20), nullable=False, default="dark")
    primary_color = mapped_column(String(7), nullable=True, default=None)
    updated_at = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC),
    )


register_model("TenantSettings", TenantSettings)
