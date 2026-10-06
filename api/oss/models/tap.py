# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Tap model."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Uuid, event
from sqlalchemy.orm import mapped_column, relationship

from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


class Tap(Base):
    """Kegerator tap point, optionally linked to a storage vessel.

    Constraints that are policy rather than shape live in the migration, not here:
    `tenant_id`'s indexing is declared in `000`.

    `token` is the plaintext the brewer reads once to configure the physical pour sensor;
    `token_hash` is what ingest actually resolves against on every pour, which is why it is
    the indexed column. A token is always generated at create time, so the column is NOT NULL.
    """

    __tablename__ = "tap"
    __table_args__ = (
        Index("ix_tap_tenant_id", "tenant_id"),
        Index("ix_tap_token", "token", unique=True),
        Index("ix_tap_token_hash", "token_hash"),
    )

    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    name = mapped_column(String(60), nullable=False)
    tap_number = mapped_column(Integer, nullable=True, default=None)
    glass_size = mapped_column(Float, nullable=True, default=None)
    location = mapped_column(String(100), nullable=True, default=None)
    notes = mapped_column(String(200), nullable=True, default=None)
    token = mapped_column(String(64), nullable=False, default=lambda: uuid.uuid4().hex)
    token_hash = mapped_column(String(64), nullable=True, default=None)
    # Unused: no writer sets this column. Pour sensors authenticate with a single
    # tap token and never carry a separate device identity to derive this from, so
    # the derivation this comment used to describe cannot happen. Do not build new
    # behavior on this column.
    # use_alter breaks the tap/device/vessel FK cycle at DDL time, which Oracle requires
    # and every other dialect tolerates. Matches Device's batch_id/vessel_id.
    device_id = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("device.id", use_alter=True, name="fk_tap_device_id"),
        nullable=True,
        default=None,
    )
    # Set by the ingestion service when a pour resolves this tap's token — never
    # written by user-facing endpoints. This is the liveness signal for pour
    # hardware, which has no Device row to carry Device.last_seen instead.
    last_seen = mapped_column(UtcDateTime(), nullable=True, default=None)
    last_cleaned_at = mapped_column(UtcDateTime(), nullable=True, default=None)
    # Lifetime, monotonic running total of volume poured through this tap.
    # Incremented at pour time in PourEventService (record_pour/record_bottle_pour),
    # adjusted by PourEventService.toggle_excluded when a pour's excluded flag
    # changes. Not derived from PourEvent rows, so it survives their retention
    # purge -- a SUM(pour_amount) over PourEvent can't stand in for it, since a
    # tap's history can outlive the readings' own retention window.
    total_volume_poured = mapped_column(Float, nullable=False, default=0.0)
    # Snapshot of total_volume_poured taken whenever last_cleaned_at is set --
    # not a separate trigger point, see TapService.update(). Volume poured since
    # the last clean is total_volume_poured - volume_at_last_clean.
    volume_at_last_clean = mapped_column(Float, nullable=False, default=0.0)
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

    storage_vessels = relationship("StorageVessel", back_populates="tap")


register_model("Tap", Tap)


@event.listens_for(Tap, "before_update")
def _increment_version(_, __, target):
    target.version = (target.version or 0) + 1
