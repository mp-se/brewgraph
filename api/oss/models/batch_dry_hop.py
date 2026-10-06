# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""BatchDryHop model — dry hop schedule and execution tracker."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import mapped_column, relationship

from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


class BatchDryHop(Base):
    """Dry hop schedule entry for a batch."""

    __tablename__ = "batch_dry_hop"
    __table_args__ = (
        Index("ix_batch_dry_hop_batch_created", "batch_id", "created_at"),
        Index("ix_batch_dry_hop_tenant_id", "tenant_id"),
        Index("ix_batch_dry_hop_tenant_batch_created", "tenant_id", "batch_id", "created_at"),
    )

    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Bare column with no FK: this app is single-tenant and there is no tenant table
    # to reference. Every row carries DEFAULT_TENANT_ID.
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    batch_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("batch.id"), nullable=False
    )
    # Nullable, and no empty-string default: Oracle stores '' as NULL (see Device.name).
    name = mapped_column(String(60), nullable=True, default=None)
    amount = mapped_column(Float, nullable=False)
    trigger_method = mapped_column(String(30), nullable=False, default="hours_before_completion")
    trigger_gravity = mapped_column(Float, nullable=True, default=None)
    # No ORM-level default: a Core column default fires whenever the bound value is None,
    # and cannot tell "never set" from "explicitly set to null". The schema supplies 24 for
    # ordinary creates and deliberately nulls this field for trigger methods that do not use
    # it — an ORM default would silently overwrite that back to 24.
    trigger_hours_before = mapped_column(Integer, nullable=True)
    triggered_at = mapped_column(UtcDateTime(), nullable=True, default=None)
    completed_at = mapped_column(UtcDateTime(), nullable=True, default=None)
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

    batch = relationship("Batch", back_populates="dry_hops")


register_model("BatchDryHop", BatchDryHop)
