# BrewGraph
# Copyright (c) 2024-2026 Magnus
# GPL-3 / Commercial dual license

"""Integration test client — BLE frame → ingest API → DB round-trip.

Requires a running BrewGraph API (make run from api/).

Run with:
    pytest ble/tests/test_client.py -m integration -v

Environment:
    API_HOST   host:port of the running API  (default: localhost:8080)
    API_KEY    API key                        (default: devkey)
"""

import asyncio
import os

import pytest
import requests

import scan
from tests.conftest import MockAdvertisementData, MockBLEDevice
from tests.packets import (FEAA_UUID, TEST_CHIP_ID, gravitymon_eddystone,
                           gravitymon_ibeacon, pressuremon_ibeacon)

pytestmark = pytest.mark.integration

API_BASE = "http://" + os.getenv("API_HOST", "localhost:8080")
API_KEY = os.getenv("API_KEY", "devkey")
AUTH = {"Authorization": f"Bearer {API_KEY}"}
CHIP_HEX = hex(TEST_CHIP_ID)[2:]  # "dead"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_gravity_device(chip_id_hex: str) -> dict:
    """Register a gravitymon device via the API and return its JSON response."""
    resp = requests.post(
        f"{API_BASE}/api/devices/",
        json={
            "name": f"ble-test-{chip_id_hex}",
            "deviceType": "gravitymon",
            "chipId": chip_id_hex,
        },
        headers=AUTH,
        timeout=5,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _register_pressure_device(chip_id_hex: str) -> dict:
    """Register a pressuremon device via the API and return its JSON response."""
    resp = requests.post(
        f"{API_BASE}/api/devices/",
        json={
            "name": f"ble-test-p-{chip_id_hex}",
            "deviceType": "pressuremon",
            "chipId": chip_id_hex,
        },
        headers=AUTH,
        timeout=5,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _delete_device(device_id: str) -> None:
    """Delete a device from the API (test cleanup)."""
    requests.delete(f"{API_BASE}/api/devices/{device_id}", headers=AUTH, timeout=5)


def _get_gravity_readings(batch_id: str) -> list:
    """Fetch all gravity readings for a batch from the API."""
    resp = requests.get(f"{API_BASE}/api/batches/{batch_id}/gravity", headers=AUTH, timeout=5)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _get_pressure_readings(batch_id: str) -> list:
    """Fetch all pressure readings for a batch from the API."""
    resp = requests.get(f"{API_BASE}/api/batches/{batch_id}/pressure", headers=AUTH, timeout=5)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _get_batches_for_device(device_id: str) -> list:
    """Fetch all batches associated with a device from the API."""
    resp = requests.get(f"{API_BASE}/api/batches/?deviceId={device_id}", headers=AUTH, timeout=5)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _run_parser(coro):
    """Run an async parser coroutine synchronously via the event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def gravity_device():
    """Register a gravity device, yield it, then clean up."""
    device = _register_gravity_device(CHIP_HEX)
    scan.gravitymon_device_tokens[CHIP_HEX] = device["token"]
    yield device
    scan.gravitymon_device_tokens.pop(CHIP_HEX, None)
    _delete_device(device["id"])


@pytest.fixture()
def pressure_device():
    """Register a pressure device with a distinct chip ID, yield (device, chip_hex), clean up."""
    chip = hex(TEST_CHIP_ID + 1)[2:]  # different chip_id to avoid collision
    device = _register_pressure_device(chip)
    scan.pressuremon_device_tokens[chip] = device["token"]
    yield device, chip
    scan.pressuremon_device_tokens.pop(chip, None)
    _delete_device(device["id"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGravitymonIBeaconCycle:
    """Round-trip tests: GravityMon iBeacon → ingest endpoint → DB."""

    def test_reading_written_to_api(self, gravity_device):  # pylint: disable=redefined-outer-name
        """GravityMon iBeacon packet → ingest endpoint → GravityReading in DB."""
        adv = MockAdvertisementData(
            manufacturer_data=gravitymon_ibeacon(gravity=1.048, temp_c=20.0)
        )
        scan.skip_push = False
        _run_parser(scan.parse_gravitymon(MockBLEDevice(), adv))
        scan.skip_push = True

        batches = _get_batches_for_device(gravity_device["id"])
        assert len(batches) >= 1, "Expected auto-created batch"

        batch_id = batches[0]["id"]
        readings = _get_gravity_readings(batch_id)
        assert len(readings) >= 1

        latest = readings[-1]
        assert latest["gravity"] == pytest.approx(1.048, abs=0.0001)
        assert latest["temperature"] == pytest.approx(20.0, abs=0.1)

    def test_multiple_readings_accumulate(self, gravity_device):  # pylint: disable=redefined-outer-name
        """Each BLE advertisement produces a distinct reading row."""
        for gravity in [1.060, 1.050, 1.040]:
            adv = MockAdvertisementData(
                manufacturer_data=gravitymon_ibeacon(gravity=gravity)
            )
            scan.skip_push = False
            _run_parser(scan.parse_gravitymon(MockBLEDevice(), adv))
            scan.skip_push = True

        batches = _get_batches_for_device(gravity_device["id"])
        readings = _get_gravity_readings(batches[0]["id"])
        assert len(readings) >= 3


class TestGravitymonEddystoneCycle:  # pylint: disable=too-few-public-methods
    """Round-trip tests: GravityMon Eddystone → ingest endpoint → DB."""

    def test_reading_written_to_api(self, gravity_device):  # pylint: disable=redefined-outer-name
        """GravityMon Eddystone packet → ingest endpoint → GravityReading in DB."""
        svc_data = gravitymon_eddystone(gravity=1.055, temp_c=18.5)
        adv = MockAdvertisementData(
            service_data=svc_data,
            service_uuids=[FEAA_UUID],
        )
        scan.skip_push = False
        scan.parse_gravitymon_eddystone(MockBLEDevice(name="gravitymon"), adv)
        scan.skip_push = True

        batches = _get_batches_for_device(gravity_device["id"])
        assert len(batches) >= 1

        readings = _get_gravity_readings(batches[0]["id"])
        assert len(readings) >= 1
        assert readings[-1]["gravity"] == pytest.approx(1.055, abs=0.0001)


class TestPressuremonIBeaconCycle:  # pylint: disable=too-few-public-methods
    """Round-trip tests: PressureMon iBeacon → ingest endpoint → DB."""

    def test_reading_written_to_api(self, pressure_device):  # pylint: disable=redefined-outer-name
        """PressureMon iBeacon packet → ingest endpoint → PressureReading in DB."""
        device, _ = pressure_device
        adv = MockAdvertisementData(
            manufacturer_data=pressuremon_ibeacon(
                chip_id=TEST_CHIP_ID + 1, pressure=10.5, temp_c=4.0
            )
        )
        scan.skip_push = False
        _run_parser(scan.parse_pressuremon(MockBLEDevice(), adv))
        scan.skip_push = True

        batches = _get_batches_for_device(device["id"])
        assert len(batches) >= 1

        readings = _get_pressure_readings(batches[0]["id"])
        assert len(readings) >= 1
        latest = readings[-1]
        # API stores in kPa; pressuremon sends PSI → ingestion converts (PSI * 6.89476)
        assert latest["pressure"] == pytest.approx(10.5 * 6.89476, abs=0.1)


class TestMissingIdentityRejected:  # pylint: disable=too-few-public-methods
    """Verify that ingest rejects payloads with neither a token nor uppercase ID."""

    def test_missing_identity_returns_401(self):
        """A payload with no supported device identity is rejected."""
        resp = requests.post(
            f"{API_BASE}/api/ingest/gravitymon",
            json={"gravity": 1.048, "temperature": 20.0},
            timeout=5,
        )
        assert resp.status_code == 401
