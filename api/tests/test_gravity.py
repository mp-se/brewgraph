# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

# pylint: disable=duplicate-code

"""Tests for gravity reading endpoints."""
import json
from datetime import UTC, datetime, timedelta

from core.config import get_settings
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH_DATA = {
    "name": "Gravity Test Batch",
    "description": "test",
    "brewDate": "2024-01-01",
    "style": "IPA",
    "brewer": "Magnus",
    "status": "fermenting",
    "abv": 5.5,
    "ebc": 20,
    "ibu": 40,
    "fg": 1.010,
    "og": 1.055,
}

GRAVITY_DATA = {
    "temperature": 20.0,
    "gravity": 1.050,
    "velocity": 0.1,
    "angle": 45.0,
    "battery": 3.8,
    "rssi": -75.0,
    "runTime": 0.8,
    "excluded": False,
}


def _create_batch(app_client) -> str:
    r = app_client.post("/batches", json=BATCH_DATA, headers=headers)
    assert r.status_code == 201
    return json.loads(r.text)["id"]


def _create_device(app_client, chip_id: str) -> str:
    data = {
        "name": "Gravity Test Device",
        "chipId": chip_id,
        "deviceType": "gravitymon",
        "mdns": f"gravitymon-{chip_id.lower()}",
        "description": "A test gravity device",
        "chipFamily": "ESP32",
    }
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return json.loads(r.text)["id"]


def test_init():
    """Reset database state before test scenarios."""
    truncate_database()


def test_add(app_client):
    """Test adding a gravity reading."""
    test_init()
    batch_id = _create_batch(app_client)

    data = GRAVITY_DATA.copy()
    data["batchId"] = batch_id

    r = app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[data], headers=headers)
    assert r.status_code == 201
    result = json.loads(r.text)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["gravity"] == 1.050
    assert result[0]["temperature"] == 20.0


def test_list(app_client):
    """Test listing gravity readings."""
    test_init()
    batch_id = _create_batch(app_client)

    for _ in range(3):
        data = GRAVITY_DATA.copy()
        data["batchId"] = batch_id
        app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[data], headers=headers)

    r = app_client.get(f"/batches/{batch_id}/gravity", headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)["items"]
    assert len(data) == 3


def test_excluded_filter(app_client):
    """Test excluded field filtering."""
    test_init()
    batch_id = _create_batch(app_client)

    normal = GRAVITY_DATA.copy()
    normal["batchId"] = batch_id
    excluded = GRAVITY_DATA.copy()
    excluded["batchId"] = batch_id
    excluded["excluded"] = True

    app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[normal], headers=headers)
    app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[excluded], headers=headers)

    r = app_client.get(f"/batches/{batch_id}/gravity", headers=headers)
    data = json.loads(r.text)["items"]
    assert all(not g["excluded"] for g in data)
    assert len(data) == 1

    r = app_client.get(f"/batches/{batch_id}/gravity?includeExcluded=true", headers=headers)
    data = json.loads(r.text)["items"]
    assert len(data) == 2


def test_chart_data(app_client):
    """Test chart data endpoint."""
    test_init()
    batch_id = _create_batch(app_client)

    for g in [1.055, 1.040, 1.025]:
        data = GRAVITY_DATA.copy()
        data["batchId"] = batch_id
        data["gravity"] = g
        app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[data], headers=headers)

    r = app_client.get(f"/batches/{batch_id}/gravity/chart", headers=headers)
    assert r.status_code == 200
    chart = json.loads(r.text)
    assert isinstance(chart, list)
    assert len(chart) == 3
    assert "t" in chart[0]
    assert "g" in chart[0]


def test_bulk_insert(app_client):
    """Test bulk insert of gravity readings."""
    test_init()
    batch_id = _create_batch(app_client)

    readings = []
    for g in [1.060, 1.050, 1.040, 1.030, 1.020]:
        d = GRAVITY_DATA.copy()
        d["batchId"] = batch_id
        d["gravity"] = g
        readings.append(d)

    r = app_client.post(f"/batches/{batch_id}/gravity/bulk", json=readings, headers=headers)
    assert r.status_code == 201
    result = json.loads(r.text)
    assert len(result) == 5

    r = app_client.get(f"/batches/{batch_id}/gravity", headers=headers)
    data = json.loads(r.text)["items"]
    assert len(data) == 5


