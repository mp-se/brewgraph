# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

# pylint: disable=redefined-outer-name
"""Tests for batch temperature endpoints (P3)."""
import uuid

from core.config import get_settings
from tests.conftest import app_client, truncate_database  # noqa: F401  # pylint: disable=unused-import


HDR = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

def _create_batch(client, name="Temp Test Batch") -> dict:
    r = client.post("/batches", json={"name": name}, headers=HDR)
    assert r.status_code == 201
    return r.json()


def test_post_batch_temp_manual(app_client):
    """POST /batches/{id}/temp returns 201 and creates a temperature reading."""
    truncate_database()
    batch = _create_batch(app_client)
    r = app_client.post(f"/batches/{batch['id']}/temp", json={"temperature": 18.5}, headers=HDR)
    assert r.status_code == 201
    data = r.json()
    assert data["temperature"] == 18.5
    assert data["batchId"] == batch["id"]


def test_get_batch_temp_chart(app_client):
    """GET /batches/{id}/temp/chart returns list of temperature chart points."""
    truncate_database()
    batch = _create_batch(app_client)
    # Add two readings
    app_client.post(f"/batches/{batch['id']}/temp", json={"temperature": 18.5}, headers=HDR)
    app_client.post(f"/batches/{batch['id']}/temp", json={"temperature": 19.0}, headers=HDR)
    r = app_client.get(f"/batches/{batch['id']}/temp/chart", headers=HDR)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert all("t" in pt and "temp" in pt for pt in data)


def test_batch_temp_404_for_missing_batch(app_client):
    """POST /batches/{id}/temp returns 404 when batch does not exist."""
    truncate_database()
    r = app_client.post(f"/batches/{uuid.uuid4()}/temp", json={"temperature": 20.0}, headers=HDR)
    assert r.status_code == 404


def test_batch_temp_404_for_archived_batch(app_client):
    """POST /batches/{id}/temp returns 404 once the batch is archived.

    §15: archived is a distinct state from soft-deleted, but both reject new
    manual/bulk writes the same way — an archived batch is done fermenting
    and packaged away.
    """
    truncate_database()
    batch = _create_batch(app_client)
    r = app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=HDR)
    assert r.status_code == 200

    r = app_client.post(f"/batches/{batch['id']}/temp", json={"temperature": 20.0}, headers=HDR)
    assert r.status_code == 404


def test_batch_temp_list_readable_for_archived_batch(app_client):
    """GET /batches/{id}/temp still lists an archived batch's readings: archived keeps its
    history (and a backup exports it); only writes are rejected."""
    truncate_database()
    batch = _create_batch(app_client)
    app_client.post(f"/batches/{batch['id']}/temp", json={"temperature": 18.5}, headers=HDR)
    app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=HDR)

    r = app_client.get(f"/batches/{batch['id']}/temp", headers=HDR)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


def test_batch_temp_chart_readable_for_archived_batch(app_client):
    """GET /batches/{id}/temp/chart works once the batch is archived."""
    truncate_database()
    batch = _create_batch(app_client)
    app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=HDR)

    r = app_client.get(f"/batches/{batch['id']}/temp/chart", headers=HDR)
    assert r.status_code == 200


def test_batch_temp_list_404_for_soft_deleted_batch(app_client):
    """A soft-deleted batch's readings are not listable."""
    truncate_database()
    batch = _create_batch(app_client)
    assert app_client.delete(f"/batches/{batch['id']}", headers=HDR).status_code == 204

    assert app_client.get(f"/batches/{batch['id']}/temp", headers=HDR).status_code == 404


def test_batch_temp_404_for_soft_deleted_batch(app_client):
    """POST /batches/{id}/temp returns 404 once the batch is soft-deleted."""
    truncate_database()
    batch = _create_batch(app_client)
    assert app_client.delete(f"/batches/{batch['id']}", headers=HDR).status_code == 204

    r = app_client.post(f"/batches/{batch['id']}/temp", json={"temperature": 20.0}, headers=HDR)
    assert r.status_code == 404


