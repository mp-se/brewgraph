# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for pressure reading endpoints."""
from datetime import datetime, timezone

from core.config import get_settings
from core.db import create_session
from oss.services.pressure import PressureReading
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH_DATA = {
    "name": "Pressure Test Batch",
    "status": "fermenting",
    "og": 1.055,
    "fg": 1.010,
}

PRESSURE_READING = {
    "pressure": 101.325,
    "temperature": 20.0,
    "battery": 3.8,
    "rssi": -70.0,
    "excluded": False,
    "createdAt": "2024-01-01T12:00:00",
}


def test_init():
    """Reset database state before suite."""
    truncate_database()


def _create_batch(app_client):
    r = app_client.post("/batches", json=BATCH_DATA, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _bulk_insert(app_client, batch_id, readings):
    payload = [{**r, "batchId": batch_id} for r in readings]
    r = app_client.post(f"/batches/{batch_id}/pressure/bulk", json=payload, headers=headers)
    assert r.status_code == 201
    return r.json()


def test_bulk_insert_pressure(app_client):
    """POST /pressure/bulk inserts multiple readings and returns them."""
    test_init()
    batch_id = _create_batch(app_client)

    readings = [
        {**PRESSURE_READING, "pressure": float(100 + i), "createdAt": f"2024-01-01T0{i}:00:00"}
        for i in range(3)
    ]
    result = _bulk_insert(app_client, batch_id, readings)
    assert len(result) == 3
    pressures = {r["pressure"] for r in result}
    assert pressures == {100.0, 101.0, 102.0}


def test_list_pressure_empty(app_client):
    """GET pressure for a batch with no readings returns empty list."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.get(f"/batches/{batch_id}/pressure", headers=headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_list_pressure_returns_inserted(app_client):
    """Readings inserted via bulk are retrievable via list endpoint."""
    test_init()
    batch_id = _create_batch(app_client)
    _bulk_insert(app_client, batch_id, [
        PRESSURE_READING,
        {**PRESSURE_READING, "createdAt": "2024-01-01T13:00:00"},
    ])

    r = app_client.get(f"/batches/{batch_id}/pressure", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2


def test_excluded_filter(app_client):
    """Excluded readings are hidden by default, shown with includeExcluded=true."""
    test_init()
    batch_id = _create_batch(app_client)
    _bulk_insert(app_client, batch_id, [
        {**PRESSURE_READING, "excluded": False},
        {**PRESSURE_READING, "excluded": True, "createdAt": "2024-01-01T13:00:00"},
    ])

    visible = app_client.get(f"/batches/{batch_id}/pressure", headers=headers).json()["items"]
    assert len(visible) == 1
    assert visible[0]["excluded"] is False

    all_readings = app_client.get(
        f"/batches/{batch_id}/pressure?includeExcluded=true", headers=headers
    ).json()["items"]
    assert len(all_readings) == 2


def test_pressure_chart_data(app_client):
    """GET /pressure/chart returns compact chart points for each non-excluded reading."""
    test_init()
    batch_id = _create_batch(app_client)
    readings = [
        {**PRESSURE_READING, "pressure": float(100 + i), "createdAt": f"2024-01-01T0{i}:00:00"}
        for i in range(3)
    ]
    _bulk_insert(app_client, batch_id, readings)

    r = app_client.get(f"/batches/{batch_id}/pressure/chart", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    for point in data:
        assert "t" in point
        assert "p" in point


def test_pressure_chart_excludes_excluded_readings(app_client):
    """Chart endpoint omits excluded readings."""
    test_init()
    batch_id = _create_batch(app_client)
    _bulk_insert(app_client, batch_id, [
        {**PRESSURE_READING, "excluded": False},
        {**PRESSURE_READING, "excluded": True, "createdAt": "2024-01-01T13:00:00"},
    ])

    data = app_client.get(f"/batches/{batch_id}/pressure/chart", headers=headers).json()
    assert len(data) == 1


def test_bulk_insert_sets_created_at_when_missing(app_client):
    """Bulk insert assigns created_at when the field is omitted."""
    test_init()
    batch_id = _create_batch(app_client)
    payload = [{"batchId": batch_id, "pressure": 99.0, "excluded": False}]
    r = app_client.post(f"/batches/{batch_id}/pressure/bulk", json=payload, headers=headers)
    assert r.status_code == 201
    assert r.json()[0]["createdAt"] is not None



def test_pressure_invalid_cursor(app_client):
    """GET /batches/{id}/pressure?cursor=bad returns 400 for an invalid cursor."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.get(f"/batches/{batch_id}/pressure?cursor=not-a-datetime", headers=headers)
    assert r.status_code == 400


def test_update_pressure_not_found(app_client):
    """PATCH /batches/{id}/pressure/{bad_id} returns 404 when reading does not exist."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.patch(
        f"/batches/{batch_id}/pressure/999999",
        json={"pressure": 101.0, "excluded": True},
        headers=headers,
    )
    assert r.status_code == 404


def test_update_pressure_success(app_client):
    """PATCH /batches/{id}/pressure/{id} updates a reading and returns 200."""
    test_init()
    batch_id = _create_batch(app_client)
    _bulk_insert(app_client, batch_id, [PRESSURE_READING])
    list_r = app_client.get(f"/batches/{batch_id}/pressure", headers=headers)
    reading_id = list_r.json()["items"][0]["id"]

    r = app_client.patch(
        f"/batches/{batch_id}/pressure/{reading_id}",
        json={"pressure": 115.0, "excluded": False},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["pressure"] == 115.0


def test_update_soft_deleted_pressure_reading_returns_404(app_client):
    """PATCH on a soft-deleted reading returns 404, mirroring update()'s get_active() gate.

    update_for_owner() is not reachable by any soft-delete path today (there is no
    DELETE endpoint for a single reading), so the row is soft-deleted directly via
    the session to prove the service-level guard itself, independent of whether an
    API path to trigger it exists yet.
    """
    test_init()
    batch_id = _create_batch(app_client)
    _bulk_insert(app_client, batch_id, [PRESSURE_READING])
    list_r = app_client.get(f"/batches/{batch_id}/pressure", headers=headers)
    reading_id = list_r.json()["items"][0]["id"]

    session = create_session()
    row = session.get(PressureReading, reading_id)
    row.deleted_at = datetime.now(timezone.utc)
    session.commit()
    session.close()

    r = app_client.patch(
        f"/batches/{batch_id}/pressure/{reading_id}",
        json={"pressure": 115.0},
        headers=headers,
    )
    assert r.status_code == 404


def test_create_single_pressure_reading(app_client):
    """POST /batches/{id}/pressure creates one reading, nulls deviceId, defaults createdAt."""
    test_init()
    batch_id = _create_batch(app_client)
    data = {**PRESSURE_READING}
    data.pop("createdAt")
    data["deviceId"] = "11111111-1111-1111-1111-111111111111"

    r = app_client.post(f"/batches/{batch_id}/pressure", json=data, headers=headers)
    assert r.status_code == 201
    result = r.json()
    assert result["batchId"] == batch_id
    assert result["deviceId"] is None
    # pressure is quantised to 2 decimals at the API boundary (see oss/precision.py);
    # 101.325 in, 101.33 out is the deliberate loss of the third decimal, not a bug.
    assert result["pressure"] == 101.33
    assert result["createdAt"] is not None


def test_create_single_pressure_reading_preserves_created_at(app_client):
    """POST /batches/{id}/pressure keeps an explicit createdAt when provided."""
    test_init()
    batch_id = _create_batch(app_client)
    data = {**PRESSURE_READING, "createdAt": "2024-06-01T12:00:00+00:00"}

    r = app_client.post(f"/batches/{batch_id}/pressure", json=data, headers=headers)
    assert r.status_code == 201
    assert r.json()["createdAt"].startswith("2024-06-01T12:00:00")
