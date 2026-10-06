# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""TempReading model.

tenant_id is a bare column with no FK, matching Batch/Device/StorageVessel/Tap/GravityReading —
this app is single-tenant and every row carries DEFAULT_TENANT_ID; there is no tenant table
to reference.
"""
from datetime import UTC, datetime

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Float, ForeignKey, Identity, Index,
                        Integer, String, Uuid)
from sqlalchemy.orm import mapped_column, relationship

from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


class TempReading(Base):
    """Generic temperature ingest from any source."""

    __tablename__ = "temp_reading"
    __table_args__ = (
        CheckConstraint(
            "NOT (batch_id IS NOT NULL AND vessel_id IS NOT NULL)",
            name="ck_temp_reading_no_conflicting_context",
        ),
        Index("ix_temp_reading_vessel_created", "vessel_id", "created_at"),
        Index("ix_temp_reading_batch_created", "batch_id", "created_at"),
        Index("ix_temp_reading_tenant_id", "tenant_id"),
        Index("ix_temp_reading_tenant_vessel_created", "tenant_id", "vessel_id", "created_at"),
        Index("ix_temp_reading_tenant_batch_created", "tenant_id", "batch_id", "created_at"),
    )

    id = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), primary_key=True
    )
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    vessel_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("storage_vessel.id"), nullable=True, default=None
    )
    batch_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("batch.id"), nullable=True, default=None
    )
    device_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device.id"), nullable=True, default=None
    )
    temperature = mapped_column(Float, nullable=False)
    # battery is volts, not a percentage — see write_gravity's clamp in ingestion.py
    # for why (1S lithium voltage bound). Nullable: chamber_controller is the only
    # device type writing this table today and it is mains-powered, so it reports
    # no battery — the column exists for parity with GravityReading/PressureReading
    # and any future battery-powered temp probe.
    battery = mapped_column(Float, nullable=True, default=None)
    rssi = mapped_column(Float, nullable=True, default=None)
    temp_type = mapped_column(String(10), nullable=False, default="beer")
    is_aggregate = mapped_column(Boolean, nullable=False, default=False)
    excluded = mapped_column(Boolean, nullable=False, default=False)
    created_at = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC)
    )
    deleted_at = mapped_column(UtcDateTime(), nullable=True, default=None)

    vessel = relationship("StorageVessel", foreign_keys="TempReading.vessel_id")
    batch = relationship(
        "Batch", foreign_keys="TempReading.batch_id", back_populates="temp_readings"
    )
    device = relationship("Device", foreign_keys="TempReading.device_id")


register_model("TempReading", TempReading)
