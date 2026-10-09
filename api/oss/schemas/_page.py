# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Shared pagination envelope schemas."""
import math
import uuid
from datetime import datetime
from typing import Generic, List, Optional, Tuple, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator

from core.schemas.camel import to_camel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Offset-paginated envelope for entity lists.

    Serializes ``pageSize`` (not ``page_size``) like every other response schema —
    the envelope was the one place the camelCase wire contract wasn't applied.
    ``populate_by_name`` keeps every ``Page(page_size=...)`` construction working.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    @model_validator(mode="before")
    @classmethod
    def compute_pages(cls, values):
        """Compute total page count from total and page_size before validation."""
        total = values.get("total", 0)
        page_size = values.get("page_size", 1)
        if "pages" not in values or values["pages"] is None:
            values["pages"] = max(1, math.ceil(total / page_size)) if page_size else 1
        return values


class CursorPage(BaseModel, Generic[T]):
    """Cursor-paginated envelope for time-series readings.

    Serializes ``nextCursor``/``hasMore`` — same reason as ``Page`` above.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: List[T]
    next_cursor: Optional[str] = None
    has_more: bool


def encode_cursor(created_at: datetime, row_id) -> str:
    """Encode a compound `(created_at, id)` cursor for `CursorPage.next_cursor`.

    The id half is what makes the cursor exact even when several rows share one
    `created_at` — see `oss.services._cursor` for why that isn't rare.
    """
    return f"{created_at.isoformat()}|{row_id}"


def _validate_cursor_id(id_part: str) -> None:
    """Reject a cursor id that is neither a bounded integer nor a UUID.

    Every cursor-paginated model keys on one or the other; checking here keeps a
    malformed id a ValueError (mapped to 400) instead of failing later in the query.
    """
    if id_part.isascii() and id_part.isdigit():
        if int(id_part) > 2 ** 63 - 1:
            raise ValueError("Cursor id out of range")
        return
    uuid.UUID(id_part)


def parse_cursor(cursor: Optional[str]) -> Optional[Tuple[datetime, str]]:
    """Parse a cursor emitted by `encode_cursor` back into `(created_at, id_str)`.

    Tolerates the `+` → space substitution that happens when a client puts the
    cursor straight into a query string without percent-encoding it: against a
    timezone-aware database the timestamp half ends `+00:00`, and `+` decodes to
    a space, so what arrives here is `...T10:00:00 00:00|<id>`. Rejecting that
    would break the obvious client implementation on every page after the
    first, while the same code works fine against a database that stores naive
    datetimes.

    Raises `ValueError` for anything genuinely unparseable, including a cursor
    missing its `|<id>` half — callers map that to 400.
    """
    if not cursor:
        return None
    text = cursor.strip()
    if "|" not in text:
        raise ValueError("Cursor missing id component")
    ts_part, id_part = text.rsplit("|", 1)
    if not id_part:
        raise ValueError("Cursor missing id component")
    _validate_cursor_id(id_part)
    tail = ts_part[-6:]
    if tail.startswith(" ") and tail[1:].replace(":", "").isdigit():
        ts_part = ts_part[:-6] + "+" + tail[1:]
    return datetime.fromisoformat(ts_part), id_part
