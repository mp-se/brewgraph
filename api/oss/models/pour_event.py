# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""PourEvent model.

tenant_id is a bare column with no FK, matching Batch/Device/StorageVessel/Tap/GravityReading —
this app is single-tenant and every row carries DEFAULT_TENANT_ID; there is no tenant table
to reference.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Float, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import mapped_column, relationship

from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


class PourEvent(Base):
    """A single pour recorded against a storage vessel."""

    __tablename__ = "pour_event"
    __table_args__ = (
        Index("ix_pour_event_tenant_id", "tenant_id"),
        Index("ix_pour_event_batch_created", "batch_id", "created_at"),
        UniqueConstraint("tap_id", "event_id", name="uq_pour_event_tap_event_id"),
    )

    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    vessel_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("storage_vessel.id"), nullable=False
    )
    # Stamped from the vessel at pour time, so a keg's history stays separable across
    # refills: the pour belongs to the beer, the vessel is just what held it. Nullable
    # because a pour can be recorded against a vessel with nothing assigned to it.
    batch_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("batch.id"), nullable=True, default=None
    )
    # Stamped from the vessel's current tap at pour time. Survives the vessel's own
    # tap_id being cleared (e.g. on drain-to-empty), so tap-scoped pour history
    # stays attributable across keg swaps. This is the detail view; Tap.total_
    # volume_poured is the authoritative lifetime total -- see its docstring.
    tap_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tap.id"), nullable=True, default=None
    )
    # Device-supplied receipt key. Nullable keeps legacy firmware compatible.
    event_id = mapped_column(String(128), nullable=True, default=None)
    pour_amount = mapped_column(Float, nullable=False)
    volume_remaining = mapped_column(Float, nullable=False)
    is_manual = mapped_column(Boolean, nullable=False, default=False)
    excluded = mapped_column(Boolean, nullable=False, default=False)
    deleted_at = mapped_column(UtcDateTime(), nullable=True, default=None)
    created_at = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC)
    )

    vessel = relationship("StorageVessel", back_populates="pour_events")
    batch = relationship("Batch", back_populates="pour_events")


register_model("PourEvent", PourEvent)
