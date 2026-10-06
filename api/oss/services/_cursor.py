# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Shared compound `(created_at, id)` cursor-pagination filter/order helper.

`created_at > cursor` alone drops rows that share the boundary row's exact
timestamp: when more rows than fit on one page carry that timestamp, the ones
after the page boundary are excluded by the strict `>` just as surely as the
ones already returned. That is routine here, not a rare edge case — chamber
polls intentionally write one shared timestamp across several rows, and every
bulk-insert endpoint assigns one `now` to any row missing its own
`created_at`.

The fix is a compound cursor: `(created_at, id)` instead of `created_at`
alone, compared lexicographically. `id` is unique and stable, so the compound
key can never repeat and the boundary can never hide a row. This module is
the one place that filter and its matching `ORDER BY` are written, for every
service (gravity, pressure, temp, pours, notes, predictions, logs) that does
cursor pagination — see `oss/schemas/_page.py` for the matching
encode/decode of the cursor string itself.
"""
import uuid
from datetime import datetime
from typing import Any, Optional, Tuple

from sqlalchemy import and_, or_

Cursor = Tuple[datetime, str]


def _coerce_id(model: Any, id_str: str) -> Any:
    """Convert a cursor's string id component to the model's own id type."""
    py_type = model.id.type.python_type
    if py_type is int:
        return int(id_str)
    if py_type is uuid.UUID:
        return uuid.UUID(id_str)
    return id_str


def apply_cursor_filter(query, model: Any, cursor: Optional[Cursor], ascending: bool = True):
    """Add the `(created_at, id)` boundary filter to `query`, if a cursor is given.

    Ascending pages (readings, notes) want rows *after* the boundary; descending
    pages (logs, prediction history) want rows *before* it.
    """
    if cursor is None:
        return query
    created_at, id_str = cursor
    row_id = _coerce_id(model, id_str)
    if ascending:
        return query.where(
            or_(
                model.created_at > created_at,
                and_(model.created_at == created_at, model.id > row_id),
            )
        )
    return query.where(
        or_(
            model.created_at < created_at,
            and_(model.created_at == created_at, model.id < row_id),
        )
    )


def cursor_order_by(model: Any, ascending: bool = True) -> Tuple[Any, Any]:
    """Return the `(created_at, id)` ORDER BY columns matching `apply_cursor_filter`."""
    if ascending:
        return (model.created_at.asc(), model.id.asc())
    return (model.created_at.desc(), model.id.desc())
