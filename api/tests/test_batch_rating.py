# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for Batch.rating — settable only while packaged/archived, 1-5 range."""
from core.config import get_settings
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH_DATA = {
    "name": "Rating Batch",
    "acceptIngest": True,
    "og": 1.055,
    "fg": 1.010,
}


def test_init():
    """Reset database state before suite."""
    truncate_database()


def _create_batch(app_client, overrides=None):
    data = {**BATCH_DATA, **(overrides or {})}
    r = app_client.post("/batches", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


def _patch(app_client, batch_id, payload):
    return app_client.patch(f"/batches/{batch_id}", json=payload, headers=headers)


def test_rating_settable_when_packaged(app_client):
    """Rating can be set once the batch is already packaged."""
    test_init()
    batch = _create_batch(app_client)
    batch_id = batch["id"]

    r = _patch(app_client, batch_id, {"status": "packaged"})
    assert r.status_code == 200

    r = _patch(app_client, batch_id, {"rating": 4})
    assert r.status_code == 200
    assert r.json()["rating"] == 4


def test_rating_settable_when_archived(app_client):
    """Rating can be set once the batch is already archived."""
    test_init()
    batch = _create_batch(app_client)
    batch_id = batch["id"]

    r = _patch(app_client, batch_id, {"status": "packaged"})
    assert r.status_code == 200
    r = _patch(app_client, batch_id, {"status": "archived"})
    assert r.status_code == 200

    r = _patch(app_client, batch_id, {"rating": 5})
    assert r.status_code == 200
    assert r.json()["rating"] == 5


def test_rating_rejected_when_fermenting(app_client):
    """Rating is rejected with 400 while the batch is still fermenting."""
    test_init()
    batch = _create_batch(app_client)
    batch_id = batch["id"]

    r = _patch(app_client, batch_id, {"rating": 3})
    assert r.status_code == 400


def test_rating_and_status_transition_same_request(app_client):
    """Setting rating and transitioning to packaged in the same request succeeds."""
    test_init()
    batch = _create_batch(app_client)
    batch_id = batch["id"]

    r = _patch(app_client, batch_id, {"status": "packaged", "rating": 4})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "packaged"
    assert data["rating"] == 4


def test_rating_rejected_out_of_range(app_client):
    """Rating outside 1-5 is rejected, even once the batch is packaged."""
    test_init()
    batch = _create_batch(app_client)
    batch_id = batch["id"]

    r = _patch(app_client, batch_id, {"status": "packaged"})
    assert r.status_code == 200

    r = _patch(app_client, batch_id, {"rating": 0})
    assert r.status_code == 422

    r = _patch(app_client, batch_id, {"rating": 6})
    assert r.status_code == 422


def test_rating_null_or_absent_is_noop(app_client):
    """Omitting rating, or explicitly sending null, never triggers the status check."""
    test_init()
    batch = _create_batch(app_client)
    batch_id = batch["id"]

    # Absent entirely — plain unrelated update while fermenting.
    r = _patch(app_client, batch_id, {"notes": "still fermenting"})
    assert r.status_code == 200
    assert r.json()["rating"] is None

    # Explicit null while fermenting — should not be rejected.
    r = _patch(app_client, batch_id, {"rating": None})
    assert r.status_code == 200
    assert r.json()["rating"] is None