def test_bulk_insert_preserves_device_id(app_client):
    """Bulk insert (restore's path) keeps a caller-supplied device_id.

    Unlike the single-reading POST, which strips device_id for manual entries,
    the bulk endpoint exists to let BrewGraph-restore relink readings to the
    devices it just recreated — regression test for that behavior.
    """
    test_init()
    batch_id = _create_batch(app_client)
    device_id = _create_device(app_client, "GRAVDEV01")

    data = GRAVITY_DATA.copy()
    data["batchId"] = batch_id
    data["deviceId"] = device_id

    r = app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[data], headers=headers)
    assert r.status_code == 201
    result = json.loads(r.text)
    assert result[0]["deviceId"] == device_id

    r = app_client.get(f"/batches/{batch_id}/gravity", headers=headers)
    items = json.loads(r.text)["items"]
    assert items[0]["deviceId"] == device_id


def test_nullable_fields(app_client):
    """Test nullable gravity fields."""
    test_init()
    batch_id = _create_batch(app_client)

    data = GRAVITY_DATA.copy()
    data["batchId"] = batch_id
    data["temperature"] = None
    data["velocity"] = None
    data["runTime"] = None

    r = app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[data], headers=headers)
    assert r.status_code == 201
    result = json.loads(r.text)[0]
    assert result["temperature"] is None
    assert result["velocity"] is None
    assert result["runTime"] is None
    assert result["gravity"] == 1.050



def test_gravity_cursor_pagination(app_client):
    """GET with a cursor param returns only readings after the boundary row, none repeated."""
    test_init()
    batch_id = _create_batch(app_client)

    readings = []
    for i in range(3):
        d = GRAVITY_DATA.copy()
        d["batchId"] = batch_id
        d["createdAt"] = (datetime.now(UTC) - timedelta(hours=10 - i)).isoformat()
        readings.append(d)
    app_client.post(f"/batches/{batch_id}/gravity/bulk", json=readings, headers=headers)

    r = app_client.get(f"/batches/{batch_id}/gravity?limit=1", headers=headers)
    assert r.status_code == 200
    first_page = json.loads(r.text)
    assert first_page["hasMore"] is True
    first_id = first_page["items"][0]["id"]

    r2 = app_client.get(
        f"/batches/{batch_id}/gravity?cursor={first_page['nextCursor']}", headers=headers
    )
    assert r2.status_code == 200
    second_page = json.loads(r2.text)
    assert len(second_page["items"]) == 2
    assert all(item["id"] != first_id for item in second_page["items"])


def test_gravity_invalid_cursor(app_client):
    """GET /batches/{id}/gravity?cursor=bad returns 400 for an invalid cursor format."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.get(f"/batches/{batch_id}/gravity?cursor=not-a-datetime", headers=headers)
    assert r.status_code == 400


def test_update_gravity_not_found(app_client):
    """PATCH /batches/{id}/gravity/{bad_id} returns 404 when reading does not exist."""
    test_init()
    batch_id = _create_batch(app_client)
    # reading IDs are integers; use a very large value that won't exist
    r = app_client.patch(
        f"/batches/{batch_id}/gravity/999999",
        json={"gravity": 1.050, "excluded": True},
        headers=headers,
    )
    assert r.status_code == 404


def test_update_gravity_success(app_client):
    """PATCH /batches/{id}/gravity/{id} updates a reading and returns 200."""
    test_init()
    batch_id = _create_batch(app_client)
    data = GRAVITY_DATA.copy()
    data["batchId"] = batch_id
    created = app_client.post(
        f"/batches/{batch_id}/gravity/bulk", json=[data], headers=headers
    ).json()[0]
    reading_id = created["id"]

    r = app_client.patch(
        f"/batches/{batch_id}/gravity/{reading_id}",
        json={"gravity": 1.040, "excluded": False},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["gravity"] == 1.040



def test_create_single_gravity_reading(app_client):
    """POST /batches/{id}/gravity creates one reading, nulls deviceId, defaults createdAt."""
    test_init()
    batch_id = _create_batch(app_client)
    data = GRAVITY_DATA.copy()
    data["deviceId"] = "11111111-1111-1111-1111-111111111111"

    r = app_client.post(f"/batches/{batch_id}/gravity", json=data, headers=headers)
    assert r.status_code == 201
    result = r.json()
    assert result["batchId"] == batch_id
    assert result["deviceId"] is None
    assert result["gravity"] == 1.050
    assert result["createdAt"] is not None


def test_create_single_gravity_reading_preserves_created_at(app_client):
    """POST /batches/{id}/gravity keeps an explicit createdAt when provided."""
    test_init()
    batch_id = _create_batch(app_client)
    data = GRAVITY_DATA.copy()
    data["createdAt"] = "2024-06-01T12:00:00+00:00"

    r = app_client.post(f"/batches/{batch_id}/gravity", json=data, headers=headers)
    assert r.status_code == 201
    assert r.json()["createdAt"].startswith("2024-06-01T12:00:00")
