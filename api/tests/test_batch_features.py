# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for batch notes and restore endpoints."""
import uuid

from core.config import get_settings
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH_DATA = {"name": "FeatureBatch", "acceptIngest": True, "og": 1.055, "fg": 1.010, "abv": 5.9}


def clean_db():
    """Truncate the database before each test."""
    truncate_database()


def _create_batch(app_client, overrides=None):
    data = {**BATCH_DATA, **(overrides or {})}
    r = app_client.post("/batches", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# 1. Batch notes
# ---------------------------------------------------------------------------

def test_notes_set_on_create(app_client):
    """Notes can be set when creating a batch."""
    clean_db()
    b = _create_batch(app_client, {"notes": "My tasting notes"})
    assert b["notes"] == "My tasting notes"


def test_notes_update_via_patch(app_client):
    """PATCH /batches/{id} updates the notes field."""
    clean_db()
    b = _create_batch(app_client)
    assert b["notes"] is None

    r = app_client.patch(f"/batches/{b['id']}", json={**BATCH_DATA, "notes": "Updated notes"},
                         headers=headers)
    assert r.status_code == 200
    assert r.json()["notes"] == "Updated notes"


def test_notes_clear_via_patch(app_client):
    """PATCH /batches/{id} can clear notes back to null."""
    clean_db()
    b = _create_batch(app_client, {"notes": "Some notes"})

    r = app_client.patch(f"/batches/{b['id']}", json={**BATCH_DATA, "notes": None},
                         headers=headers)
    assert r.status_code == 200
    assert r.json()["notes"] is None


def test_notes_returned_in_get(app_client):
    """GET /batches/{id} includes the notes field."""
    clean_db()
    b = _create_batch(app_client, {"notes": "Readable notes"})
    r = app_client.get(f"/batches/{b['id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["notes"] == "Readable notes"


# ---------------------------------------------------------------------------
# 2. Restore soft-deleted batch
# ---------------------------------------------------------------------------

def test_restore_non_deleted_batch_returns_404(app_client):
    """POST /batches/{id}/restore on a live batch returns 404."""
    clean_db()
    b = _create_batch(app_client)
    r = app_client.post(f"/batches/{b['id']}/restore", headers=headers)
    assert r.status_code == 404


def test_restore_unknown_batch_returns_404(app_client):
    """POST /batches/{id}/restore with an unknown ID returns 404."""
    r = app_client.post(f"/batches/{uuid.uuid4()}/restore", headers=headers)
    assert r.status_code == 404
