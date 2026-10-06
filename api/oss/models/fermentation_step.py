# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""FermentationStep model."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import mapped_column, relationship

from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


# Allowed values for FermentationStep.trigger_type. "day_offset" is the legacy/
# default behavior (step ends when its days window elapses). The other values
# describe what event should end the step early via triggered_at; detecting and setting
# triggered_at itself is out of scope here (nothing sets it automatically today).
TRIGGER_TYPES = ("day_offset", "krausen_peak", "terminal_gravity", "manual")


class FermentationStep(Base):
    """Planned fermentation temperature/time step within a batch."""

    __tablename__ = "fermentation_step"
    __table_args__ = (
        Index("ix_fermentation_step_batch_order", "batch_id", "order"),
        Index("ix_fermentation_step_tenant_id", "tenant_id"),
        Index("ix_fermentation_step_tenant_batch_order", "tenant_id", "batch_id", "order"),
    )

    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Bare column with no FK: this app is single-tenant and there is no tenant table
    # to reference. Every row carries DEFAULT_TENANT_ID.
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    batch_id = mapped_column(Uuid(as_uuid=True), ForeignKey("batch.id"), nullable=False)
    device_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device.id"), nullable=True, default=None
    )
    order = mapped_column(Integer, nullable=False, default=0)
    # Nullable, and no empty-string default: Oracle stores '' as NULL, so a NOT NULL
    # column defended only by default="" inserts NULL and violates its own constraint.
    type = mapped_column(String(30), nullable=True, default=None)
    name = mapped_column(String(30), nullable=True, default=None)
    temp = mapped_column(Float, nullable=False, default=0.0)
    days = mapped_column(Integer, nullable=False, default=0)
    date = mapped_column(Date, nullable=True, default=None)
    control = mapped_column(String(10), nullable=True, default=None)
    trigger_type = mapped_column(String(20), nullable=False, default="day_offset")
    triggered_at = mapped_column(UtcDateTime(), nullable=True, default=None)
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

    batch = relationship("Batch", back_populates="fermentation_steps")
    device = relationship("Device", back_populates="fermentation_steps")


register_model("FermentationStep", FermentationStep)
