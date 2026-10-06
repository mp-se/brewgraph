# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Prediction model.

tenant_id is a bare column with no FK, matching Batch/Device/StorageVessel/Tap/GravityReading —
this app is single-tenant and every row carries DEFAULT_TENANT_ID; there is no tenant table
to reference.
"""
from datetime import UTC, datetime

from sqlalchemy import (BigInteger, Float, ForeignKey, Identity, Index,
                        Integer, String, Uuid)
from sqlalchemy.orm import mapped_column, relationship

from core.enums import PredictionType
from core.models.types import JsonDocument
from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


class Prediction(Base):
    """ML-generated fermentation completion estimate for a batch."""

    __tablename__ = "prediction"
    __table_args__ = (
        Index("ix_prediction_batch_created", "batch_id", "created_at"),
        Index("ix_prediction_device_created", "device_id", "created_at"),
        Index("ix_prediction_vessel_created", "vessel_id", "created_at"),
        Index("ix_prediction_tap_created", "tap_id", "created_at"),
        Index("ix_prediction_tenant_batch_created", "tenant_id", "batch_id", "created_at"),
    )

    id = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), primary_key=True
    )
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    batch_id = mapped_column(Uuid(as_uuid=True), ForeignKey("batch.id"), nullable=True)
    device_id = mapped_column(Uuid(as_uuid=True), ForeignKey("device.id"), nullable=True)
    vessel_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("storage_vessel.id"), nullable=True
    )
    # A prediction carries every reference that gives it meaning, not one polymorphic
    # subject: a low-battery prediction is about a device *and* the batch it is on.
    # `tap_id` is for predictions that belong to the plumbing rather than the beer —
    # cleaning is due on a tap, and stays with it when the keg is swapped.
    tap_id = mapped_column(Uuid(as_uuid=True), ForeignKey("tap.id"), nullable=True)
    # Validated string, not a DB enum — same rule as `device_type` and `temp_type`.
    # A DB enum put a CHECK constraint in the ORM path
    # that the migration never created, so tests validated what production did not.
    # `PredictionType` is a str-subclass, so members bind as their value unchanged.
    prediction_type = mapped_column(
        String(30),
        nullable=False,
        default=PredictionType.FERMENTATION_PROGRESS,
    )
    outcome = mapped_column(String(30), nullable=False, default="fermenting")
    hours_left = mapped_column(Float, nullable=True, default=None)
    confidence = mapped_column(Float, nullable=True, default=None)
    # Type-specific output. `outcome` is the field every consumer can rely on; anything
    # a single PredictionType needs goes in here rather than becoming a column no other
    # type populates. Stored via `JsonDocument`, so it renders correctly on every
    # supported database dialect (see core/models/types.py for why that type exists).
    details = mapped_column(JsonDocument, nullable=False, default=dict)
    deleted_at = mapped_column(UtcDateTime(), nullable=True, default=None)
    created_at = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC)
    )

    batch = relationship("Batch", back_populates="predictions")


register_model("Prediction", Prediction)
