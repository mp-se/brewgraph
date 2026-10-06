# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for public ingestion endpoints."""
import json

from core.config import get_settings
from tests.conftest import DEVICE_DEFAULTS, truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

DEVICE_DATA = {
    "name": "Test GravityMon",
    "deviceType": "gravitymon",
    "chipId": "GGGG01",
    **DEVICE_DEFAULTS,
}

GRAVITY_PAYLOAD = {
    "name": "GravityMon Test",
    "id": "GGGG01",
    "interval": 10,
    "temperature": 20.0,
    "temp_units": "C",
    "gravity": 1.050,
    "velocity": 0.1,
    "angle": 34.45,
    "battery": 3.85,
    "rssi": -76,
    "run-time": 6,
    "gravity-unit": "G",
}

PRESSURE_PAYLOAD = {
    "name": "PressureMon Test",
    "id": "PPPP01",
    "interval": 10,
    "temperature": 21.0,
    "temp_units": "C",
    "pressure": 14.7,
    "pressure_units": "psi",
    "battery": 3.5,
    "rssi": -80,
    "run-time": 6,
}


def _create_device(app_client, overrides=None) -> dict:
    data = {**DEVICE_DATA, **(overrides or {})}
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return json.loads(r.text)


def test_init():
    """Reset database state before test scenarios."""
    truncate_database()


def test_gravitymon_ingest(app_client):
    """Test GravityMon ingestion endpoint."""
    test_init()
    device = _create_device(app_client)
    token = device["token"]
    device_id = device["id"]

    payload = {**GRAVITY_PAYLOAD, "token": token}
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200

    r = app_client.get(f"/batches/?deviceId={device_id}", headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)["items"]
    assert len(data) == 1
    batch_id = data[0]["id"]

    r = app_client.get(f"/batches/{batch_id}/gravity", headers=headers)
    readings = json.loads(r.text)["items"]
    assert len(readings) == 1
    assert readings[0]["gravity"] == 1.050
    # Regression: firmware sends the literal wire key "run-time" (hyphenated),
    # not "run_time" — the alias must match or this silently stays NULL.
    assert readings[0]["runTime"] == 6
    # GravityIngestRequest must map real GravityMon firmware's velocity (SG/24h)
    # field or it stays NULL.
    assert readings[0]["velocity"] == 0.1


def test_ispindel_ingest(app_client):
    """Test iSpindel ingestion endpoint."""
    test_init()
    device = _create_device(
        app_client,
        {"name": "Test iSpindel", "deviceType": "ispindel", "chipId": "ISPI01"},
    )
    token = device["token"]
    device_id = device["id"]

    payload = {
        "name": "[SG] Test iSpindel",
        "ID": 13065051,
        "token": token,
        "gravity": 1.05,
        "temperature": 20.0,
        "temp_units": "C",
        "angle": 34.45,
        "battery": 3.85,
        "RSSI": -76,
    }
    r = app_client.post("/ingest/ispindel", json=payload)
    assert r.status_code == 200

    r = app_client.get(f"/batches/?deviceId={device_id}", headers=headers)
    data = json.loads(r.text)["items"]
    assert len(data) == 1


def test_pressuremon_ingest(app_client):
    """Test PressureMon ingestion endpoint."""
    test_init()
    device = _create_device(
        app_client,
        {"name": "Test PressureMon", "deviceType": "pressuremon", "chipId": "PPPP01"},
    )
    token = device["token"]
    device_id = device["id"]

    payload = {**PRESSURE_PAYLOAD, "token": token}
    r = app_client.post("/ingest/pressuremon", json=payload)
    assert r.status_code == 200

    r = app_client.get(f"/batches/?deviceId={device_id}", headers=headers)
    data = json.loads(r.text)["items"]
    assert len(data) == 1
    batch_id = data[0]["id"]

    r = app_client.get(f"/batches/{batch_id}/pressure", headers=headers)
    readings = json.loads(r.text)["items"]
    assert len(readings) == 1
    # PressureIngestRequest must map real firmware's "run-time" (hyphenated) key
    # or it stays NULL.
    assert readings[0]["runTime"] == 6


