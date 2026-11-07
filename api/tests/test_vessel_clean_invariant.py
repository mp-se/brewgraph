# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""A clean vessel is empty and unassigned: no batch, no tap, nothing remaining."""
from core.config import get_settings
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def _batch(app_client) -> str:
    r = app_client.post("/batches", json={"name": "Batch", "status": "packaged"}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _tap(app_client) -> str:
    r = app_client.post("/taps", json={"name": "Tap 1", "tapNumber": 1}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _keg(app_client, **overrides):
    payload = {
        "vesselType": "keg", "name": "Keg", "fillDate": "2026-05-01",
        "totalVolume": 19.0, "volumeRemaining": 12.0, "status": "serving", **overrides,
    }
    return app_client.post("/vessels", json=payload, headers=headers)


def _assert_clean_and_empty(body: dict) -> None:
    assert body["status"] == "clean"
    assert body["batchId"] is None
    assert body["tapId"] is None
    assert body["volumeRemaining"] == 0
    assert body["bottlesRemaining"] == 0


def _on_tap_with_batch(app_client) -> str:
    batch_id, tap_id = _batch(app_client), _tap(app_client)
    r = _keg(app_client, batchId=batch_id, tapId=tap_id)
    assert r.status_code == 201
    return r.json()["id"]


def test_init():
    """Reset database state before the scenario group."""
    truncate_database()


def test_patch_status_clean_releases_batch_tap_and_volume(app_client):
    """Marking a keg clean is the same transition as clearing its batch."""
    test_init()
    vessel_id = _on_tap_with_batch(app_client)

    r = app_client.patch(f"/vessels/{vessel_id}", json={"status": "clean"}, headers=headers)

    assert r.status_code == 200
    _assert_clean_and_empty(r.json())
    _assert_clean_and_empty(app_client.get(f"/vessels/{vessel_id}", headers=headers).json())


def test_patch_status_clean_matches_explicit_batch_null(app_client):
    """`status: clean` and `batchId: null` leave the vessel in the same state."""
    test_init()
    first = _on_tap_with_batch(app_client)
    by_status = app_client.patch(f"/vessels/{first}", json={"status": "clean"}, headers=headers)
    test_init()
    second = _on_tap_with_batch(app_client)
    by_batch = app_client.patch(f"/vessels/{second}", json={"batchId": None}, headers=headers)

    for field in ("status", "batchId", "tapId", "volumeRemaining", "bottlesRemaining"):
        assert by_status.json()[field] == by_batch.json()[field]


def test_patch_status_clean_with_a_batch_is_rejected(app_client):
    """A request cannot both link a batch and ask for a clean vessel."""
    test_init()
    vessel_id = _keg(app_client, status="filled").json()["id"]

    r = app_client.patch(
        f"/vessels/{vessel_id}", json={"status": "clean", "batchId": _batch(app_client)},
        headers=headers,
    )

    assert r.status_code == 422
    assert "a clean vessel has no batch" in r.text


def test_patch_status_clean_with_a_tap_is_rejected(app_client):
    """A request cannot both assign a tap and ask for a clean vessel."""
    test_init()
    vessel_id = _keg(app_client, status="filled").json()["id"]

    r = app_client.patch(
        f"/vessels/{vessel_id}", json={"status": "clean", "tapId": _tap(app_client)},
        headers=headers,
    )

    assert r.status_code == 422
    assert "a clean vessel has no tap" in r.text


def test_linking_a_batch_moves_a_clean_vessel_to_filled(app_client):
    """Filling a clean vessel from a batch takes the status a new filled vessel takes."""
    test_init()
    vessel_id = _keg(app_client, status="clean").json()["id"]

    r = app_client.patch(
        f"/vessels/{vessel_id}",
        json={"batchId": _batch(app_client), "volumeRemaining": 19.0}, headers=headers,
    )

    assert r.status_code == 200
    assert r.json()["status"] == "filled"
    assert r.json()["volumeRemaining"] == 19.0


def test_filling_a_clean_vessel_with_volume_moves_it_to_filled(app_client):
    """Volume put into a clean vessel means it is no longer clean."""
    test_init()
    vessel_id = _keg(app_client, status="clean").json()["id"]

    r = app_client.patch(f"/vessels/{vessel_id}", json={"volumeRemaining": 5.0}, headers=headers)

    assert r.json()["status"] == "filled"
    assert r.json()["volumeRemaining"] == 5.0


def test_unrelated_edit_keeps_a_clean_vessel_clean(app_client):
    """Renaming a clean vessel does not change its status or links."""
    test_init()
    vessel_id = _keg(app_client, status="clean").json()["id"]

    r = app_client.patch(f"/vessels/{vessel_id}", json={"name": "Renamed"}, headers=headers)

    _assert_clean_and_empty(r.json())


def test_create_clean_with_a_batch_is_rejected(app_client):
    """A vessel cannot be created clean and linked to a batch."""
    test_init()

    r = _keg(app_client, status="clean", batchId=_batch(app_client))

    assert r.status_code == 422
    assert "a clean vessel has no batch" in r.text


def test_create_clean_with_a_tap_is_rejected(app_client):
    """A vessel cannot be created clean and on a tap."""
    test_init()

    r = _keg(app_client, status="clean", tapId=_tap(app_client))

    assert r.status_code == 422
    assert "a clean vessel has no tap" in r.text


def test_create_clean_stores_nothing_remaining(app_client):
    """A clean vessel is created empty whatever volume the payload carries."""
    test_init()

    r = _keg(app_client, status="clean", volumeRemaining=19.0)

    assert r.status_code == 201
    _assert_clean_and_empty(r.json())


def test_draining_a_keg_by_pouring_is_empty_not_clean(app_client):
    """A keg poured to zero keeps its batch and status; only the tap is released."""
    test_init()
    vessel_id = _on_tap_with_batch(app_client)

    r = app_client.post(f"/vessels/{vessel_id}/pours", json={"pourAmount": 50.0}, headers=headers)
    assert r.status_code == 201

    body = app_client.get(f"/vessels/{vessel_id}", headers=headers).json()
    assert body["volumeRemaining"] == 0
    assert body["tapId"] is None
    assert body["status"] == "serving"
    assert body["batchId"] is not None
