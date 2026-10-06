# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""PressureReading model.

tenant_id is a bare column with no FK, matching Batch/Device/StorageVessel/Tap — this app is
single-tenant and every row carries DEFAULT_TENANT_ID; there is no tenant table to reference.
"""
from datetime import UTC, datetime

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Float, ForeignKey, Identity,
                        Index, Integer, Uuid)
from sqlalchemy.orm import mapped_column, relationship

from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


class PressureReading(Base):
    """Time-series pressure reading from a sensor device."""

    __tablename__ = "pressure_reading"
    __table_args__ = (
        CheckConstraint(
            "batch_id IS NOT NULL OR vessel_id IS NOT NULL",
            name="ck_pressure_reading_has_context",
        ),
        Index("ix_pressure_reading_batch_created", "batch_id", "created_at"),
        Index("ix_pressure_reading_vessel_created", "vessel_id", "created_at"),
        Index("ix_pressure_reading_device_created", "device_id", "created_at"),
        Index("ix_pressure_reading_tenant_id", "tenant_id"),
    )

    id = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), primary_key=True
    )
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    batch_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("batch.id"), nullable=True, default=None
    )
    vessel_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("storage_vessel.id"), nullable=True, default=None
    )
    device_id = mapped_column(Uuid(as_uuid=True), ForeignKey("device.id"), nullable=True)
    temperature = mapped_column(Float, nullable=True)
    pressure = mapped_column(Float, nullable=False)
    battery = mapped_column(Float, nullable=True)
    rssi = mapped_column(Float, nullable=True)
    run_time = mapped_column(Float, nullable=True)
    excluded = mapped_column(Boolean, nullable=False, default=False)
    is_aggregate = mapped_column(Boolean, nullable=False, default=False)
    deleted_at = mapped_column(UtcDateTime(), nullable=True, default=None)
    created_at = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC)
    )

    batch = relationship("Batch", back_populates="pressure_readings")
    vessel = relationship("StorageVessel", back_populates="pressure_readings")
    device = relationship("Device", back_populates="pressure_readings")


register_model("PressureReading", PressureReading)
