# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Integration model."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Index, Integer, String, Uuid, event
from sqlalchemy.orm import mapped_column

from core.models.types import JsonDocument
from core.models import Base
from core.models.types import UtcDateTime
from core.models.registry import register_model
from oss.extensions.tenant import DEFAULT_TENANT_ID


class Integration(Base):
    """Account-level configuration for forwarding collected measurements to an
    external service in the background.

    Replaces the former per-device `Device.ispindel_forward_url`/`brewfather_forward_url`
    columns — forwarding is a property of the account, not of any one device. No
    uniqueness beyond the primary key: an account may configure any number of
    targets, including several of the same `type` for the same `measurement`.

    `measurement` is which measurement this target forwards (`gravity`, `pressure`,
    `pour`, or `temp`) — immutable after creation. `type` is one of `ispindel_forward`,
    `brewfather_forward`, or `custom_forward`. `ispindel_forward` requires
    `measurement=gravity`; `brewfather_forward` takes `gravity`, `pressure` or `temp`; both
    carry a fixed, server-defined payload shape. `custom_forward` renders
    `config["template"]` against a `${key}` token set that depends on `measurement`. See
    `oss/jobs/gravity_forward.py` and its pressure/pour/temp siblings.
    """

    __tablename__ = "integration"
    __table_args__ = (
        Index("ix_integration_tenant_id", "tenant_id"),
        Index("ix_integration_tenant_measurement_enabled", "tenant_id", "measurement", "enabled"),
    )

    id = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=False, default=DEFAULT_TENANT_ID)
    # User-chosen label, e.g. "Brewfather" or "Thingspeak channel 2" -- for telling
    # multiple configured targets apart, not a key.
    name = mapped_column(String(60), nullable=False)
    # gravity | pressure | pour | temp -- immutable after creation, see class docstring.
    measurement = mapped_column(String(10), nullable=False)
    type = mapped_column(String(30), nullable=False)
    enabled = mapped_column(Boolean, nullable=False, default=True)
    # {"url": str, "method": "POST"|"GET", "headers": {str: str}, "template": str|None}.
    # `template` is required for custom_forward, ignored for the two built-in types.
    config = mapped_column(JsonDocument, nullable=False)
    consecutive_failures = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_success_at = mapped_column(UtcDateTime(), nullable=True, default=None)
    last_failure_at = mapped_column(UtcDateTime(), nullable=True, default=None)
    last_failure_code = mapped_column(String(50), nullable=True, default=None)
    disabled_reason = mapped_column(String(20), nullable=True, default=None)
    version = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at = mapped_column(
        UtcDateTime(),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


register_model("Integration", Integration)


@event.listens_for(Integration, "before_update")
def _increment_version(_, __, target):
    target.version = (target.version or 0) + 1
