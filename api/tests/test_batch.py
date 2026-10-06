# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

# pylint: disable=duplicate-code

"""Tests for batch endpoints."""
import json

from core.config import get_settings
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH_DATA = {
    "name": "Test Batch",
    "description": "A test batch",
    "brewDate": "2024-01-01",
    "style": "IPA",
    "brewer": "Magnus",
    "brewfatherBatchId": "bf123",
    "acceptIngest": True,
    "abv": 5.5,
    "ebc": 20,
    "ibu": 40,
    "fg": 1.010,
    "og": 1.055,
}


def test_init():
    """Reset database state before test scenarios."""
    truncate_database()


def test_add(app_client):
    """Test creating a batch."""
    test_init()

    r = app_client.post("/batches", json=BATCH_DATA, headers=headers)
    assert r.status_code == 201
    data = json.loads(r.text)
    assert "id" in data
    assert data["name"] == BATCH_DATA["name"]
    assert data["acceptIngest"] is True
    assert data["abv"] == 5.5

    batch_id = data["id"]

    # Read back
    r2 = app_client.get(f"/batches/{batch_id}", headers=headers)
    assert r2.status_code == 200
    data2 = json.loads(r2.text)
    assert data2["name"] == BATCH_DATA["name"]

    # Invalid path
    r3 = app_client.get("/batches/hello", headers=headers)
    assert r3.status_code == 422


def test_list(app_client):
    """Test listing batches."""
    test_init()

    r = app_client.post("/batches", json=BATCH_DATA, headers=headers)
    assert r.status_code == 201
    batch_id = json.loads(r.text)["id"]

    r = app_client.get("/batches", headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)["items"]
    assert len(data) >= 1
    assert batch_id in [b["id"] for b in data]


def test_update(app_client):
    """Test updating a batch."""
    test_init()

    r0 = app_client.post("/batches", json=BATCH_DATA, headers=headers)
    assert r0.status_code == 201
    batch_id = json.loads(r0.text)["id"]

    update = BATCH_DATA.copy()
    update["name"] = "Updated Batch"
    update["acceptIngest"] = False

    r = app_client.patch(f"/batches/{batch_id}", json=update, headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert data["name"] == "Updated Batch"
    assert data["acceptIngest"] is False

    # Missing entity
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = app_client.patch(f"/batches/{fake_id}", json=update, headers=headers)
    assert r.status_code == 404


def test_delete(app_client):
    """Test soft-deleting a batch."""
    test_init()

    r = app_client.post("/batches", json=BATCH_DATA, headers=headers)
    assert r.status_code == 201
    batch_id = json.loads(r.text)["id"]

    r = app_client.delete(f"/batches/{batch_id}", headers=headers)
    assert r.status_code == 204

    # Should be gone from list
    r = app_client.get("/batches", headers=headers)
    data = json.loads(r.text)["items"]
    ids = [b["id"] for b in data]
    assert batch_id not in ids

    # GET should 404
    r = app_client.get(f"/batches/{batch_id}", headers=headers)
    assert r.status_code == 404


def test_accept_ingest_toggle(app_client):
    """Test toggling accept_ingest on a batch."""
    test_init()

    r = app_client.post("/batches", json=BATCH_DATA, headers=headers)
    assert r.status_code == 201
    batch_id = json.loads(r.text)["id"]

    update = BATCH_DATA.copy()
    update["acceptIngest"] = False
    r = app_client.patch(f"/batches/{batch_id}", json=update, headers=headers)
    assert r.status_code == 200
    assert json.loads(r.text)["acceptIngest"] is False

    update["acceptIngest"] = True
    r = app_client.patch(f"/batches/{batch_id}", json=update, headers=headers)
    assert r.status_code == 200
    assert json.loads(r.text)["acceptIngest"] is True


def test_status_accepts_valid_enum_values(app_client):
    """Batch status accepts each real BatchStatus value and round-trips it."""
    test_init()

    for status in ("fermenting", "packaged", "archived"):
        payload = BATCH_DATA.copy()
        payload["status"] = status
        r = app_client.post("/batches", json=payload, headers=headers)
        assert r.status_code == 201
        assert r.json()["status"] == status


def test_status_rejects_invalid_value(app_client):
    """Batch status rejects a value outside the BatchStatus enum."""
    test_init()

    payload = BATCH_DATA.copy()
    payload["status"] = "kegged"
    r = app_client.post("/batches", json=payload, headers=headers)
    assert r.status_code == 422


def test_temp_device_id_round_trips(app_client):
    """temp_device_id survives create, read-back and update, like gravity/pressure."""
    test_init()

    device_payload = {
        "name": "Test Temp Device",
        "chipId": "TEMPDEV01",
        "deviceType": "gravitymon",
        "mdns": "gravitymon-tempdev01",
        "description": "A test temp device",
        "chipFamily": "ESP32",
    }
    rd = app_client.post("/devices", json=device_payload, headers=headers)
    assert rd.status_code == 201
    device_id = json.loads(rd.text)["id"]

    payload = BATCH_DATA.copy()
    payload["tempDeviceId"] = device_id
    r = app_client.post("/batches", json=payload, headers=headers)
    assert r.status_code == 201
    data = json.loads(r.text)
    assert data["tempDeviceId"] == device_id
    batch_id = data["id"]

    r2 = app_client.get(f"/batches/{batch_id}", headers=headers)
    assert r2.status_code == 200
    assert json.loads(r2.text)["tempDeviceId"] == device_id

    r3 = app_client.patch(
        f"/batches/{batch_id}", json={"tempDeviceId": None}, headers=headers
    )
    assert r3.status_code == 200
    assert json.loads(r3.text)["tempDeviceId"] is None
