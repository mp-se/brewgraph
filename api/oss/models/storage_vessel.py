# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""StorageVessel model."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import (Boolean, CheckConstraint, Date, Float, ForeignKey, Index, event,
                        Integer, String, Uuid)
from sqlalchemy.orm import mapped_column, relationship

from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


class StorageVessel(Base):
    """Keg or bottle vessel that holds finished beer.

    `token` / `token_hash` are absent: a pour sensor is mounted on the tap, not the keg, so
    no path ever resolves a vessel by token.

    Constraints that are policy rather than shape live in the migration, not here:
    `tenant_id`'s indexing is declared in `000`.
    """

    __tablename__ = "storage_vessel"
    __table_args__ = (
        Index("ix_storage_vessel_tenant_id", "tenant_id"),
        CheckConstraint("total_volume >= 0", name="ck_storage_vessel_total_volume_non_negative"),
        CheckConstraint(
            "volume_remaining >= 0", name="ck_storage_vessel_volume_remaining_non_negative"
        ),
        CheckConstraint(
            "volume_remaining <= total_volume", name="ck_storage_vessel_volume_remaining_le_total"
        ),
        CheckConstraint(
            "bottle_count IS NULL OR bottle_count >= 0",
            name="ck_storage_vessel_bottle_count_non_negative",
        ),
        CheckConstraint(
            "bottles_remaining IS NULL OR bottles_remaining >= 0",
            name="ck_storage_vessel_bottles_remaining_non_negative",
        ),
        CheckConstraint(
            "bottle_count IS NULL OR bottles_remaining IS NULL "
            "OR bottles_remaining <= bottle_count",
            name="ck_storage_vessel_bottles_remaining_le_count",
        ),
    )

    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    # Nullable: releasing a keg clears the batch and sets status CLEAN — the only path that
    # reaches VesselStatus.CLEAN, and the reason an empty clean keg can exist as a row.
    batch_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("batch.id"), nullable=True, default=None
    )
    tap_id = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tap.id"), nullable=True, unique=True, default=None
    )
    vessel_number = mapped_column(Integer, nullable=True, default=None)
    vessel_type = mapped_column(String(10), nullable=False)
    name = mapped_column(String(60), nullable=False)
    fill_date = mapped_column(Date, nullable=False)
    total_volume = mapped_column(Float, nullable=False)
    volume_remaining = mapped_column(Float, nullable=False)
    bottle_volume = mapped_column(Float, nullable=True, default=None)
    bottle_count = mapped_column(Integer, nullable=True, default=None)
    bottles_remaining = mapped_column(Integer, nullable=True, default=None)
    status = mapped_column(String(15), nullable=False, default="filled")
    location = mapped_column(String(100), nullable=True, default=None)
    notes = mapped_column(String(200), nullable=True, default=None)
    serving_temp_alert_enabled = mapped_column(Boolean, nullable=False, default=False)
    serving_temp_min = mapped_column(Float, nullable=True, default=None)
    serving_temp_max = mapped_column(Float, nullable=True, default=None)
    conditioning_days = mapped_column(Integer, nullable=True, default=None)
    priming_sugar_type = mapped_column(String(20), nullable=True, default=None)
    priming_sugar_amount = mapped_column(Float, nullable=True, default=None)
    conditioning_temp = mapped_column(Float, nullable=True, default=None)
    # "Volumes" here means volumes of CO2 per volume of beer — a dimensionless
    # ratio, not a volume. It carries no unit suffix to strip and gets no unit
    # conversion on the way in or out; canonical-units drops suffixes that name
    # a unit, and this field doesn't have one.
    carbonation_volumes_target = mapped_column(Float, nullable=True, default=None)
    keg_identifier = mapped_column(String(60), nullable=True, default=None)
    fill_count = mapped_column(Integer, nullable=False, default=1)
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

    batch = relationship("Batch", back_populates="storage_vessels")
    tap = relationship("Tap", back_populates="storage_vessels")
    devices = relationship("Device", foreign_keys="Device.vessel_id", back_populates="vessel")
    pour_events = relationship("PourEvent", back_populates="vessel", cascade="all, delete-orphan")
    pressure_readings = relationship(
        "PressureReading", back_populates="vessel", cascade="all, delete-orphan"
    )


register_model("StorageVessel", StorageVessel)


@event.listens_for(StorageVessel, "before_update")
def _increment_version(_, __, target):
    target.version = (target.version or 0) + 1
