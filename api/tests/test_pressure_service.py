# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

# pylint: disable=too-few-public-methods
"""Tests for PressureService methods not covered by endpoint tests."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from core.db import create_session
from core.enums import VesselType
from oss.schemas.batch import BatchCreate
from oss.schemas.device import DeviceCreate
from oss.schemas.pressure_reading import PressureReadingCreate
from oss.schemas.storage_vessel import StorageVesselCreate
from oss.services.batch import BatchService
from oss.services.device import DeviceService
from oss.services.pressure import PressureService
from oss.services.storage_vessel import StorageVesselService
from tests.conftest import truncate_database


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate the database before each test."""
    truncate_database()


def _batch_id():
    svc = BatchService(create_session())
    return svc.create(BatchCreate(name="PressureTestBatch")).id


def _device_id():
    """Create a device row and return its id, so FK-checking backends accept it."""
    svc = DeviceService(create_session())
    return svc.create(DeviceCreate(name=f"dev-{uuid.uuid4().hex[:6]}")).id


def _vessel_id():
    """Create a storage vessel row and return its id."""
    svc = StorageVesselService(create_session())
    return svc.create(
        StorageVesselCreate(vessel_type=VesselType.KEG, name=f"vessel-{uuid.uuid4().hex[:6]}")
    ).id


def _svc():
    return PressureService(create_session())


def _reading(batch_id, pressure=100.0, offset_hours=0, excluded=False, device_id=None):
    return PressureReadingCreate(
        batch_id=batch_id,
        device_id=device_id or _device_id(),
        pressure=pressure,
        temperature=20.0,
        battery=3.8,
        rssi=-70,
        excluded=excluded,
        created_at=datetime.now(UTC) - timedelta(hours=offset_hours),
    )


class TestCreateList:
    """Tests for PressureService.create_list."""

    def test_empty_list_raises_400(self):
        """Raises HTTP 400 when an empty list is passed to create_list."""
        with pytest.raises(HTTPException) as exc_info:
            _svc().create_list([])
        assert exc_info.value.status_code == 400

    def test_valid_list_persisted(self):
        """All readings in a valid list are persisted to the database."""
        bid = _batch_id()
        readings = [_reading(bid, pressure=100.0 + i) for i in range(3)]
        created = _svc().create_list(readings)
        assert len(created) == 3


class TestSearchByBatchIdCursor:
    """Tests for PressureService.search_by_batch_id_cursor."""

    def test_cursor_excludes_older_readings(self):
        """Readings at or before the cursor timestamp are excluded from results."""
        bid = _batch_id()
        svc = _svc()
        old = svc.create(_reading(bid, offset_hours=2))
        new = svc.create(_reading(bid, offset_hours=0))

        results, has_more = PressureService(create_session()).search_by_batch_id_cursor(
            bid, cursor=(old.created_at, str(old.id))
        )
        ids = [r.id for r in results]
        assert old.id not in ids
        assert new.id in ids
        assert has_more is False

    def test_has_more_true_when_more_than_limit(self):
        """has_more is True when the total result count exceeds the page limit."""
        bid = _batch_id()
        svc = _svc()
        for i in range(5):
            svc.create(_reading(bid, offset_hours=10 - i))

        results, has_more = PressureService(create_session()).search_by_batch_id_cursor(
            bid, limit=3
        )
        assert len(results) == 3
        assert has_more is True


class TestLatestForDevice:
    """Tests for PressureService.latest_for_device."""

    def test_returns_most_recent(self):
        """Returns the reading with the most recent timestamp for the given device."""
        bid = _batch_id()
        dev_id = _device_id()
        svc = _svc()
        svc.create(_reading(bid, device_id=dev_id, offset_hours=2))
        newer = svc.create(_reading(bid, device_id=dev_id, offset_hours=0))

        result = PressureService(create_session()).latest_for_device(dev_id)
        assert result.id == newer.id

    def test_returns_none_for_unknown_device(self):
        """Returns None when no readings exist for the given device ID."""
        assert _svc().latest_for_device(uuid.uuid4()) is None


class TestLatestGlobal:
    """Tests for PressureService.latest_global."""

    def test_returns_up_to_limit(self):
        """Returns at most limit readings from all batches, newest first."""
        bid = _batch_id()
        svc = _svc()
        for i in range(4):
            svc.create(_reading(bid, offset_hours=10 - i))

        results = PressureService(create_session()).latest_global(limit=2)
        assert len(results) == 2