def test_batch_temp_range_validation(app_client):
    """POST /batches/{id}/temp returns 422 when temperature is out of range."""
    truncate_database()
    batch = _create_batch(app_client)
    r = app_client.post(f"/batches/{batch['id']}/temp", json={"temperature": 9999.0}, headers=HDR)
    assert r.status_code == 422


def test_list_temp_is_cursor_paginated(app_client):
    """GET /batches/{id}/temp returns a cursor page, oldest first."""
    truncate_database()
    batch = _create_batch(app_client)
    for temp in (18.0, 19.0, 20.0):
        app_client.post(f"/batches/{batch['id']}/temp", json={"temperature": temp}, headers=HDR)

    r = app_client.get(f"/batches/{batch['id']}/temp", headers=HDR)
    assert r.status_code == 200
    body = r.json()
    assert [i["temperature"] for i in body["items"]] == [18.0, 19.0, 20.0]
    assert body["hasMore"] is False


def test_list_temp_hides_excluded_unless_asked(app_client):
    """Excluded readings are filtered out by default, like gravity and pressure."""
    truncate_database()
    batch = _create_batch(app_client)
    app_client.post(f"/batches/{batch['id']}/temp", json={"temperature": 18.0}, headers=HDR)
    r = app_client.post(
        f"/batches/{batch['id']}/temp", json={"temperature": 99.0, "excluded": True}, headers=HDR
    )
    assert r.status_code == 201

    default = app_client.get(f"/batches/{batch['id']}/temp", headers=HDR).json()
    assert [i["temperature"] for i in default["items"]] == [18.0]

    everything = app_client.get(
        f"/batches/{batch['id']}/temp?includeExcluded=true", headers=HDR
    ).json()
    assert len(everything["items"]) == 2


def test_bulk_insert_temp(app_client):
    """POST /batches/{id}/temp/bulk restores history without per-row requests."""
    truncate_database()
    batch = _create_batch(app_client)
    rows = [{"temperature": 18.0}, {"temperature": 18.4}, {"temperature": 18.9}]

    r = app_client.post(f"/batches/{batch['id']}/temp/bulk", json=rows, headers=HDR)
    assert r.status_code == 201
    assert len(r.json()) == 3

    listed = app_client.get(f"/batches/{batch['id']}/temp", headers=HDR).json()
    assert len(listed["items"]) == 3


def test_patch_temp_reading(app_client):
    """PATCH /batches/{id}/temp/{reading_id} updates a single reading."""
    truncate_database()
    batch = _create_batch(app_client)
    created = app_client.post(
        f"/batches/{batch['id']}/temp", json={"temperature": 18.5}, headers=HDR
    ).json()

    r = app_client.patch(
        f"/batches/{batch['id']}/temp/{created['id']}",
        json={"excluded": True},
        headers=HDR,
    )
    assert r.status_code == 200
    assert r.json()["excluded"] is True

    remaining = app_client.get(f"/batches/{batch['id']}/temp", headers=HDR).json()
    assert remaining["items"] == []


def test_patch_unknown_temp_reading_is_404(app_client):
    """PATCH against a reading that does not exist returns 404."""
    truncate_database()
    batch = _create_batch(app_client)
    r = app_client.patch(
        f"/batches/{batch['id']}/temp/999999", json={"excluded": True}, headers=HDR
    )
    assert r.status_code == 404


def test_temp_chart_takes_resolution_like_the_others(app_client):
    """The temp chart accepts resolution/from/to, matching gravity and pressure."""
    truncate_database()
    batch = _create_batch(app_client)
    app_client.post(f"/batches/{batch['id']}/temp", json={"temperature": 18.5}, headers=HDR)

    r = app_client.get(f"/batches/{batch['id']}/temp/chart?resolution=hourly", headers=HDR)
    assert r.status_code == 200
    assert r.json()

    assert app_client.get(
        f"/batches/{batch['id']}/temp/chart?resolution=nonsense", headers=HDR
    ).status_code == 422
