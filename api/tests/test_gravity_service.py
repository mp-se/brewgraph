# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

# pylint: disable=too-few-public-methods
"""Tests for GravityService methods not covered by endpoint tests."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from core.db import create_session
from oss.schemas.batch import BatchCreate
from oss.schemas.device import DeviceCreate
from oss.schemas.gravity_reading import GravityReadingCreate
from oss.services.batch import BatchService
from oss.services.device import DeviceService
from oss.services.gravity import GravityService
from tests.conftest import truncate_database


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate the database before each test."""
    truncate_database()


def _batch_id():
    """Create a batch and return its id."""
    return BatchService(create_session()).create(BatchCreate(name="GravSvcTest")).id


def _device_id():
    """Create a device row and return its id, so FK-checking backends accept it."""
    svc = DeviceService(create_session())
    return svc.create(DeviceCreate(name=f"dev-{uuid.uuid4().hex[:6]}")).id


def _svc():
    """Return a fresh GravityService instance."""
    return GravityService(create_session())


def _reading(batch_id, gravity=1.050, offset_hours=0, excluded=False, device_id=None):
    """Build a GravityReadingCreate with sensible defaults."""
    return GravityReadingCreate(
        batch_id=batch_id,
        device_id=device_id or _device_id(),
        gravity=gravity,
        temperature=20.0,
        battery=3.8,
        rssi=-70,
        excluded=excluded,
        created_at=datetime.now(UTC) - timedelta(hours=offset_hours),
    )


class TestCreateList:
    """Tests for GravityService.create_list."""

    def test_empty_list_raises_400(self):
        """create_list with empty list raises HTTP 400."""
        with pytest.raises(HTTPException) as exc_info:
            _svc().create_list([])
        assert exc_info.value.status_code == 400


class TestSearchByBatchIdCursor:
    """Tests for GravityService.search_by_batch_id_cursor with cursor set."""

    def test_cursor_excludes_older_readings(self):
        """Readings at or before the cursor timestamp are excluded from results."""
        bid = _batch_id()
        svc = _svc()
        old = svc.create(_reading(bid, offset_hours=2))
        new = svc.create(_reading(bid, offset_hours=0))

        results, has_more = GravityService(create_session()).search_by_batch_id_cursor(
            bid, cursor=(old.created_at, str(old.id))
        )
        ids = [r.id for r in results]
        assert old.id not in ids
        assert new.id in ids
        assert has_more is False

    def test_has_more_true_when_more_than_limit(self):
        """has_more is True when results exceed the page limit."""
        bid = _batch_id()
        svc = _svc()
        for i in range(5):
            svc.create(_reading(bid, offset_hours=10 - i))

        results, has_more = GravityService(create_session()).search_by_batch_id_cursor(
            bid, limit=3
        )
        assert len(results) == 3
        assert has_more is True

    def test_pages_through_rows_sharing_one_created_at_without_dropping_any(self):
        """A strict `created_at > cursor` filter silently drops rows that share the
        boundary row's exact timestamp — routine here, since chamber polls and every
        bulk-insert endpoint write one shared `created_at` across several rows. The
        compound `(created_at, id)` cursor must return every row exactly once."""
        bid = _batch_id()
        svc = _svc()
        shared = datetime.now(UTC)
        created = [
            svc.create(_reading(bid, gravity=1.050 + i * 0.001, offset_hours=0))
            for i in range(5)
        ]
        # Force every row onto the same timestamp, as a bulk import or chamber poll would.
        for row in created:
            row.created_at = shared
        svc.db_session.commit()

        seen_ids = []
        cursor = None
        for _ in range(10):  # bounded so a broken cursor cannot loop forever
            page, has_more = GravityService(create_session()).search_by_batch_id_cursor(
                bid, limit=2, cursor=cursor
            )
            assert page, "page came back empty while has_more was still true"
            seen_ids.extend(r.id for r in page)
            if not has_more:
                break
            cursor = (page[-1].created_at, str(page[-1].id))

        assert sorted(seen_ids) == sorted(r.id for r in created)
        assert len(seen_ids) == len(set(seen_ids)), "cursor paging returned a duplicate row"