class TestHighestAndLowest:
    """Tests for PressureService.highest_for_batch and lowest_for_batch."""

    def test_highest_for_batch(self):
        """Returns the reading with the highest pressure value for the batch."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, pressure=90.0, offset_hours=2))
        svc.create(_reading(bid, pressure=110.0, offset_hours=1))

        result = PressureService(create_session()).highest_for_batch(bid)
        assert result.pressure == 110.0

    def test_lowest_for_batch(self):
        """Returns the reading with the lowest pressure value for the batch."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, pressure=90.0, offset_hours=2))
        svc.create(_reading(bid, pressure=110.0, offset_hours=1))

        result = PressureService(create_session()).lowest_for_batch(bid)
        assert result.pressure == 90.0

    def test_returns_none_for_empty_batch(self):
        """Returns None for both highest and lowest when the batch has no readings."""
        bid = _batch_id()
        assert _svc().highest_for_batch(bid) is None
        assert _svc().lowest_for_batch(bid) is None

    def test_with_retention_cutoff(self):
        """Readings before the retention cutoff are excluded from highest calculation."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, pressure=120.0, offset_hours=48))  # before cutoff
        svc.create(_reading(bid, pressure=100.0, offset_hours=1))   # after cutoff

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        result = PressureService(create_session()).highest_for_batch(bid, retention_cutoff=cutoff)
        assert result.pressure == 100.0


class TestCountWithRetentionCutoff:
    """Tests for PressureService.count_for_batch with retention cutoff."""

    def test_count_respects_cutoff(self):
        """Only readings after the retention cutoff are included in the count."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, offset_hours=48))  # before cutoff
        svc.create(_reading(bid, offset_hours=1))   # after cutoff

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        count = PressureService(create_session()).count_for_batch(bid, retention_cutoff=cutoff)
        assert count == 1


class TestChartData:
    """Tests for PressureService.chart_data."""

    def test_returns_chart_points(self):
        """Returns chart data points with a pressure attribute for each reading."""
        bid = _batch_id()
        svc = _svc()
        for i in range(3):
            svc.create(_reading(bid, pressure=100.0 + i, offset_hours=10 - i))

        points = PressureService(create_session()).chart_data(bid)
        assert len(points) == 3
        assert all(hasattr(p, "p") for p in points)

    def test_from_to_filter(self):
        """Applies from_dt filter to exclude readings before the given datetime."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, pressure=100.0, offset_hours=10))
        svc.create(_reading(bid, pressure=105.0, offset_hours=1))

        from_dt = datetime.now(UTC) - timedelta(hours=5)
        points = PressureService(create_session()).chart_data(bid, from_dt=from_dt)
        assert len(points) == 1
        assert points[0].p == 105.0


class TestCursorWithRetentionCutoff:
    """Tests for search_by_batch_id_cursor with retention_cutoff."""

    def test_cursor_respects_retention_cutoff(self):
        """search_by_batch_id_cursor excludes readings before the retention cutoff."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, pressure=100.0, offset_hours=48))
        svc.create(_reading(bid, pressure=105.0, offset_hours=1))

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        results, _ = PressureService(create_session()).search_by_batch_id_cursor(
            bid, retention_cutoff=cutoff
        )
        assert len(results) == 1
        assert results[0].pressure == 105.0


class TestSearchByBatchId:
    """Tests for PressureService.search_by_batch_id with include_excluded and retention_cutoff."""

    def test_include_excluded_returns_all(self):
        """include_excluded=True returns both excluded and non-excluded readings."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, pressure=100.0, excluded=False))
        svc.create(_reading(bid, pressure=101.0, excluded=True, offset_hours=1))

        results = PressureService(create_session()).search_by_batch_id(bid, include_excluded=True)
        assert len(results) == 2

    def test_retention_cutoff_excludes_old_readings(self):
        """Readings before the retention cutoff are excluded from results."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, pressure=100.0, offset_hours=48))  # before cutoff
        svc.create(_reading(bid, pressure=105.0, offset_hours=1))   # after cutoff

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        results = PressureService(create_session()).search_by_batch_id(
            bid, retention_cutoff=cutoff
        )
        assert len(results) == 1
        assert results[0].pressure == 105.0


class TestSearchByBatchIdLast24h:
    """Tests for PressureService.search_by_batch_id_last_24h."""

    def test_returns_only_recent_readings(self):
        """Only readings within the last 24 hours are returned."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, offset_hours=1))    # within 24h
        svc.create(_reading(bid, offset_hours=48))   # older than 24h

        results = PressureService(create_session()).search_by_batch_id_last_24h(bid)
        assert len(results) == 1

    def test_returns_empty_for_no_recent_readings(self):
        """Returns empty list when no readings are within the last 24 hours."""
        bid = _batch_id()
        _svc().create(_reading(bid, offset_hours=50))
        results = PressureService(create_session()).search_by_batch_id_last_24h(bid)
        assert len(results) == 0


class TestLatestForBatchWithCutoff:
    """Tests for PressureService.latest_for_batch with retention_cutoff."""

    def test_latest_with_cutoff_excludes_old(self):
        """Readings before the retention cutoff are excluded from latest result."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, pressure=120.0, offset_hours=48))  # before cutoff
        recent = svc.create(_reading(bid, pressure=100.0, offset_hours=1))

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        result = PressureService(create_session()).latest_for_batch(bid, retention_cutoff=cutoff)
        assert result.id == recent.id


