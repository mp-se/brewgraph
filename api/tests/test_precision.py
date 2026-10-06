# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/precision.py — decimal quantisation at the API boundary."""
import json

import pytest

from core.config import get_settings
from oss.precision import DECIMALS, quantise
from tests.conftest import DEVICE_DEFAULTS, truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


# ---------------------------------------------------------------------------
# quantise
# ---------------------------------------------------------------------------

class TestQuantise:
    """quantise() rounds each quantity to its documented decimal count."""

    def test_temperature_two_decimals(self):
        """Temperature quantises to 2 decimals."""
        assert quantise(18.4712, "temperature") == 18.47

    def test_volume_three_decimals(self):
        """Volume quantises to 3 decimals (one millilitre)."""
        assert quantise(0.3300000001, "volume") == 0.33

    def test_mass_one_decimal(self):
        """Mass quantises to 1 decimal."""
        assert quantise(123.456, "mass") == 123.5

    def test_pressure_two_decimals(self):
        """Pressure quantises to 2 decimals."""
        assert quantise(101.325, "pressure") == 101.33

    def test_gravity_four_decimals(self):
        """Gravity quantises to 4 decimals (one gravity point)."""
        assert quantise(1.050126, "gravity") == 1.0501

    def test_battery_two_decimals(self):
        """Battery voltage quantises to 2 decimals."""
        assert quantise(3.847, "battery") == 3.85

    def test_signal_zero_decimals(self):
        """Signal strength quantises to a whole number."""
        assert quantise(-76.6, "signal") == -77.0

    def test_percent_one_decimal(self):
        """Percentages (ABV, SoC) quantise to 1 decimal."""
        assert quantise(5.67, "percent") == 5.7

    def test_none_in_none_out(self):
        """An absent measurement stays absent for every quantity."""
        for quantity in DECIMALS:
            assert quantise(None, quantity) is None

    def test_already_correct_precision_is_unchanged(self):
        """A value already at the target precision round-trips unchanged."""
        assert quantise(18.47, "temperature") == 18.47
        assert quantise(0.33, "volume") == 0.33
        assert quantise(1.0501, "gravity") == 1.0501

    def test_does_not_reject_excess_precision(self):
        """More digits than we keep is not an error -- it is just rounded."""
        assert quantise(0.3300000001, "volume") == pytest.approx(0.33)


# ---------------------------------------------------------------------------
# Boundary: ingest (device payload)
# ---------------------------------------------------------------------------

def _create_device(app_client) -> dict:
    data = {
        "name": "Precision Test GravityMon",
        "deviceType": "gravitymon",
        "chipId": "PREC01",
        **DEVICE_DEFAULTS,
    }
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return json.loads(r.text)


def test_ingest_quantises_fahrenheit_to_celsius_conversion(app_client):
    """A device sending Fahrenheit gets a temperature quantised to 2 decimals in C."""
    truncate_database()
    device = _create_device(app_client)
    payload = {
        "name": "GravityMon",
        "id": "PREC01",
        "interval": 10,
        "temperature": 68.111,
        "temp_units": "F",
        "gravity": 1.050,
        "gravity-unit": "G",
        "battery": 3.85123,
        "token": device["token"],
    }
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200

    readings = app_client.get(
        f"/batches/?deviceId={device['id']}", headers=headers
    )
    batch_id = readings.json()["items"][0]["id"]
    gravity = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    reading = gravity[0]
    # (68.111 - 32) * 5 / 9 = 20.0616... -> quantised to 2 decimals
    assert reading["temperature"] == round((68.111 - 32) * 5 / 9, 2)
    assert reading["battery"] == 3.85


def test_ingest_quantises_plato_to_sg_conversion(app_client):
    """A device sending Plato gets a gravity quantised to 4 decimals in SG."""
    truncate_database()
    device = _create_device(app_client)
    payload = {
        "name": "GravityMon",
        "id": "PREC01",
        "interval": 10,
        "gravity": 12.345,
        "gravity-unit": "P",
        "token": device["token"],
    }
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers)
    batch_id = batches.json()["items"][0]["id"]
    gravity = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    plato = 12.345
    expected = round(1 + (plato / (258.6 - ((plato / 258.2) * 227.1))), 4)
    assert gravity[0]["gravity"] == expected


# ---------------------------------------------------------------------------
# Boundary: write schema (API client, not a device)
# ---------------------------------------------------------------------------

def test_write_schema_quantises_gravity_bulk_write(app_client):
    """A REST client writing a gravity reading directly also gets quantised."""
    truncate_database()
    r = app_client.post(
        "/batches",
        json={
            "name": "Precision Batch",
            "description": "test",
            "brewDate": "2024-01-01",
            "style": "IPA",
            "brewer": "Magnus",
            "status": "fermenting",
        },
        headers=headers,
    )
    batch_id = r.json()["id"]

    r = app_client.post(
        f"/batches/{batch_id}/gravity/bulk",
        json=[{"gravity": 1.050126789, "temperature": 18.4712, "createdAt": "2024-01-01T12:00:00"}],
        headers=headers,
    )
    assert r.status_code == 201

    gravity = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    assert gravity[0]["gravity"] == 1.0501
    assert gravity[0]["temperature"] == 18.47


def test_write_schema_null_stays_null(app_client):
    """An absent temperature is not turned into a 0.0 by quantisation."""
    truncate_database()
    r = app_client.post(
        "/batches",
        json={
            "name": "Precision Batch",
            "description": "test",
            "brewDate": "2024-01-01",
            "style": "IPA",
            "brewer": "Magnus",
            "status": "fermenting",
        },
        headers=headers,
    )
    batch_id = r.json()["id"]

    r = app_client.post(
        f"/batches/{batch_id}/gravity/bulk",
        json=[{"gravity": 1.050, "createdAt": "2024-01-01T12:00:00"}],
        headers=headers,
    )
    assert r.status_code == 201

    gravity = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    assert gravity[0]["temperature"] is None
