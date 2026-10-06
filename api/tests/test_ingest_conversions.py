# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for ingestion unit conversions and error paths."""
from core.config import get_settings
from tests.conftest import DEVICE_DEFAULTS, truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

DEVICE_BASE = {
    "name": "Conv Device",
    "deviceType": "gravitymon",
    "chipId": "CONV01",
    **DEVICE_DEFAULTS,
}

GRAVITY_BASE = {
    "name": "Conv Test",
    "id": "CONV01",
    "interval": 10,
    "temperature": 68.0,
    "temp_units": "F",
    "gravity": 1.050,
    "angle": 34.0,
    "battery": 3.85,
    "rssi": -76,
    "gravity-unit": "G",
}


def _make_device(app_client, overrides=None):
    data = {**DEVICE_BASE, **(overrides or {})}
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


def test_init():
    """Reset database state before suite."""
    truncate_database()


def test_temperature_fahrenheit_converted_to_celsius(app_client):
    """Fahrenheit temperature is stored as Celsius."""
    test_init()
    device = _make_device(app_client, {"chipId": "FAHR01", "name": "FahrDev"})
    payload = {**GRAVITY_BASE, "id": "FAHR01", "token": device["token"],
               "temperature": 68.0, "temp_units": "F"}
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    assert abs(readings[0]["temperature"] - 20.0) < 0.05


def test_invalid_temperature_sentinel_stored_as_none(app_client):
    """Gravity readings with temperature below -270 are stored as null."""
    test_init()
    device = _make_device(app_client, {"chipId": "SENT01", "name": "SentDev"})
    payload = {**GRAVITY_BASE, "id": "SENT01", "token": device["token"],
               "temperature": -300.0, "temp_units": "C"}
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    assert readings[0]["temperature"] is None


def test_gravity_plato_converted_to_sg(app_client):
    """Gravity in Plato is converted and stored as SG."""
    test_init()
    device = _make_device(app_client, {"chipId": "PLAT01", "name": "PlatoDev"})
    payload = {
        **GRAVITY_BASE, "id": "PLAT01", "token": device["token"],
        "gravity": 12.0, "gravity-unit": "P", "temp_units": "C", "temperature": 20.0,
    }
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    sg = readings[0]["gravity"]
    assert 1.040 < sg < 1.060


def test_pressure_psi_converted_to_kpa(app_client):
    """PSI pressure is converted and stored in kPa."""
    test_init()
    device = _make_device(app_client, {
        "chipId": "PPSI01", "name": "PSIDev", "deviceType": "pressuremon",
    })
    payload = {
        "name": "PSIDev", "id": "PPSI01", "token": device["token"],
        "interval": 10, "temperature": 20.0, "temp_units": "C",
        "pressure": 14.504, "pressure_units": "psi",
        "battery": 3.5, "rssi": -80, "run-time": 0,
    }
    r = app_client.post("/ingest/pressuremon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/pressure", headers=headers).json()["items"]
    assert readings[0]["pressure"] > 90  # ~99.97 kPa


def test_pressure_bar_converted_to_kpa(app_client):
    """BAR pressure is converted and stored in kPa."""
    test_init()
    device = _make_device(app_client, {
        "chipId": "PBAR01", "name": "BARDev", "deviceType": "pressuremon",
    })
    payload = {
        "name": "BARDev", "id": "PBAR01", "token": device["token"],
        "interval": 10, "temperature": 20.0, "temp_units": "C",
        "pressure": 1.0, "pressure_units": "bar",
        "battery": 3.5, "rssi": -80, "run-time": 0,
    }
    r = app_client.post("/ingest/pressuremon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/pressure", headers=headers).json()["items"]
    assert readings[0]["pressure"] == 100.0


def test_pressure_temperature_fahrenheit_converted(app_client):
    """PressureMon Fahrenheit temperature is stored as Celsius."""
    test_init()
    device = _make_device(app_client, {
        "chipId": "PTMP01", "name": "PTmpDev", "deviceType": "pressuremon",
    })
    payload = {
        "name": "PTmpDev", "id": "PTMP01", "token": device["token"],
        "interval": 10, "temperature": 32.0, "temp_units": "F",
        "pressure": 0.0, "pressure_units": "kPa",
        "battery": 3.5, "rssi": -80,
    }
    r = app_client.post("/ingest/pressuremon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/pressure", headers=headers).json()["items"]
    assert abs(readings[0]["temperature"] - 0.0) < 0.05


def test_ingest_reuses_existing_fermenting_batch(app_client):
    """Second ingestion reuses the existing fermenting batch, not creating a new one."""
    test_init()
    device = _make_device(app_client, {"chipId": "REUS01", "name": "ReusDev"})
    payload = {**GRAVITY_BASE, "id": "REUS01", "token": device["token"], "temp_units": "C"}
    app_client.post("/ingest/gravitymon", json=payload)
    app_client.post("/ingest/gravitymon", json=payload)

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    assert len(batches) == 1

    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    assert len(readings) == 2


def test_ispindel_rssi_uppercase_field(app_client):
    """iSpindel payloads use the native uppercase ``RSSI`` field."""
    test_init()
    device = _make_device(app_client, {
        "chipId": "ISPI02", "name": "iSpindel2", "deviceType": "ispindel",
    })
    payload = {
        "name": "[SG] iSpindel2", "ID": 13065052, "token": device["token"],
        "interval": 10, "temperature": 20.0, "temp_units": "C",
        "gravity": 1.055, "angle": 30.0, "battery": 4.0, "RSSI": -65,
    }
    r = app_client.post("/ingest/ispindel", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    assert readings[0]["rssi"] == -65.0


def _ispindel_reading(app_client, chip_id, **overrides):
    """POST an iSpindel payload for a fresh device; return (response, stored gravity readings)."""
    test_init()
    device = _make_device(app_client, {
        "chipId": chip_id, "name": f"iSp{chip_id}", "deviceType": "ispindel",
    })
    payload = {
        "name": "[SG] iSpindel", "ID": 13065052, "token": device["token"],
        "interval": 10, "temperature": 68.0,
        "gravity": 1.055, "angle": 30.0, "battery": 4.0, "RSSI": -65,
        **overrides,
    }
    r = app_client.post("/ingest/ispindel", json=payload)
    if r.status_code != 200:
        return r, []
    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    return r, app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]


def test_ispindel_hyphenated_temp_unit_alias_is_ignored(app_client):
    """``temp-unit`` is not a wire spelling: it is ignored and the reading stays Celsius."""
    r, readings = _ispindel_reading(app_client, "ISPI03", **{"temp-unit": "F"})
    assert r.status_code == 200
    assert readings[0]["temperature"] == 68.0


def test_ispindel_unknown_temp_units_value_rejected(app_client):
    """``temp_units`` is exactly ``C`` or ``F``; any other value is a 422."""
    r, _ = _ispindel_reading(app_client, "ISPI04", temp_units="K")
    assert r.status_code == 422