class TestLowestWithCutoff:
    """Tests for PressureService.lowest_for_batch with retention_cutoff."""

    def test_lowest_ignores_pre_cutoff_readings(self):
        """Low-pressure reading before cutoff is excluded; higher post-cutoff reading wins."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, pressure=50.0, offset_hours=48))  # before cutoff
        svc.create(_reading(bid, pressure=100.0, offset_hours=1))  # after cutoff

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        result = PressureService(create_session()).lowest_for_batch(bid, retention_cutoff=cutoff)
        assert result.pressure == 100.0


class TestChartDataToFilter:
    """Tests for PressureService.chart_data with to_dt filter."""

    def test_to_dt_excludes_recent_readings(self):
        """Readings after to_dt are excluded from chart data."""
        bid = _batch_id()
        svc = _svc()
        svc.create(_reading(bid, pressure=100.0, offset_hours=10))
        svc.create(_reading(bid, pressure=105.0, offset_hours=1))

        to_dt = datetime.now(UTC) - timedelta(hours=5)
        points = PressureService(create_session()).chart_data(bid, to_dt=to_dt)
        assert len(points) == 1
        assert points[0].p == 100.0


class TestChartDataByVessel:
    """Tests for PressureService.chart_data_by_vessel."""

    def test_returns_chart_points_for_vessel(self):
        """chart_data_by_vessel returns readings associated with the given vessel_id."""
        bid = _batch_id()
        vessel_id = _vessel_id()
        svc = _svc()
        # Create a reading with a vessel_id
        r = PressureReadingCreate(
            batch_id=bid,
            device_id=_device_id(),
            pressure=103.0,
            temperature=20.0,
            battery=3.8,
            rssi=-70,
            vessel_id=vessel_id,
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
        svc.create(r)
        # Create a reading with no vessel_id (should not appear)
        svc.create(_reading(bid, pressure=99.0))

        points = PressureService(create_session()).chart_data_by_vessel(vessel_id)
        assert len(points) == 1
        assert points[0].p == 103.0

    def test_returns_empty_for_unknown_vessel(self):
        """Returns empty list when no readings exist for the given vessel_id."""
        points = _svc().chart_data_by_vessel(uuid.uuid4())
        assert points == []

    def test_from_dt_filter(self):
        """chart_data_by_vessel respects from_dt and excludes older readings."""
        bid = _batch_id()
        vessel_id = _vessel_id()
        svc = _svc()
        svc.create(PressureReadingCreate(
            batch_id=bid, vessel_id=vessel_id, device_id=_device_id(),
            pressure=100.0, temperature=20.0,
            created_at=datetime.now(UTC) - timedelta(hours=10),
        ))
        svc.create(PressureReadingCreate(
            batch_id=bid, vessel_id=vessel_id, device_id=_device_id(),
            pressure=105.0, temperature=20.0,
            created_at=datetime.now(UTC) - timedelta(hours=1),
        ))

        from_dt = datetime.now(UTC) - timedelta(hours=5)
        points = PressureService(create_session()).chart_data_by_vessel(vessel_id, from_dt=from_dt)
        assert len(points) == 1
        assert points[0].p == 105.0

    def test_to_dt_filter(self):
        """chart_data_by_vessel respects to_dt and excludes recent readings."""
        bid = _batch_id()
        vessel_id = _vessel_id()
        svc = _svc()
        svc.create(PressureReadingCreate(
            batch_id=bid, vessel_id=vessel_id, device_id=_device_id(),
            pressure=100.0, temperature=20.0,
            created_at=datetime.now(UTC) - timedelta(hours=10),
        ))
        svc.create(PressureReadingCreate(
            batch_id=bid, vessel_id=vessel_id, device_id=_device_id(),
            pressure=105.0, temperature=20.0,
            created_at=datetime.now(UTC) - timedelta(hours=1),
        ))

        to_dt = datetime.now(UTC) - timedelta(hours=5)
        points = PressureService(create_session()).chart_data_by_vessel(vessel_id, to_dt=to_dt)
        assert len(points) == 1
        assert points[0].p == 100.0