def test_gravitymon_ingest_stock_firmware_wire_format(app_client):
    """GravityMon's HTTP-push template keys: uppercase "ID"/"RSSI" and "gravity-unit".

    The reading is accepted and its RSSI is stored.
    """
    test_init()
    device = _create_device(app_client, {"chipId": "STOCK1"})
    token = device["token"]
    device_id = device["id"]

    payload = {
        "name": "GravityMon Test",
        "ID": "STOCK1",
        "token": token,
        "interval": 10,
        "temperature": 20.0,
        "temp_units": "C",
        "gravity": 1.050,
        "velocity": 0.1,
        "angle": 34.45,
        "battery": 3.85,
        "RSSI": -76,
        "run-time": 6,
        "gravity-unit": "G",
    }
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200

    r = app_client.get(f"/batches/?deviceId={device_id}", headers=headers)
    data = json.loads(r.text)["items"]
    assert len(data) == 1
    batch_id = data[0]["id"]

    r = app_client.get(f"/batches/{batch_id}/gravity", headers=headers)
    readings = json.loads(r.text)["items"]
    assert len(readings) == 1
    assert readings[0]["rssi"] == -76


def test_pressuremon_ingest_stock_firmware_wire_format(app_client):
    """PressureMon's HTTP-push template keys: "pressure-unit" and "temperature-unit"."""
    test_init()
    device = _create_device(
        app_client,
        {"name": "Test PressureMon Stock", "deviceType": "pressuremon", "chipId": "STOCKP1"},
    )
    token = device["token"]
    device_id = device["id"]

    payload = {
        "name": "PressureMon Test",
        "id": "STOCKP1",
        "token": token,
        "interval": 10,
        "temperature": 21.0,
        "temperature-unit": "C",
        "pressure": 14.7,
        "pressure-unit": "psi",
        "battery": 3.5,
        "rssi": -80,
        "run-time": 6,
    }
    r = app_client.post("/ingest/pressuremon", json=payload)
    assert r.status_code == 200

    r = app_client.get(f"/batches/?deviceId={device_id}", headers=headers)
    data = json.loads(r.text)["items"]
    assert len(data) == 1


def test_device_id_without_token_uses_lan_fallback(app_client):
    """A unique GravityMon lowercase ID supports trusted-LAN ingestion."""
    test_init()
    _create_device(
        app_client,
        {"name": "Device ID Fallback", "deviceType": "gravitymon", "chipId": "GGGG01"},
    )
    payload = {k: v for k, v in GRAVITY_PAYLOAD.items() if k != "token"}
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200


def test_missing_token_returns_401(app_client):
    """A payload without a token is rejected."""
    test_init()
    r = app_client.post(
        "/ingest/gravitymon",
        json={"name": "orphan", "gravity": 1.05, "gravity-unit": "G"},
    )
    assert r.status_code == 401


def test_unregistered_token_returns_401(app_client):
    """A token that does not match any device is rejected."""
    test_init()
    payload = {**GRAVITY_PAYLOAD, "token": "notavalidtoken"}
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 401


def test_auto_creates_batch(app_client):
    """Ingestion auto-creates a fermenting batch when none exists for the device."""
    test_init()
    device = _create_device(
        app_client,
        {"name": "Test AutoBatch", "deviceType": "gravitymon", "chipId": "NOBAT1"},
    )
    token = device["token"]
    device_id = device["id"]

    payload = {**GRAVITY_PAYLOAD, "ID": "NOBAT1", "token": token}
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200

    r = app_client.get(f"/batches/?deviceId={device_id}", headers=headers)
    data = json.loads(r.text)["items"]
    assert len(data) == 1


def test_ingest_to_archived_batch_auto_creates_new_batch(app_client):
    """A device assigned to an archived batch does not keep appending readings
    to it — the assignment is treated as unset, same as a device with no
    batch_id, and a fresh batch is auto-created instead (regression)."""
    test_init()
    device = _create_device(
        app_client,
        {"name": "Test Archived", "deviceType": "gravitymon", "chipId": "ARCH01"},
    )
    token = device["token"]
    device_id = device["id"]

    batch = app_client.post("/batches", json={"name": "To Archive"}, headers=headers).json()
    app_client.patch(f"/devices/{device_id}", json={"batchId": batch["id"]}, headers=headers)
    r = app_client.patch(
        f"/batches/{batch['id']}", json={"status": "archived"}, headers=headers
    )
    assert r.status_code == 200

    payload = {**GRAVITY_PAYLOAD, "token": token}
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200

    r = app_client.get(f"/batches/?deviceId={device_id}", headers=headers)
    data = json.loads(r.text)["items"]
    assert len(data) == 1
    new_batch_id = data[0]["id"]
    assert new_batch_id != batch["id"], "reading must not re-attach to the archived batch"

    # Its readings stay readable, and the ingest never landed there.
    r = app_client.get(f"/batches/{batch['id']}/gravity", headers=headers)
    assert r.status_code == 200
    assert json.loads(r.text)["items"] == []

    r = app_client.get(f"/batches/{new_batch_id}/gravity", headers=headers)
    assert len(json.loads(r.text)["items"]) == 1