class TestSearchByBatchIdLast24h:
    """Tests for GravityService.search_by_batch_id_last_24h."""

    def test_returns_only_recent_readings(self):
        """Only readings within the last 24 hours are returned."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, offset_hours=1))    # within 24h
        svc.create(_reading(bid, offset_hours=48))   # older than 24h

        results = GravityService(create_session()).search_by_batch_id_last_24h(bid)
        assert len(results) == 1

    def test_returns_empty_for_no_recent_readings(self):
        """Returns an empty list when no readings exist within 24 hours."""
        bid = _batch_id()
        _svc().create(_reading(bid, offset_hours=50))
        results = GravityService(create_session()).search_by_batch_id_last_24h(bid)
        assert len(results) == 0


class TestEarliestForBatchWithCutoff:
    """Tests for GravityService.earliest_for_batch with retention_cutoff."""

    def test_earliest_without_cutoff(self):
        """Returns the oldest reading when no cutoff is set."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, offset_hours=10))
        newer = svc.create(_reading(bid, offset_hours=1))
        _ = newer  # noqa
        oldest = svc.create(_reading(bid, offset_hours=20))
        result = GravityService(create_session()).earliest_for_batch(bid)
        assert result.id == oldest.id

    def test_earliest_with_cutoff_excludes_old(self):
        """Readings before retention_cutoff are excluded from earliest result."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, offset_hours=48))    # before cutoff
        recent = svc.create(_reading(bid, offset_hours=1))  # after cutoff

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        result = GravityService(create_session()).earliest_for_batch(bid, retention_cutoff=cutoff)
        assert result.id == recent.id


class TestHighestForBatchWithCutoff:
    """Tests for GravityService.highest_for_batch with retention_cutoff."""

    def test_highest_ignores_pre_cutoff_readings(self):
        """High-gravity reading before cutoff is excluded; lower post-cutoff reading wins."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, gravity=1.080, offset_hours=48))  # before cutoff
        svc.create(_reading(bid, gravity=1.050, offset_hours=1))   # after cutoff

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        result = GravityService(create_session()).highest_for_batch(bid, retention_cutoff=cutoff)
        assert result.gravity == 1.050

    def test_highest_returns_none_for_empty_batch(self):
        """Returns None when no readings exist for the batch."""
        bid = _batch_id()
        assert _svc().highest_for_batch(bid) is None


class TestLowestForBatchWithCutoff:
    """Tests for GravityService.lowest_for_batch with retention_cutoff."""

    def test_lowest_ignores_pre_cutoff_readings(self):
        """Low-gravity reading before cutoff is excluded; higher post-cutoff reading wins."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, gravity=1.005, offset_hours=48))  # before cutoff
        svc.create(_reading(bid, gravity=1.020, offset_hours=1))   # after cutoff

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        result = GravityService(create_session()).lowest_for_batch(bid, retention_cutoff=cutoff)
        assert result.gravity == 1.020

    def test_lowest_returns_none_for_empty_batch(self):
        """Returns None when no readings exist for the batch."""
        bid = _batch_id()
        assert _svc().lowest_for_batch(bid) is None


class TestChartDataFilters:
    """Tests for GravityService.chart_data with from_dt and to_dt."""

    def test_from_dt_filter(self):
        """Readings before from_dt are excluded from chart data."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, gravity=1.060, offset_hours=10))
        svc.create(_reading(bid, gravity=1.050, offset_hours=1))

        from_dt = datetime.now(UTC) - timedelta(hours=5)
        points = GravityService(create_session()).chart_data(bid, from_dt=from_dt)
        assert len(points) == 1
        assert points[0].g == 1.050

    def test_to_dt_filter(self):
        """Readings after to_dt are excluded from chart data."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, gravity=1.060, offset_hours=10))
        svc.create(_reading(bid, gravity=1.050, offset_hours=1))

        to_dt = datetime.now(UTC) - timedelta(hours=5)
        points = GravityService(create_session()).chart_data(bid, to_dt=to_dt)
        assert len(points) == 1
        assert points[0].g == 1.060

    def test_from_and_to_dt_filter(self):
        """Only readings within [from_dt, to_dt] range are returned."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, gravity=1.070, offset_hours=20))  # too old
        svc.create(_reading(bid, gravity=1.060, offset_hours=8))   # in range
        svc.create(_reading(bid, gravity=1.050, offset_hours=1))   # too recent

        from_dt = datetime.now(UTC) - timedelta(hours=15)
        to_dt = datetime.now(UTC) - timedelta(hours=3)
        points = GravityService(create_session()).chart_data(bid, from_dt=from_dt, to_dt=to_dt)
        assert len(points) == 1
        assert points[0].g == 1.060


class TestRetentionCutoffBranches:
    """Tests for retention_cutoff branches in count_for_batch, latest_for_batch, cursor."""

    def test_count_for_batch_with_retention_cutoff(self):
        """count_for_batch excludes readings before the retention cutoff."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, gravity=1.060, offset_hours=48))
        svc.create(_reading(bid, gravity=1.050, offset_hours=1))

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        count = GravityService(create_session()).count_for_batch(bid, retention_cutoff=cutoff)
        assert count == 1

    def test_latest_for_batch_with_retention_cutoff(self):
        """latest_for_batch excludes readings before the retention cutoff."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, gravity=1.060, offset_hours=48))
        recent = svc.create(_reading(bid, gravity=1.040, offset_hours=1))

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        result = GravityService(create_session()).latest_for_batch(bid, retention_cutoff=cutoff)
        assert result.id == recent.id

    def test_cursor_with_retention_cutoff(self):
        """search_by_batch_id_cursor respects retention_cutoff."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, gravity=1.060, offset_hours=48))
        svc.create(_reading(bid, gravity=1.050, offset_hours=1))

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        results, _ = GravityService(create_session()).search_by_batch_id_cursor(
            bid, retention_cutoff=cutoff
        )
        assert len(results) == 1
        assert results[0].gravity == 1.050
