# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for tap endpoints."""
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.config import get_settings
from core.db import create_session
from core.models.registry import resolve_model
from main_oss import app
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

TAP_DATA = {"name": "Left Tap", "tapNumber": 1, "location": "Kegerator A"}


def test_init():
    """Reset database state before the scenario group."""
    truncate_database()


def test_create_tap(app_client):
    """POST /taps/ creates a tap and returns it."""
    test_init()
    r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Left Tap"
    assert data["tapNumber"] == 1
    assert data["location"] == "Kegerator A"
    assert "id" in data


def test_list_taps(app_client):
    """GET /taps/ returns paginated envelope with all taps."""
    test_init()
    app_client.post("/taps", json=TAP_DATA, headers=headers)
    app_client.post("/taps", json={"name": "Right Tap", "tapNumber": 2}, headers=headers)

    r = app_client.get("/taps", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert "pages" in body
    assert len(body["items"]) == 2


def test_list_taps_pagination(app_client):
    """GET /taps/?page=1&pageSize=1 returns correct page metadata."""
    test_init()
    app_client.post("/taps", json=TAP_DATA, headers=headers)
    app_client.post("/taps", json={"name": "Right Tap", "tapNumber": 2}, headers=headers)

    r = app_client.get("/taps/?page=1&pageSize=1", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["pages"] == 2
    assert len(body["items"]) == 1


def test_get_tap(app_client):
    """GET /taps/{id} returns the requested tap."""
    test_init()
    r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    tap_id = r.json()["id"]

    r2 = app_client.get(f"/taps/{tap_id}", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["id"] == tap_id


def test_get_tap_not_found(app_client):
    """GET /taps/{id} returns 404 for an unknown id."""
    r = app_client.get("/taps/00000000-0000-0000-0000-000000000000", headers=headers)
    assert r.status_code == 404


def test_update_tap(app_client):
    """PATCH /taps/{id} updates tap fields."""
    test_init()
    r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    tap_id = r.json()["id"]

    r2 = app_client.patch(f"/taps/{tap_id}", json={"name": "Renamed Tap"}, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["name"] == "Renamed Tap"


def test_delete_tap(app_client):
    """DELETE /taps/{id} soft-deletes a tap and makes it 404."""
    test_init()
    r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    tap_id = r.json()["id"]

    r2 = app_client.delete(f"/taps/{tap_id}", headers=headers)
    assert r2.status_code == 204

    r3 = app_client.get(f"/taps/{tap_id}", headers=headers)
    assert r3.status_code == 404


def test_delete_tap_excludes_it_from_the_list(app_client):
    """A soft-deleted tap disappears from GET /taps/ rather than lingering."""
    test_init()
    r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    tap_id = r.json()["id"]
    app_client.delete(f"/taps/{tap_id}", headers=headers)

    listed = app_client.get("/taps", headers=headers).json()
    ids = [t["id"] for t in listed["items"]]
    assert tap_id not in ids


def test_restore_tap_that_is_not_deleted_returns_404(app_client):
    """Restoring a live tap is a 404 -- there is nothing to undo."""
    test_init()
    r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    tap_id = r.json()["id"]

    r2 = app_client.post(f"/taps/{tap_id}/restore", headers=headers)
    assert r2.status_code == 404


def test_create_tap_generates_token(app_client):
    """POST /taps/ generates an ingest token and returns it."""
    test_init()
    r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert "token" in data
    assert data["token"] is not None
    assert len(data["token"]) > 0
    # Token persists in GET response (UI handles display via frontend state)
    tap_id = data["id"]
    r2 = app_client.get(f"/taps/{tap_id}", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["token"] is not None


def test_regenerate_tap_token(app_client):
    """POST /taps/{id}/token regenerates and returns a new token."""
    test_init()
    r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    tap_id = r.json()["id"]
    original_token = r.json()["token"]

    r2 = app_client.post(f"/taps/{tap_id}/token", headers=headers)
    assert r2.status_code == 200
    data = r2.json()
    assert "token" in data
    assert data["token"] is not None
    assert data["token"] != original_token
    assert len(data["token"]) > 0


def test_regenerate_tap_token_not_found(app_client):
    """POST /taps/{id}/token returns 404 for unknown tap."""
    r = app_client.post("/taps/00000000-0000-0000-0000-000000000000/token", headers=headers)
    assert r.status_code == 404


def test_patch_soft_deleted_tap_returns_404(app_client):
    """PATCHing a soft-deleted tap is rejected, not silently applied."""
    test_init()
    r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    tap_id = r.json()["id"]
    assert app_client.delete(f"/taps/{tap_id}", headers=headers).status_code == 204

    r2 = app_client.patch(f"/taps/{tap_id}", json={"name": "Should not apply"}, headers=headers)
    assert r2.status_code == 404


def test_regenerate_token_on_soft_deleted_tap_returns_404(app_client):
    """A soft-deleted tap's ingest token cannot be rotated — no fresh live
    token should ever be handed out for an entity the UI shows as deleted."""
    test_init()
    r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    tap_id = r.json()["id"]
    assert app_client.delete(f"/taps/{tap_id}", headers=headers).status_code == 204

    r2 = app_client.post(f"/taps/{tap_id}/token", headers=headers)
    assert r2.status_code == 404


def test_tap_token_collision_surfaces_as_409():
    """A forced token collision rolls back the whole staged tap creation."""
    test_init()
    with TestClient(
        app, base_url="http://testserver/api", raise_server_exceptions=False
    ) as client, patch(
        "oss.services.tap.generate_token", return_value="FIXEDTAPTOKENVALUE"
    ):
        first = client.post("/taps", json=TAP_DATA, headers=headers)
        assert first.status_code == 201
        assert first.json()["token"] == "FIXEDTAPTOKENVALUE"

        second = client.post(
            "/taps", json={"name": "Right Tap", "tapNumber": 2}, headers=headers
        )
        assert second.status_code == 409
        tap_model = resolve_model("Tap")
        session = create_session()
        try:
            assert session.query(tap_model).count() == 1
        finally:
            session.remove()


def test_tap_response_includes_last_seen_camel_case_null(app_client):
    """GET /taps/{id} exposes lastSeen (camelCase), null for a never-poured tap."""
    test_init()
    r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    tap_id = r.json()["id"]
    assert "lastSeen" in r.json()
    assert r.json()["lastSeen"] is None

    r2 = app_client.get(f"/taps/{tap_id}", headers=headers)
    assert r2.status_code == 200
    assert "lastSeen" in r2.json()
    assert r2.json()["lastSeen"] is None


def test_tap_last_seen_is_not_writable_on_create(app_client):
    """lastSeen is server-assigned; posting it must not set it (forgeable liveness)."""
    test_init()
    payload = dict(TAP_DATA, lastSeen="2026-01-01T00:00:00Z")
    r = app_client.post("/taps", json=payload, headers=headers)
    assert r.status_code == 201
    assert r.json()["lastSeen"] is None


def test_tap_last_seen_is_not_writable_on_update(app_client):
    """PATCH must not let a client set lastSeen either."""
    test_init()
    r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    tap_id = r.json()["id"]

    r2 = app_client.patch(
        f"/taps/{tap_id}", json={"lastSeen": "2026-01-01T00:00:00Z"}, headers=headers
    )
    assert r2.status_code == 200
    assert r2.json()["lastSeen"] is None


def _tap_counters(tap_id):
    """Read Tap.total_volume_poured/volume_at_last_clean directly.

    Neither field is exposed on TapResponse, so this reads the ORM row the same
    way test_pour_events.py's test_latest_global_pours reads PourEvent rows.
    """
    tap_model = resolve_model("Tap")
    s = create_session()
    try:
        tap = s.get(tap_model, uuid.UUID(tap_id))
        return tap.total_volume_poured, tap.volume_at_last_clean
    finally:
        s.remove()


def test_new_tap_starts_with_zero_throughput_counters(app_client):
    """A freshly created tap has both throughput columns at 0."""
    test_init()
    tap_id = app_client.post("/taps", json=TAP_DATA, headers=headers).json()["id"]
    total, at_clean = _tap_counters(tap_id)
    assert total == 0.0
    assert at_clean == 0.0


def test_last_cleaned_at_snapshots_throughput_counter(app_client):
    """PATCH lastCleanedAt snapshots total_volume_poured into volume_at_last_clean.

    Hangs off the existing last_cleaned_at write path (TapService.update), not
    a new trigger point -- see oss/services/tap.py. A pour recorded after the
    snapshot advances the running total but must not move the snapshot itself.
    """
    test_init()
    tap_id = app_client.post("/taps", json=TAP_DATA, headers=headers).json()["id"]
    batch_id = app_client.post(
        "/batches", json={"name": "Clean Snapshot Batch", "status": "packaged"}, headers=headers
    ).json()["id"]
    vessel_id = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselType": "keg",
            "name": "Snapshot Keg",
            "fillDate": "2026-05-01",
            "totalVolume": 19.0,
            "volumeRemaining": 19.0,
            "status": "serving",
        },
        headers=headers,
    ).json()["id"]
    # tapId is Update/Response-only on the vessel schema, not settable at create.
    app_client.patch(f"/vessels/{vessel_id}", json={"tapId": tap_id}, headers=headers)
    app_client.post(f"/vessels/{vessel_id}/pours", json={"pourAmount": 1.0}, headers=headers)

    total, at_clean = _tap_counters(tap_id)
    assert total == 1.0
    assert at_clean == 0.0

    r = app_client.patch(
        f"/taps/{tap_id}", json={"lastCleanedAt": "2026-01-01T00:00:00Z"}, headers=headers
    )
    assert r.status_code == 200
    _, at_clean = _tap_counters(tap_id)
    assert at_clean == 1.0

    app_client.post(f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.4}, headers=headers)
    total, at_clean = _tap_counters(tap_id)
    assert round(total, 4) == 1.4
    assert at_clean == 1.0


def test_unrelated_tap_update_does_not_snapshot_the_counter(app_client):
    """PATCH fields other than lastCleanedAt must not touch volume_at_last_clean."""
    test_init()
    tap_id = app_client.post("/taps", json=TAP_DATA, headers=headers).json()["id"]
    r = app_client.patch(f"/taps/{tap_id}", json={"name": "Renamed Again"}, headers=headers)
    assert r.status_code == 200
    total, at_clean = _tap_counters(tap_id)
    assert total == 0.0
    assert at_clean == 0.0
