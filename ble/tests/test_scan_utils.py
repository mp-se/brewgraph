# BrewGraph
# Copyright (c) 2024-2026 Magnus
# GPL-3 / Commercial dual license

"""Unit tests for scan.py utility functions, skip-flag paths, and device_found dispatch."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests as req_lib

import scan
from tests.conftest import MockAdvertisementData, MockBLEDevice
from tests.packets import (FEAA_UUID, TEST_CHIP_ID, chamber_ibeacon,
                           gravitymon_eddystone, gravitymon_ibeacon,
                           pressuremon_ibeacon)

CHIP_HEX = hex(TEST_CHIP_ID)[2:]


# ---------------------------------------------------------------------------
# remove_none_values — list branch and plain-value branch
# ---------------------------------------------------------------------------

def test_remove_none_values_list():
    """remove_none_values filters None entries from a list when flag is set."""
    scan.SKIP_NULL_VALUES = True
    result = scan.remove_none_values([1, None, 2, None])
    assert result == [1, 2]
    scan.SKIP_NULL_VALUES = False


def test_remove_none_values_scalar():
    """remove_none_values returns a scalar unchanged when flag is set."""
    scan.SKIP_NULL_VALUES = True
    assert scan.remove_none_values(42) == 42
    scan.SKIP_NULL_VALUES = False


def test_remove_none_values_disabled():
    """remove_none_values returns the original object when flag is False."""
    scan.SKIP_NULL_VALUES = False
    obj = [None, 1, None]
    assert scan.remove_none_values(obj) is obj


# ---------------------------------------------------------------------------
# _post — success and network-error branches
# ---------------------------------------------------------------------------

def test_post_success_logs_status():
    """_post fires requests.post and logs the status code."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    with patch("scan.requests.post", return_value=mock_response) as mock_post:
        scan.skip_push = False
        scan._post("http://localhost/ingest", {"gravity": 1.05}, "test")  # pylint: disable=protected-access
        scan.skip_push = True
    mock_post.assert_called_once()


def test_post_request_exception_is_swallowed():
    """_post swallows RequestException without raising."""
    with patch("scan.requests.post", side_effect=req_lib.exceptions.RequestException("fail")):
        scan.skip_push = False
        scan._post("http://localhost/ingest", {}, "test")  # must not raise  # pylint: disable=protected-access
        scan.skip_push = True


# ---------------------------------------------------------------------------
# BLE device-token mapping
# ---------------------------------------------------------------------------

def test_load_device_tokens_uses_protocol_specific_keys_and_authenticated_list():
    """Each BLE protocol maps its transmitted key via one authenticated device GET."""
    response = MagicMock()
    response.json.return_value = {
        "items": [
            {
                "deviceType": "gravitymon",
                "chipId": "00DEAD",
                "deviceColor": "red",
                "token": "gravity-token",
            },
            {
                "deviceType": "pressuremon",
                "chipId": "dead",
                "deviceColor": "blue",
                "token": "pressure-token",
            },
        ]
    }
    with patch("scan.requests.get", return_value=response) as mock_get:
        assert scan.load_device_tokens() is True

    assert scan.gravitymon_device_tokens == {"dead": "gravity-token"}
    assert scan.pressuremon_device_tokens == {"dead": "pressure-token"}
    mock_get.assert_called_once_with(scan.endpoint_devices, headers=scan.headers, timeout=10)


def test_load_device_tokens_rejects_duplicate_protocol_keys():
    """Duplicate transmitted IDs fail closed within their protocol."""
    response = MagicMock()
    response.json.return_value = {
        "items": [
            {
                "deviceType": "gravitymon",
                "chipId": "dead",
                "deviceColor": "red",
                "token": "first-token",
            },
            {
                "deviceType": "gravitymon",
                "chipId": "00DEAD",
                "deviceColor": "red",
                "token": "second-token",
            },
        ]
    }
    with patch("scan.requests.get", return_value=response):
        assert scan.load_device_tokens() is False

    assert "dead" not in scan.gravitymon_device_tokens


def test_load_device_tokens_clears_stale_maps_on_request_error():
    """An unavailable device list leaves no stale token mapping active."""
    scan.gravitymon_device_tokens["dead"] = "stale-token"
    scan.pressuremon_device_tokens["beef"] = "stale-token"
    scan.chamber_device_tokens["cafe"] = "stale-token"
    with patch("scan.requests.get", side_effect=req_lib.exceptions.RequestException("down")):
        assert scan.load_device_tokens() is False

    assert not scan.gravitymon_device_tokens
    assert not scan.pressuremon_device_tokens
    assert not scan.chamber_device_tokens


# ---------------------------------------------------------------------------
# Skip-flag paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_gravitymon_skipped_when_flag_set():
    """parse_gravitymon returns immediately when skip_gravitymon is True."""
    scan.skip_gravitymon = True
    with patch("scan.requests.post") as mock_post:
        adv = MockAdvertisementData(manufacturer_data=gravitymon_ibeacon())
        await scan.parse_gravitymon(MockBLEDevice(), adv)
    mock_post.assert_not_called()
    scan.skip_gravitymon = False


