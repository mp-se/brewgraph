# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Column types that have to render differently per dialect.

`JsonDocument` exists because SQLAlchemy's Oracle dialect cannot render a bare
`JSON` type at all — `CREATE TABLE` fails with a CompileError before any database
is touched. PostgreSQL gets native JSON, SQLite gets its JSON1 text storage, and
Oracle gets a CLOB — the dialect's stand-in for a JSON document column, paired
with an `IS JSON` check constraint declared alongside it in the migration.

The `IS JSON` check constraint that makes the CLOB honest belongs to the DDL, so
each product's migration declares it; this type only decides storage and
serialisation.

`UtcDateTime` exists because SQLite and the Oracle driver hand back naive datetimes
for `TIMESTAMP(timezone=True)` columns, which pydantic then serialises with no zone
marker -- browsers parse that as local time. Every instant is stored as UTC, so the
type re-attaches UTC on read and the API emits an explicit offset.
"""
import json
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import CLOB, JSON, TIMESTAMP
from sqlalchemy.types import TypeDecorator


class JsonDocument(TypeDecorator):  # pylint: disable=abstract-method
    """A JSON document, stored natively where the dialect has a JSON type.

    On Oracle the value round-trips through a CLOB as text, because the driver
    hands back a string rather than a parsed document.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        """CLOB on Oracle, the dialect's own JSON type everywhere else."""
        if dialect.name == "oracle":
            return dialect.type_descriptor(CLOB())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect) -> Optional[Any]:
        """Serialise to text for Oracle; leave every other dialect to its JSON type."""
        if dialect.name == "oracle" and value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value: Any, dialect) -> Optional[Any]:
        """Parse Oracle's CLOB text back into a document.

        `value` isn't always the raw CLOB string the docstring above assumes: this method
        runs after `impl`'s own (JSON) result processing, and on some SQLAlchemy/oracledb
        version combinations that already returns a parsed dict/list rather than text --
        `json.loads()` on an already-parsed value raises `TypeError: the JSON object must be
        str, bytes or bytearray, not dict`. Only parse when it's actually still a string.
        """
        if dialect.name == "oracle" and isinstance(value, (str, bytes)):
            return json.loads(value)
        return value


class UtcDateTime(TypeDecorator):  # pylint: disable=abstract-method,too-many-ancestors
    """An instant stored as UTC, always read back as a timezone-aware UTC datetime.

    DDL is identical to `TIMESTAMP(timezone=True)`, so no migration changes. Aware
    values are converted to UTC on the way in; naive values are taken to be UTC
    already and left untouched. On the way out, a naive value (SQLite, Oracle) gets
    UTC attached and an aware value is converted to UTC.
    """

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
