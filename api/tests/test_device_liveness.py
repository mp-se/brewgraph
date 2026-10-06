# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
"""Device liveness: `Device.last_seen` is stamped on every token-resolved ingest."""
# pylint: disable=missing-function-docstring,protected-access
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from core.enums import DeviceType
from oss.services.ingestion import IngestionService

# Device types that authenticate with a *device* token and therefore have a resolved
# Device in hand at write time. KEGMON is deliberately excluded: it authenticates with
# a *tap* token and carries no device identity in its payload at all, so there is
# nothing to stamp — pour hardware records its liveness on the Tap instead.
TOKEN_RESOLVED_TYPES = [
    DeviceType.ISPINDEL,
    DeviceType.GRAVITYMON,
    DeviceType.GRAVITYMON_GATEWAY,
    DeviceType.PRESSUREMON,
    DeviceType.CHAMBER_CONTROLLER,
]


def _make_svc(db=None):
    settings = MagicMock()
    settings.unit_type = "metric"
    return IngestionService(db or MagicMock(), settings)


def _mock_device(**overrides):
    d = MagicMock()
    d.id = uuid.uuid4()
    d.batch_id = overrides.get("batch_id", uuid.uuid4())
    d.vessel_id = overrides.get("vessel_id")
    d.last_seen = None
    return d


def _mock_batch(**overrides):
    b = MagicMock()
    b.id = uuid.uuid4()
    b.og = overrides.get("og")
    b.fg = overrides.get("fg")
    return b


def _assert_stamped_recently(device, before: datetime):
    assert device.last_seen is not None
    assert device.last_seen.tzinfo is not None, "last_seen must be timezone-aware"
    assert device.last_seen.utcoffset() == timedelta(0), "last_seen must be UTC"
    now = datetime.now(UTC)
    assert before <= device.last_seen <= now + timedelta(seconds=5)


@pytest.mark.parametrize("device_type", TOKEN_RESOLVED_TYPES)
def test_last_seen_stamped_for_every_token_resolved_device_type(device_type):
    """Every device-token type stamps last_seen on ingest."""
    svc = _make_svc()
    device = _mock_device()
    before = datetime.now(UTC)

    if device_type == DeviceType.PRESSUREMON:
        svc._pressure_svc = MagicMock()
        svc.write_pressure(device, {"pressure": 10.0})
    elif device_type == DeviceType.CHAMBER_CONTROLLER:
        svc._device_svc.find_by_token = MagicMock(return_value=device)
        svc._temp_svc = MagicMock()
        svc.write_temp("some-token", temperature=20.0)
    else:
        batch = _mock_batch()
        svc._gravity_svc = MagicMock()
        svc.write_gravity(batch, device, {"gravity": 1.050})

    _assert_stamped_recently(device, before)


def test_last_seen_stamped_even_when_temp_write_is_dropped():
    """write_temp stamps + commits liveness even on the silently-dropped no-context branch."""
    svc = _make_svc()
    device = _mock_device(batch_id=None, vessel_id=None)
    svc._device_svc.find_by_token = MagicMock(return_value=device)
    before = datetime.now(UTC)

    returned = svc.write_temp("some-token", temperature=20.0)

    assert returned is device
    _assert_stamped_recently(device, before)
    svc._db.commit.assert_called_once()


def test_last_seen_stamp_survives_unrelated_gravity_write_failure():
    """The liveness stamp is applied before the reading write, so an unrelated failure
    in the reading write does not prevent the stamp from having been set on the object."""
    svc = _make_svc()
    device = _mock_device()
    batch = _mock_batch()
    svc._gravity_svc = MagicMock()
    svc._gravity_svc.create.side_effect = RuntimeError("unrelated db failure")
    before = datetime.now(UTC)

    with pytest.raises(RuntimeError):
        svc.write_gravity(batch, device, {"gravity": 1.050})

    _assert_stamped_recently(device, before)


def test_last_seen_stamp_survives_unrelated_pressure_write_failure():
    svc = _make_svc()
    device = _mock_device()
    svc._pressure_svc = MagicMock()
    svc._pressure_svc.create.side_effect = RuntimeError("unrelated db failure")
    before = datetime.now(UTC)

    with pytest.raises(RuntimeError):
        svc.write_pressure(device, {"pressure": 10.0})

    _assert_stamped_recently(device, before)


def test_touch_device_from_token_removed():
    """The dead, zero-caller helper is not shipped unused."""
    assert not hasattr(IngestionService, "touch_device_from_token")


def test_write_pour_takes_no_device_argument():
    """write_pour resolves a Tap, never a Device — so pour liveness lives on the Tap."""
    import inspect  # pylint: disable=import-outside-toplevel
    params = inspect.signature(IngestionService.write_pour).parameters
    assert "device" not in params
