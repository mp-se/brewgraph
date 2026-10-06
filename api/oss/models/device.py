# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Device model."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import (Boolean, Enum, ForeignKey, Index, Integer, String,
                        Uuid)
from sqlalchemy.orm import mapped_column, relationship

from core.enums import DeviceColor
from core.models.types import JsonDocument
from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


class Device(Base):
    """Physical sensor device, optionally linked to a batch and/or storage vessel.

    `token_prefix` is an indexed prefix of `token`, for looking a device up without
    scanning every row. `mdns`, `url`, `config`, `device_color` and `collect_logs` carry the
    device's local-network addressing and display settings.

    Constraints that are policy rather than shape live in the migration, not here: the
    UNIQUE on `token` and the per-`chip_id` uniqueness are declared in `000`.
    """

    __tablename__ = "device"
    __table_args__ = (
        Index("ix_device_tenant_id", "tenant_id"),
        Index("uq_device_token", "token", unique=True),
        Index("uq_device_type_chip", "device_type", "chip_id", unique=True),
    )

    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    # Nullable, and no empty-string default: Oracle stores '' as NULL, so a NOT NULL
    # column defended only by default="" inserts NULL and violates its own constraint.
    name = mapped_column(String(60), nullable=True, default=None)
    chip_id = mapped_column(String(32), nullable=True, default=None)
    # Plaintext token; ingest verifies it directly.
    token = mapped_column(String(64), nullable=True, default=None)
    token_prefix = mapped_column(String(8), nullable=True, default=None, index=True)
    mdns = mapped_column(String(80), nullable=True, default=None)
    description = mapped_column(String(200), nullable=True, default=None)
    device_type = mapped_column(
        String(20),
        nullable=True,
        default=None,
    )
    # Nullable for the same reason as name above.
    url = mapped_column(String(80), nullable=True, default=None)
    # Backup of the device's own configuration, fetched from the device over the LAN
    # and stored verbatim inside the standard envelope. The server never interprets it:
    # it is whatever the firmware returned, and a firmware that answers with plain text
    # is kept as {"raw": "..."} rather than rejected.
    config = mapped_column(JsonDocument, nullable=False, default=dict)
    device_color = mapped_column(
        Enum(DeviceColor, values_callable=lambda enum: [member.value for member in enum]),
        nullable=False,
        default=DeviceColor.WHITE,
    )
    collect_logs = mapped_column(Boolean, nullable=False, default=False)
    chip_family = mapped_column(String(10), nullable=True, default=None)
    board = mapped_column(String(10), nullable=True, default=None)
    gyro_model = mapped_column(String(20), nullable=True, default=None)
    device_filtered = mapped_column(Boolean, nullable=False, default=False)
    # HMAC-SHA256 of the origin IP, overwritten on every successful ingest write — a snapshot
    # of the latest origin, not a history.
    last_ingest_ip_hash = mapped_column(String(64), nullable=True, default=None, index=True)
    # use_alter breaks the batch/device/vessel/tap FK cycle at DDL time, which Oracle requires
    # and every other dialect tolerates.
    batch_id = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("batch.id", use_alter=True, name="fk_device_batch_id"),
        nullable=True,
        default=None,
    )
    # Validated string, not a DB enum — see prediction.prediction_type.
    batch_role = mapped_column(
        String(10),
        nullable=True,
        default=None,
    )
    vessel_id = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("storage_vessel.id", use_alter=True, name="fk_device_vessel_id"),
        nullable=True,
        default=None,
    )
    deleted_at = mapped_column(UtcDateTime(), nullable=True, default=None)
    # Set by the ingestion service when an optional device_token resolves to
    # this device (Kegmon pour or beer-poll) — never written by user-facing endpoints.
    last_seen = mapped_column(UtcDateTime(), nullable=True, default=None)
    # Count of consecutive readings dropped for this device since its last successfully
    # persisted reading (rate-limited, unparseable payload). Incremented by
    # IngestionService.log_ingestion_error when a resolved device's reading fails to
    # persist, reset to 0 on the device's next successfully persisted reading.
    failed_ingest_counter = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at = mapped_column(
        UtcDateTime(),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    batch = relationship("Batch", foreign_keys="Device.batch_id", back_populates="devices")
    vessel = relationship(
        "StorageVessel", foreign_keys="Device.vessel_id", back_populates="devices"
    )
    gravity_readings = relationship("GravityReading", back_populates="device")
    pressure_readings = relationship("PressureReading", back_populates="device")
    fermentation_steps = relationship("FermentationStep", back_populates="device")


register_model("Device", Device)
