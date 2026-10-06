# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Bounded time windows for chart queries."""
from datetime import UTC, datetime, timedelta
from typing import TypeVar

from starlette.exceptions import HTTPException

# A fermentation dashboard normally covers days or weeks. Older history remains
# available by requesting adjacent windows, rather than loading an entire
# high-frequency retention period into one request.
MAX_CHART_WINDOW = timedelta(days=31)
MAX_CHART_SOURCE_ROWS = 50_000

T = TypeVar("T")


def bounded_chart_window(
    from_dt: datetime | None, to_dt: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    """Return a valid explicit chart window without changing legacy full-history reads."""
    if from_dt is None and to_dt is None:
        return None, None
    end = to_dt or datetime.now(UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    start = from_dt or end - MAX_CHART_WINDOW
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if start > end:
        raise HTTPException(status_code=422, detail="Chart 'from' must not be after 'to'")
    if end - start > MAX_CHART_WINDOW:
        raise HTTPException(
            status_code=422,
            detail="Chart range must not exceed 31 days; request adjacent windows",
        )
    return start, end


def bounded_chart_rows(session, query) -> list[T]:
    """Materialise a chart's source rows under a hard resource ceiling."""
    rows = list(session.scalars(query.limit(MAX_CHART_SOURCE_ROWS + 1)).all())
    if len(rows) > MAX_CHART_SOURCE_ROWS:
        raise HTTPException(
            status_code=422,
            detail="Chart has too many readings; request a smaller time window",
        )
    return rows
