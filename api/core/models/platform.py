# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Infrastructure-only ORM models.
"""
from datetime import UTC, datetime

from sqlalchemy import Identity, Integer, String, Text, Uuid
from sqlalchemy.orm import mapped_column

from core.models import Base
from core.models.types import UtcDateTime


class SystemLog(Base):
    """Operator-facing infrastructure event log."""

    __tablename__ = "system_log"

    id = mapped_column(Integer, Identity(), primary_key=True)
    level = mapped_column(String(10), nullable=False, default="INFO")
    event = mapped_column(String(80), nullable=True, default=None)
    message = mapped_column(String(500), nullable=True, default=None)
    created_at = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC)
    )


class IngestionLog(Base):
    """Error-only log for failed device POST requests.

    tenant_id/device_id are bare nullable columns with no FK. This app is single-tenant and
    never populates them with a non-default value; they must stay mapped here rather than
    unmapped, because a model with no mapped tenant_id is invisible to tenant-scoped session
    filters — an unmapped column is how a table can silently leak rows across a filter that
    keys off mapped attributes.

    Nullable is deliberate and specified: an unrecognised token resolves to no tenant. A NULL
    tenant matches no tenant and must never be treated as a wildcard.
    """

    __tablename__ = "ingestion_log"

    # Opts this model out of the fail-secure insert guard, which otherwise refuses to
    # write any tenant-scoped row without a tenant context. Unknown-token rows have no
    # resolvable tenant by definition and must still be recorded.
    __tenant_nullable__ = True

    # Identity(), not autoincrement=True: Oracle does not honour the latter and the
    # INSERT fails with ORA-01400 on the PK. Matches SystemLog above.
    id = mapped_column(Integer, Identity(), primary_key=True)
    tenant_id = mapped_column(Uuid(as_uuid=True), nullable=True, default=None)
    device_id = mapped_column(Uuid(as_uuid=True), nullable=True, default=None)
    # Validated string, not a DB enum. This one matters most of the set: `IngestionSource`
    # grows with every device type, and those register through a registry precisely so a
    # new device needs no migration. A native PG enum would put an ALTER TYPE back
    # in that path.
    source_type = mapped_column(String(20), nullable=False)
    device_type = mapped_column(String(12), nullable=True, default=None)
    ip_address = mapped_column(String(45), nullable=True, default=None)
    reason = mapped_column(String(30), nullable=True, default=None)
    error_detail = mapped_column(String(200), nullable=True, default=None)
    payload = mapped_column(Text, nullable=True, default=None)
    created_at = mapped_column(
        UtcDateTime(), nullable=False, default=lambda: datetime.now(UTC)
    )
