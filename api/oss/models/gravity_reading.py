# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""GravityReading model.

tenant_id is a bare column with no FK, matching Batch/Device/StorageVessel/Tap — this app is
single-tenant and every row carries DEFAULT_TENANT_ID; there is no tenant table to reference.
"""
from datetime import UTC, datetime

from sqlalchemy import (BigInteger, Boolean, Float, ForeignKey, Identity,
                        Index, Integer, Uuid)
from sqlalchemy.orm import mapped_column, relationship

from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


class GravityReading(Base):
    """Time-series gravity reading from a sensor device."""

    __tablename__ = "gravity_reading"
    __table_args__ = (
        Index("ix_gravity_reading_batch_created", "batch_id", "created_at"),
        Index("ix_gravity_reading_device_created", "device_id", "created_at"),
        Index("ix_gravity_reading_tenant_batch_created", "tenant_id", "batch_id", "created_at"),
    )

    id = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), primary_key=True
    )
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    batch_id = mapped_column(Uuid(as_uuid=True), ForeignKey("batch.id"), nullable=False)
    device_id = mapped_column(Uuid(as_uuid=True), ForeignKey("device.id"), nullable=True)
    temperature = mapped_column(Float, nullable=True)
    gravity = mapped_column(Float, nullable=False)
    angle = mapped_column(Float, nullable=True)
    velocity = mapped_column(Float, nullable=True)
    battery = mapped_column(Float, nullable=True)
    rssi = mapped_column(Float, nullable=True)
    run_time = mapped_column(Float, nullable=True)
    excluded = mapped_column(Boolean, nullable=False, default=False)
    is_aggregate = mapped_column(Boolean, nullable=False, default=False)
    deleted_at = mapped_column(UtcDateTime(), nullable=True, default=None)
    created_at = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC)
    )

    batch = relationship("Batch", back_populates="gravity_readings")
    device = relationship("Device", back_populates="gravity_readings")


register_model("GravityReading", GravityReading)
