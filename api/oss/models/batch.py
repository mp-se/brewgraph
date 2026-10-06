# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Batch model."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import (Boolean, Date, Float, ForeignKey, Index, event,
                        Integer, Numeric, String, Text, Uuid)
from sqlalchemy.orm import mapped_column, relationship

from core.enums import BatchStatus
from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


class Batch(Base):
    """Batch — a single brew from start to finish.

    tenant_id is a bare column with no FK. This app is single-tenant: every row carries
    DEFAULT_TENANT_ID, and there is no tenant table to reference.
    """

    __tablename__ = "batch"
    __table_args__ = (
        Index("ix_batch_tenant_id", "tenant_id"),
    )

    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    # Nullable, and no empty-string default: Oracle stores '' as NULL, so a NOT NULL
    # column defended only by default="" inserts NULL and violates its own constraint.
    name = mapped_column(String(60), nullable=True, default=None)
    description = mapped_column(String(200), nullable=True, default=None)
    accept_ingest = mapped_column(Boolean, nullable=False, default=True)
    brew_date = mapped_column(Date, nullable=True, default=None)
    style = mapped_column(String(60), nullable=True, default=None)
    brewer = mapped_column(String(60), nullable=True, default=None)
    og = mapped_column(Float, nullable=True, default=None)
    fg = mapped_column(Float, nullable=True, default=None)
    og_measured = mapped_column(Float, nullable=True, default=None)
    fg_measured = mapped_column(Float, nullable=True, default=None)
    abv = mapped_column(Float, nullable=True, default=None)
    ebc = mapped_column(Float, nullable=True, default=None)
    ibu = mapped_column(Float, nullable=True, default=None)
    carbonation_volumes = mapped_column(Float, nullable=True, default=None)
    brewfather_batch_id = mapped_column(String(40), nullable=True, default=None)
    volume = mapped_column(Float, nullable=True, default=None)
    package_date = mapped_column(Date, nullable=True, default=None)
    conditioning_days = mapped_column(Integer, nullable=True, default=None)
    rating = mapped_column(Integer, nullable=True, default=None)
    notes = mapped_column(Text, nullable=True, default=None)
    yeast = mapped_column(String(100), nullable=True, default=None)
    yeast_product_id = mapped_column(String(40), nullable=True, default=None)
    # Pitch-rate / viability inputs recorded alongside the yeast strain.
    yeast_amount = mapped_column(Float, nullable=True, default=None)
    yeast_amount_unit = mapped_column(String(10), nullable=True, default=None)
    yeast_form = mapped_column(String(10), nullable=True, default=None)
    yeast_starter_used = mapped_column(Boolean, nullable=True, default=None)
    yeast_starter_size_l = mapped_column(Float, nullable=True, default=None)
    yeast_manufacturing_date = mapped_column(Date, nullable=True, default=None)
    yeast_best_before_date = mapped_column(Date, nullable=True, default=None)
    yeast_generation = mapped_column(Integer, nullable=True, default=None)
    gravity_device_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device.id"), nullable=True, default=None
    )
    pressure_device_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device.id"), nullable=True, default=None
    )
    temp_device_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device.id"), nullable=True, default=None
    )
    recipe_cost = mapped_column(Numeric(10, 2), nullable=True, default=None)
    cost_currency = mapped_column(String(3), nullable=True, default=None)
    status = mapped_column(
        String(20), nullable=False, default=BatchStatus.FERMENTING.value
    )
    chamber_control_active = mapped_column(Boolean, nullable=False, default=False)
    version = mapped_column(Integer, nullable=False, default=1, server_default="1")
    deleted_at = mapped_column(UtcDateTime(), nullable=True, default=None)
    created_at = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at = mapped_column(
        UtcDateTime(),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    devices = relationship("Device", foreign_keys="Device.batch_id", back_populates="batch")
    gravity_readings = relationship(
        "GravityReading", back_populates="batch", cascade="all, delete-orphan"
    )
    pressure_readings = relationship(
        "PressureReading", back_populates="batch", cascade="all, delete-orphan"
    )
    predictions = relationship(
        "Prediction", back_populates="batch", cascade="all, delete-orphan"
    )
    storage_vessels = relationship(
        "StorageVessel", back_populates="batch", cascade="all, delete-orphan"
    )
    fermentation_steps = relationship(
        "FermentationStep", back_populates="batch", cascade="all, delete-orphan"
    )
    batch_notes = relationship(
        "BatchNote",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="BatchNote.created_at",
    )
    dry_hops = relationship(
        "BatchDryHop",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="BatchDryHop.created_at",
    )
    temp_readings = relationship(
        "TempReading", back_populates="batch", cascade="all, delete-orphan"
    )
    pour_events = relationship(
        "PourEvent", back_populates="batch", cascade="all, delete-orphan"
    )

    @property
    def active_dry_hops(self):
        """Non-soft-deleted dry hops, for embedding in batch API responses
        (oss/schemas/batch.py BatchResponse.dry_hops reads this, not the raw
        cascade-managed `dry_hops` relationship, so a soft-deleted hop doesn't
        leak back into the batch payload)."""
        return [h for h in self.dry_hops if h.deleted_at is None]


register_model("Batch", Batch)


@event.listens_for(Batch, "before_update")
def _increment_version(_, __, target):
    """Advance the optimistic-concurrency token for every ORM update."""
    target.version = (target.version or 0) + 1