def test_parse_gravitymon_eddystone_skipped_when_flag_set():
    """parse_gravitymon_eddystone returns immediately when skip_gravitymon is True."""
    scan.skip_gravitymon = True
    with patch("scan.requests.post") as mock_post:
        adv = MockAdvertisementData(
            service_uuids=[FEAA_UUID],
            service_data={FEAA_UUID: gravitymon_eddystone()},
        )
        scan.parse_gravitymon_eddystone(MockBLEDevice(), adv)
    mock_post.assert_not_called()
    scan.skip_gravitymon = False


@pytest.mark.asyncio
async def test_parse_pressuremon_skipped_when_flag_set():
    """parse_pressuremon returns immediately when skip_pressuremon is True."""
    scan.skip_pressuremon = True
    with patch("scan.requests.post") as mock_post:
        adv = MockAdvertisementData(manufacturer_data=pressuremon_ibeacon())
        await scan.parse_pressuremon(MockBLEDevice(), adv)
    mock_post.assert_not_called()
    scan.skip_pressuremon = False


@pytest.mark.asyncio
async def test_parse_chamber_skipped_when_flag_set():
    """parse_chamber returns immediately when skip_chamber is True."""
    scan.skip_chamber = True
    with patch("scan.requests.post") as mock_post:
        adv = MockAdvertisementData(manufacturer_data=chamber_ibeacon())
        await scan.parse_chamber(MockBLEDevice(), adv)
    mock_post.assert_not_called()
    scan.skip_chamber = False


# ---------------------------------------------------------------------------
# Exception-path (bad payload → KeyError/ConstError silently caught)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_pressuremon_bad_payload_swallowed():
    """parse_pressuremon does not raise on a truncated payload."""
    adv = MockAdvertisementData(manufacturer_data={0x004C: b"\x00" * 3})
    await scan.parse_pressuremon(MockBLEDevice(), adv)  # must not raise


@pytest.mark.asyncio
async def test_parse_chamber_bad_payload_swallowed():
    """parse_chamber does not raise on a truncated payload."""
    adv = MockAdvertisementData(manufacturer_data={0x004C: b"\x00" * 3})
    await scan.parse_chamber(MockBLEDevice(), adv)  # must not raise


# ---------------------------------------------------------------------------
# device_found — dispatch routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_device_found_routes_eddystone():
    """device_found calls parse_gravitymon_eddystone for eddystone advertisements."""
    device = MockBLEDevice(name="gravitymon")
    adv = MockAdvertisementData(
        service_uuids=["0000feaa-0000-1000-8000-00805f9b34fb"],
        service_data={},
    )
    with patch("scan.parse_gravitymon_eddystone") as mock_eddy:
        await scan.device_found(device, adv)
    mock_eddy.assert_called_once()


@pytest.mark.asyncio
async def test_device_found_routes_non_eddystone():
    """device_found dispatches to all three enabled parsers for non-eddystone adverts."""
    device = MockBLEDevice(name="other")
    adv = MockAdvertisementData()
    with patch("scan.parse_gravitymon", new_callable=AsyncMock) as mg, \
         patch("scan.parse_pressuremon", new_callable=AsyncMock) as mp, \
         patch("scan.parse_chamber", new_callable=AsyncMock) as mc:
        await scan.device_found(device, adv)
    mg.assert_called_once()
    mp.assert_called_once()
    mc.assert_called_once()


# ---------------------------------------------------------------------------
# main() — env config paths
# ---------------------------------------------------------------------------

async def _run_main_once():
    """Drive main() through exactly one scan iteration, then unwind it."""
    with patch("scan.load_device_tokens"), \
         patch("scan.BleakScanner") as mock_scanner_cls:
        mock_scanner_cls.return_value = AsyncMock()

        async def _fake_sleep(_):
            raise KeyboardInterrupt

        with patch("scan.asyncio.sleep", _fake_sleep):
            with pytest.raises(KeyboardInterrupt):
                await scan.main()


@pytest.mark.asyncio
async def test_main_reads_min_interval_from_env():
    """MIN_INTERVAL overrides the default when set."""
    original = scan.MINIMUM_INTERVAL
    try:
        with patch.dict("os.environ", {"MIN_INTERVAL": "30"}):
            await _run_main_once()
        assert scan.MINIMUM_INTERVAL == 30
    finally:
        scan.MINIMUM_INTERVAL = original


@pytest.mark.asyncio
async def test_main_defaults_min_interval_to_15_minutes():
    """With no MIN_INTERVAL set, the throttle defaults to 900s.

    Worth asserting rather than assuming: `MINIMUM_INTERVAL` is 0 at import and only
    `main()` assigns it, so a regression here silently disables every throttle instead
    of failing loudly.
    """
    original = scan.MINIMUM_INTERVAL
    env = {k: v for k, v in os.environ.items() if k != "MIN_INTERVAL"}
    try:
        with patch.dict("os.environ", env, clear=True):
            await _run_main_once()
        assert scan.MINIMUM_INTERVAL == 900
    finally:
        scan.MINIMUM_INTERVAL = original
