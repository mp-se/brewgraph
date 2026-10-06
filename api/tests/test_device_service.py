# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

# pylint: disable=too-few-public-methods
"""Tests for DeviceService methods not covered by endpoint tests."""
from datetime import UTC, datetime, timedelta

import pytest

from core.db import create_session
from core.enums import DeviceColor, DeviceStatus, DeviceType
from oss.schemas.batch import BatchCreate
from oss.schemas.device import DeviceCreate
from oss.schemas.pressure_reading import PressureReadingCreate
from oss.services.batch import BatchService
from oss.services.device import DeviceService
from oss.services.pressure import PressureService
from tests.conftest import truncate_database


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate the database before each test."""
    truncate_database()


def _dev_svc():
    """Return a fresh DeviceService instance."""
    return DeviceService(create_session())


def _create_device(name="TestDev", device_type=None, device_color=DeviceColor.WHITE):
    """Create a device with optional device type/color and return it."""
    return _dev_svc().create(
        DeviceCreate(name=name, device_type=device_type, device_color=device_color)
    )


def _batch_id():
    """Create a batch and return its id."""
    return BatchService(create_session()).create(BatchCreate(name="DevSvcBatch")).id


def _stamp_last_seen(device_id, offset_hours=0):
    """Stamp a device's `last_seen` directly — `status_for_all` reads only this."""
    session = create_session()
    device = DeviceService(session).get(device_id)
    device.last_seen = datetime.now(UTC) - timedelta(hours=offset_hours)
    session.commit()


def _pressure_reading(batch_id, device_id, offset_hours=0):
    """Build a PressureReadingCreate for status tests."""
    return PressureReadingCreate(
        batch_id=batch_id,
        device_id=device_id,
        pressure=101.0,
        temperature=20.0,
        battery=3.8,
        rssi=-70,
        created_at=datetime.now(UTC) - timedelta(hours=offset_hours),
    )


class TestSearchDeviceType:
    """Tests for DeviceService.search_device_type."""

    def test_finds_devices_by_device_type(self):
        """Returns devices matching the given device_type."""
        _create_device("Dev1", device_type=DeviceType.GRAVITYMON)
        _create_device("Dev2", device_type=DeviceType.ISPINDEL)
        results = _dev_svc().search_device_type(DeviceType.GRAVITYMON)
        assert len(results) == 1
        assert results[0].name == "Dev1"

    def test_returns_empty_for_unknown_device_type(self):
        """Returns empty list when no device matches the given device_type."""
        _create_device("Dev1", device_type=DeviceType.ISPINDEL)
        assert _dev_svc().search_device_type(DeviceType.GRAVITYMON) == []


class TestSearchDeviceColor:
    """Tests for DeviceService.search_device_color."""

    def test_finds_devices_by_device_color(self):
        """Returns devices matching the given physical-device color."""
        _create_device("BlueDev", device_color=DeviceColor.BLUE)
        _create_device("RedDev", device_color=DeviceColor.RED)
        results = _dev_svc().search_device_color(DeviceColor.BLUE)
        assert len(results) == 1
        assert results[0].name == "BlueDev"

    def test_returns_empty_for_unused_device_color(self):
        """Returns empty list when no device has the requested color."""
        assert _dev_svc().search_device_color(DeviceColor.PURPLE) == []


class TestStatusForAll:
    """Tests for DeviceService.status_for_all."""

    def test_never_seen_when_no_readings(self):
        """Device with no readings gets NEVER_SEEN status."""
        dev = _create_device("NeverSeen")
        statuses = DeviceService(create_session()).status_for_all()
        match = next((s for s in statuses if s.device_id == dev.id), None)
        assert match is not None
        assert match.status == DeviceStatus.NEVER_SEEN
        assert match.last_seen_at is None

    def test_active_status_for_recent_last_seen(self):
        """Device with a recent `last_seen` gets ACTIVE status.

        §1: `status_for_all` now derives status from `Device.last_seen` alone,
        not from `GravityReading`/`PressureReading` timestamps — every
        reading-producing write path stamps `last_seen`, so a reading is no
        longer the thing this test needs to assert against.
        """
        dev = _create_device("ActiveDev")
        _stamp_last_seen(dev.id, offset_hours=1)

        statuses = DeviceService(create_session()).status_for_all()
        match = next((s for s in statuses if s.device_id == dev.id), None)
        assert match is not None
        assert match.status == DeviceStatus.ACTIVE

    def test_disconnected_status_for_old_last_seen(self):
        """Device with a stale `last_seen` gets DISCONNECTED status."""
        dev = _create_device("OldDev")
        _stamp_last_seen(dev.id, offset_hours=10)

        statuses = DeviceService(create_session()).status_for_all()
        match = next((s for s in statuses if s.device_id == dev.id), None)
        assert match is not None
        assert match.status == DeviceStatus.DISCONNECTED

    def test_active_status_ignores_reading_recency_when_last_seen_is_stale(self):
        """A recent gravity/pressure reading must not feed status on its own.

        Status must not be computed from
        `max(GravityReading.created_at, PressureReading.created_at)` — a
        temperature-only device, or a device whose `last_seen` stamp lags its
        readings for any reason, would show the wrong status. A recent
        reading with a stale `last_seen` must report DISCONNECTED, not
        ACTIVE.
        """
        dev = _create_device("PressureDev")
        bid = _batch_id()
        PressureService(create_session()).create(
            _pressure_reading(bid, dev.id, offset_hours=0)
        )
        _stamp_last_seen(dev.id, offset_hours=10)

        statuses = DeviceService(create_session()).status_for_all()
        match = next((s for s in statuses if s.device_id == dev.id), None)
        assert match is not None
        assert match.status == DeviceStatus.DISCONNECTED

    def test_empty_list_when_no_devices(self):
        """Returns empty list when no devices exist."""
        assert not DeviceService(create_session()).status_for_all()


class TestSoftDelete:
    """Tests for DeviceService.soft_delete."""

    def test_soft_delete_hides_device(self):
        """Soft-deleted device no longer appears in list()."""
        dev = _create_device("ToDelete")
        svc = _dev_svc()
        svc.soft_delete(dev.id)
        visible = DeviceService(create_session()).list()
        assert all(d.id != dev.id for d in visible)

    def test_soft_delete_returns_false_for_unknown_device(self):
        """soft_delete returns False and does nothing when the device does not exist."""
        import uuid  # pylint: disable=import-outside-toplevel
        result = _dev_svc().soft_delete(uuid.uuid4())
        assert result is False


class TestGenerateToken:
    """Tests for DeviceService.generate_token."""

    def test_generate_token_raises_for_unknown_device(self):
        """generate_token raises ValueError when the device does not exist."""
        import uuid  # pylint: disable=import-outside-toplevel
        with pytest.raises(ValueError):
            _dev_svc().generate_token(uuid.uuid4())
