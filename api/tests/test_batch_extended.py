# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Extended batch tests covering service search methods and dashboard endpoint."""
import uuid
from datetime import datetime, timedelta, timezone

from core.config import get_settings
from core.db import get_session
from core.middleware.auth import AuthContext, get_retention_cutoff
from oss.schemas.gravity_reading import GravityReadingCreate
from oss.services.gravity import GravityService
from tests.conftest import DEVICE_DEFAULTS, truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH_DATA = {
    "name": "Extended Batch",
    "acceptIngest": True,
    "og": 1.055,
    "fg": 1.010,
}

DEVICE_DATA = {
    "name": "Ext Device",
    "deviceType": "gravitymon",
    "chipId": "EXT001",
    **DEVICE_DEFAULTS,
}


def test_init():
    """Reset database state before suite."""
    truncate_database()


def _create_batch(app_client, overrides=None):
    data = {**BATCH_DATA, **(overrides or {})}
    r = app_client.post("/batches", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


def _create_device(app_client, overrides=None):
    data = {**DEVICE_DATA, **(overrides or {})}
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


def _assign_device_to_batch(app_client, device: dict, batch_id: str, role: str = "gravity"):
    payload = {**DEVICE_DATA, "name": device["name"], "batchId": batch_id, "batchRole": role}
    r = app_client.patch(f"/devices/{device['id']}", json=payload, headers=headers)
    assert r.status_code == 200


# --- soft delete ---

def test_soft_delete_removes_from_list_and_404s_on_get(app_client):
    """Soft-deleting a batch hides it from list and returns 404 on get."""
    test_init()
    b = _create_batch(app_client)
    r = app_client.delete(f"/batches/{b['id']}", headers=headers)
    assert r.status_code == 204

    r2 = app_client.get(f"/batches/{b['id']}", headers=headers)
    assert r2.status_code == 404

    all_batches = app_client.get("/batches", headers=headers).json()["items"]
    assert b["id"] not in [x["id"] for x in all_batches]


def test_soft_delete_nonexistent_returns_404(app_client):
    """Deleting a non-existent batch returns 404."""
    test_init()
    r = app_client.delete(f"/batches/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404


def test_patch_soft_deleted_batch_returns_404(app_client):
    """PATCHing a soft-deleted batch is rejected, not silently applied."""
    test_init()
    b = _create_batch(app_client)
    assert app_client.delete(f"/batches/{b['id']}", headers=headers).status_code == 204

    r = app_client.patch(
        f"/batches/{b['id']}", json={"name": "Should not apply"}, headers=headers
    )
    assert r.status_code == 404


# --- filter by device_id ---

def test_filter_by_device_id(app_client):
    """GET /batches/?deviceId=<id> returns only batches linked to that device."""
    test_init()
    dev = _create_device(app_client)
    dev_id = dev["id"]

    linked = _create_batch(app_client)
    _assign_device_to_batch(app_client, dev, linked["id"])
    _create_batch(app_client, {"name": "Unlinked"})

    r = app_client.get(f"/batches/?deviceId={dev_id}", headers=headers)
    data = r.json()["items"]
    assert len(data) == 1
    assert data[0]["id"] == linked["id"]


def test_filter_by_device_id_returns_only_assigned_batch(app_client):
    """GET /batches/?deviceId=<id> returns only the batch the device is assigned to."""
    test_init()
    dev = _create_device(app_client, {"chipId": "EXT002", "name": "Dev2"})

    linked = _create_batch(app_client, {"acceptIngest": True})
    _assign_device_to_batch(app_client, dev, linked["id"])
    _create_batch(app_client, {"name": "Unlinked", "acceptIngest": False})

    r = app_client.get(f"/batches/?deviceId={dev['id']}", headers=headers)
    data = r.json()["items"]
    assert len(data) == 1
    assert data[0]["id"] == linked["id"]




# --- data retention (unit tests on AuthContext / get_retention_cutoff) ---

def test_retention_cutoff_none_when_unlimited():
    """get_retention_cutoff returns None when retention_days is -1."""
    assert get_retention_cutoff(AuthContext(retention_days=-1)) is None


def test_retention_cutoff_returns_datetime_when_limited():
    """get_retention_cutoff returns a datetime in the past when retention_days > 0."""
    cutoff = get_retention_cutoff(AuthContext(retention_days=30))
    assert cutoff is not None
    expected = datetime.now(timezone.utc) - timedelta(days=30)
    assert abs((cutoff - expected).total_seconds()) < 2


def test_retention_filters_old_gravity_readings(app_client):
    """GravityService.search_by_batch_id filters readings older than the cutoff."""
    test_init()
    r = app_client.post("/batches", json={**BATCH_DATA, "name": "RetBatch"}, headers=headers)
    batch_id = r.json()["id"]

    now = datetime.now(timezone.utc)
    db = next(get_session())
    svc = GravityService(db)
    for days_ago, gravity in [(5, 1.055), (0, 1.040)]:
        svc.create(GravityReadingCreate(
            batch_id=uuid.UUID(batch_id),
            gravity=gravity,
            angle=30.0,
            battery=3.8,
            rssi=-70.0,
            excluded=False,
            created_at=now - timedelta(days=days_ago),
        ))

    cutoff_2d = get_retention_cutoff(AuthContext(retention_days=2))
    recent_only = svc.search_by_batch_id(uuid.UUID(batch_id), retention_cutoff=cutoff_2d)
    assert len(recent_only) == 1
    assert recent_only[0].gravity == 1.040

    all_readings = svc.search_by_batch_id(uuid.UUID(batch_id), retention_cutoff=None)
    assert len(all_readings) == 2


# ---------------------------------------------------------------------------
# list_filtered_page — pagination and filter combinations
# ---------------------------------------------------------------------------

def test_batch_list_paginated(app_client):
    """GET /batches/?page=1&pageSize=2 returns paginated results."""
    truncate_database()
    for i in range(4):
        app_client.post(
            "/batches",
            json={"name": f"Batch {i}", "acceptIngest": True},
            headers=headers,
        )
    r = app_client.get("/batches/?page=1&pageSize=2", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 4
    assert len(data["items"]) == 2
    assert data["pages"] == 2


def test_batch_list_page2(app_client):
    """GET /batches/?page=2&pageSize=2 returns second page."""
    truncate_database()
    for i in range(3):
        app_client.post(
            "/batches",
            json={"name": f"Page2 Batch {i}", "acceptIngest": True},
            headers=headers,
        )
    r = app_client.get("/batches/?page=2&pageSize=2", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1


def test_batch_list_filter_by_accept_ingest(app_client):
    """All batches are returned regardless of accept_ingest; filtering is client-side."""
    truncate_database()
    app_client.post("/batches", json={"name": "Active", "acceptIngest": True}, headers=headers)
    app_client.post("/batches", json={"name": "Archived", "acceptIngest": False}, headers=headers)
    r = app_client.get("/batches", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2


def test_soft_delete_nonexistent_batch_returns_404(app_client):
    """DELETE /batches/{unknown_id} returns 404 (exercises soft_delete False branch)."""
    truncate_database()
    r = app_client.delete(f"/batches/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404


def test_batch_list_with_device_filter(app_client):
    """GET /batches/?deviceId=X returns only batches linked to that device."""
    truncate_database()
    dev_r = app_client.post(
        "/devices",
        json={"name": "Filter Dev", "chipId": "FLT001", **DEVICE_DEFAULTS},
        headers=headers,
    )
    dev = dev_r.json()
    linked_r = app_client.post(
        "/batches",
        json={"name": "Linked", "acceptIngest": True},
        headers=headers,
    )
    linked_id = linked_r.json()["id"]
    _assign_device_to_batch(app_client, dev, linked_id)
    app_client.post("/batches", json={"name": "Unlinked", "acceptIngest": True}, headers=headers)

    r = app_client.get(f"/batches/?deviceId={dev['id']}", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Linked"
