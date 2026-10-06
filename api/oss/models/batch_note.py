# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""BatchNote model.

tenant_id is a bare column with no FK, matching Batch/Device/StorageVessel/Tap/GravityReading —
this app is single-tenant and every row carries DEFAULT_TENANT_ID; there is no tenant table
to reference.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import mapped_column, relationship

from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


class BatchNote(Base):
    """Timestamped free-text note attached to a batch."""

    __tablename__ = "batch_note"
    __table_args__ = (
        Index("ix_batch_note_batch_created", "batch_id", "created_at"),
        Index("ix_batch_note_tenant_id", "tenant_id"),
        Index("ix_batch_note_tenant_batch_created", "tenant_id", "batch_id", "created_at"),
    )

    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    batch_id = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("batch.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = mapped_column(Text, nullable=False)
    created_by = mapped_column(String(100), nullable=True, default=None)
    note_type = mapped_column(String(20), nullable=True, default=None)
    test_result = mapped_column(String(20), nullable=True, default=None)
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

    batch = relationship("Batch", back_populates="batch_notes")


register_model("BatchNote", BatchNote)
