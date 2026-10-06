# Copyright (c) 2024-2026 Magnus Persson. All rights reserved.
# Commercial License is required for commercial use of this software.
"""Chart downsampling — bounds what a chart endpoint puts on the wire.

Chart endpoints returned every matching row. A three-week fermentation logging
every 15 minutes is ~2,000 points; a two-year retention window is far more, and
all of it was serialised to draw a line a few hundred pixels wide. The
`resolution` parameter existed on all four chart services and was discarded
(`_ = resolution`) in every one of them.

Two reductions, applied in this order:

1. **`resolution`** — `raw` keeps every point; `hourly`/`daily` keep the first
   point in each bucket. This is the caller asking for a coarser series.
2. **LTTB** — Largest-Triangle-Three-Buckets. Applied when the series still
   exceeds `LTTB_THRESHOLD`, reducing to `MAX_POINTS`. This is the endpoint
   refusing to emit an unbounded response regardless of what was asked for.

**Why this is not the `DISTINCT ON (date_trunc(...))` the spec used to
prescribe.** `DISTINCT ON` is PostgreSQL-only, and this application is expected
to run on Oracle and SQLite as well as Postgres. Postgres-shaped SQL reaching an
Oracle deployment has repeatedly been a source of bugs here. `date_trunc`
itself is equally dialect-specific — Oracle spells it `TRUNC(ts, 'HH')`, SQLite
needs `strftime`. Pushing the bucketing down would mean a dialect dispatch in
the service layer, where none currently exists.

It also would not have helped as much as it appears: LTTB has to see every
candidate point to choose between them, so the rows are loaded either way. The
payload — which is the actual defect — is bounded here just as effectively.

DB-side pushdown for the `hourly`/`daily` paths remains a worthwhile
optimisation if these series ever get large enough to make the fetch itself the
cost. It needs a portable truncation helper first; `ROW_NUMBER() OVER (PARTITION
BY ...)` works on all three backends where `DISTINCT ON` does not.

**LTTB picks real points — it never synthesises one.** Every returned item is an
object the caller passed in, so per-point fields the chart schema carries
(velocity, temperature, temp_type) survive untouched. That is why this operates
on opaque objects plus accessor functions rather than on (x, y) tuples.
"""
from datetime import datetime
from typing import Callable, List, Optional, Sequence, TypeVar

T = TypeVar("T")

#: Series longer than this are reduced by LTTB.
LTTB_THRESHOLD = 800

#: Ceiling on points returned by any chart endpoint.
MAX_POINTS = 500

_BUCKETS = {
    "hourly": lambda t: t.replace(minute=0, second=0, microsecond=0),
    "daily": lambda t: t.replace(hour=0, minute=0, second=0, microsecond=0),
}


def _bucket(rows: Sequence[T], x: Callable[[T], datetime], resolution: str) -> List[T]:
    """Keep the first row in each hour/day bucket, preserving input order."""
    key = _BUCKETS.get(resolution)
    if key is None:
        return list(rows)
    out: List[T] = []
    seen = set()
    for row in rows:
        bucket = key(x(row))
        if bucket not in seen:
            seen.add(bucket)
            out.append(row)
    return out


def _lttb(  # pylint: disable=too-many-locals
    rows: Sequence[T], x, y, target: int
) -> List[T]:
    """Largest-Triangle-Three-Buckets downsampling to `target` points.

    The local count is the algorithm: three triangle vertices, two bucket
    boundaries and a running previous-point index. Splitting it into helpers
    would hide the geometry rather than clarify it.

    Preserves visual shape — peaks, plateaus and the final gravity drop survive,
    where naive every-Nth sampling drops them. First and last points are always
    kept so the series keeps its true extent.
    """
    n = len(rows)
    if target >= n or target < 3:
        return list(rows)

    def xy(row):
        return x(row).timestamp(), y(row)

    out = [rows[0]]
    # Buckets span the interior only; first and last are fixed.
    step = (n - 2) / (target - 2)
    prev = 0

    for i in range(target - 2):
        lo = int((i + 1) * step) + 1
        hi = min(int((i + 2) * step) + 1, n - 1)
        nxt_lo = hi
        nxt_hi = min(int((i + 3) * step) + 1, n)

        # Average of the next bucket forms the third triangle vertex.
        if nxt_hi > nxt_lo:
            axs, ays = zip(*(xy(r) for r in rows[nxt_lo:nxt_hi]))
            ax, ay = sum(axs) / len(axs), sum(ays) / len(ays)
        else:
            ax, ay = xy(rows[-1])

        px, py = xy(rows[prev])
        best, best_area = lo, -1.0
        for j in range(lo, hi):
            cx, cy = xy(rows[j])
            area = abs((px - ax) * (cy - py) - (px - cx) * (ay - py))
            if area > best_area:
                best_area, best = area, j
        out.append(rows[best])
        prev = best

    out.append(rows[-1])
    return out


def downsample(  # pylint: disable=too-many-arguments
    rows: Sequence[T],
    x: Callable[[T], datetime],
    y: Callable[[T], Optional[float]],
    resolution: str = "raw",
    *,
    max_points: int = MAX_POINTS,
    threshold: int = LTTB_THRESHOLD,
) -> List[T]:
    """Reduce a time-ordered series for charting.

    `rows` must already be sorted ascending by `x`. Rows whose `y` is None are
    dropped before LTTB — the triangle-area calculation has no meaning for them —
    but they survive `raw` output untouched, since a gap is real chart data.
    """
    reduced = _bucket(rows, x, resolution)
    if len(reduced) <= threshold:
        return reduced
    measurable = [r for r in reduced if y(r) is not None]
    if len(measurable) <= max_points:
        return measurable
    return _lttb(measurable, x, y, max_points)
