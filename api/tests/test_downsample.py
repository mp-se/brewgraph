# Copyright (c) 2024-2026 Magnus Persson. All rights reserved.
# Commercial License is required for commercial use of this software.
"""Chart downsampling.

The `resolution` parameter was accepted and discarded (`_ = resolution`) by all
four chart services, and no cap was applied, so a chart endpoint serialised every
matching row. These cover the reduction itself; the service wiring is covered by
the chart endpoint tests.
"""
from datetime import UTC, datetime, timedelta

from oss.services._downsample import LTTB_THRESHOLD, MAX_POINTS, downsample

BASE = datetime(2026, 1, 1, tzinfo=UTC)


class _P:  # pylint: disable=too-few-public-methods
    """Stand-in for a reading row."""

    def __init__(self, minutes: float, value: float | None):
        self.created_at = BASE + timedelta(minutes=minutes)
        self.value = value


def _series(n: int, fn=float) -> list[_P]:
    return [_P(i, fn(i)) for i in range(n)]


def _run(rows, resolution="raw", **kw):
    return downsample(rows, x=lambda r: r.created_at, y=lambda r: r.value,
                      resolution=resolution, **kw)


class TestPassThrough:
    """Short series must survive untouched — reduction is not free."""

    def test_series_under_threshold_is_returned_whole(self):
        """Below the LTTB threshold the input list is handed back unchanged."""
        rows = _series(100)
        assert _run(rows) == rows

    def test_series_exactly_at_threshold_is_not_reduced(self):
        """The threshold is the first size that reduces, not the last that survives."""
        rows = _series(LTTB_THRESHOLD)
        assert len(_run(rows)) == LTTB_THRESHOLD

    def test_empty_series(self):
        """No rows in, no rows out — and no division by zero on the way."""
        assert _run([]) == []


class TestCap:
    """Past the threshold, the response is bounded."""

    def test_long_series_is_capped(self):
        """MAX_POINTS is a hard ceiling, whatever the input size."""
        assert len(_run(_series(10_000))) == MAX_POINTS

    def test_endpoints_are_preserved(self):
        """First and last points fix the series' true extent."""
        rows = _series(5_000)
        out = _run(rows)
        assert out[0] is rows[0]
        assert out[-1] is rows[-1]

    def test_output_stays_time_ordered(self):
        """Bucket selection must not reorder points; a chart plots them as given."""
        out = _run(_series(5_000))
        assert out == sorted(out, key=lambda r: r.created_at)

    def test_returns_original_objects_never_synthesised_ones(self):
        """LTTB selects real points, so per-point fields survive."""
        rows = _series(5_000)
        identities = {id(r) for r in rows}
        assert all(id(r) in identities for r in _run(rows))


class TestShapePreservation:
    """The reason for LTTB over every-Nth sampling."""

    def test_a_narrow_spike_survives(self):
        """Every-Nth sampling drops a one-sample spike; LTTB keeps it."""
        rows = _series(5_000, fn=lambda i: 1.050)
        rows[2_500].value = 1.200  # lone outlier
        out = _run(rows)
        assert any(r.value == 1.200 for r in out), "LTTB dropped the spike"

    def test_monotonic_decline_keeps_its_endpoints(self):
        """A gravity curve's start and finish are the two points that matter."""
        rows = _series(3_000, fn=lambda i: 1.060 - i * 0.00001)
        out = _run(rows)
        assert out[0].value == 1.060
        assert out[-1].value == rows[-1].value


class TestResolution:
    """`raw` / `hourly` / `daily` — the parameter that was being discarded."""

    def test_hourly_keeps_one_point_per_hour(self):
        """Ten hours of minute data reduce to ten points, one on each hour mark."""
        rows = _series(600)  # 10 hours at 1-minute spacing
        out = _run(rows, resolution="hourly")
        assert len(out) == 10
        assert all(r.created_at.minute == 0 for r in out)

    def test_daily_keeps_one_point_per_day(self):
        """Three days of hourly data reduce to three points."""
        rows = [_P(i * 60, float(i)) for i in range(72)]  # 72 hours
        out = _run(rows, resolution="daily")
        assert len(out) == 3

    def test_raw_is_the_default_and_keeps_everything(self):
        """Omitting `resolution` must not silently bucket anything."""
        rows = _series(600)
        assert len(_run(rows)) == 600

    def test_unknown_resolution_falls_back_to_raw(self):
        """An unrecognised value must not silently empty the chart."""
        rows = _series(100)
        assert _run(rows, resolution="fortnightly") == rows

    def test_bucketing_can_avoid_the_lttb_cap_entirely(self):
        """Hourly buckets over a long window land under the threshold."""
        rows = _series(20_000)  # ~333 hours at 1-minute spacing
        out = _run(rows, resolution="hourly")
        assert len(out) == 334
        assert len(out) < MAX_POINTS


class TestNullValues:
    """A gap is real data at `raw`; it is meaningless to LTTB."""

    def test_nulls_survive_an_unreduced_series(self):
        """Below the threshold a gap is data and is returned as it was stored."""
        rows = _series(10)
        rows[5].value = None
        assert len(_run(rows)) == 10

    def test_nulls_are_dropped_before_lttb(self):
        """LTTB weighs triangle areas, so a null has no position to contribute."""
        rows = _series(5_000)
        for r in rows[:100]:
            r.value = None
        out = _run(rows)
        assert all(r.value is not None for r in out)
