# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""JSON and UTC datetime column types for SQLite and PostgreSQL."""
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import JSON, TIMESTAMP
from sqlalchemy.types import TypeDecorator


class JsonDocument(TypeDecorator):  # pylint: disable=abstract-method
    """Store structured documents in a database JSON column."""

    impl = JSON
    cache_ok = True


class UtcDateTime(TypeDecorator):  # pylint: disable=abstract-method,too-many-ancestors
    """Store instants in UTC and return timezone-aware UTC datetimes."""

    impl = TIMESTAMP(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        """Convert aware datetimes to UTC; pass naive values and None through."""
        if value is not None and value.tzinfo is not None:
            return value.astimezone(UTC)
        return value

    def process_result_value(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        """Attach UTC to naive values, convert aware ones to UTC."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
