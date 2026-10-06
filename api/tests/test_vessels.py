# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for storage vessel endpoints."""
import uuid
from unittest.mock import patch

from core.config import get_settings
from core.db import get_session
from oss.extensions.tenant import DEFAULT_TENANT_ID
from oss.schemas.temp_reading import TempReadingCreate
from oss.services.temp_reading import TempService
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH_DATA = {"name": "Vessel Test Batch", "status": "packaged"}


def _create_batch(app_client) -> str:
    r = app_client.post("/batches", json=BATCH_DATA, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _vessel_data(batch_id: str) -> dict:
    return {
        "batchId": batch_id,
        "vesselNumber": 1,
        "vesselType": "keg",
        "name": "Keg 1",
        "fillDate": "2026-05-01",
        "totalVolume": 19.0,
        "volumeRemaining": 19.0,
        "status": "filled",
    }


def test_init():
    """Reset database state before the scenario group."""
    truncate_database()


def test_create_vessel(app_client):
    """POST /vessels/ creates a vessel and returns it."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Keg 1"
    assert data["vesselType"] == "keg"
    assert data["vesselNumber"] == 1
    assert data["volumeRemaining"] == 19.0
    assert "id" in data


def test_create_vessel_with_tap_id(app_client):
    """POST /vessels/ accepts tapId at create time (needed by restore, which
    creates vessels already carrying their old tap assignment rather than
    following up with a PATCH)."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/taps", json={"name": "Tap 1", "tapNumber": 1}, headers=headers)
    tap_id = r.json()["id"]

    data = _vessel_data(batch_id)
    data["tapId"] = tap_id
    r = app_client.post("/vessels", json=data, headers=headers)
    assert r.status_code == 201
    assert r.json()["tapId"] == tap_id


def test_list_vessels(app_client):
    """GET /vessels/ returns paginated envelope with all non-deleted vessels."""
    test_init()
    batch_id = _create_batch(app_client)
    app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)

    r = app_client.get("/vessels", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert "pages" in body
    assert len(body["items"]) >= 1


def test_list_vessels_filter_by_batch(app_client):
    """GET /vessels/?batchId=... filters to the given batch."""
    test_init()
    batch_id = _create_batch(app_client)
    app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)

    r = app_client.get(f"/vessels/?batchId={batch_id}", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(v["batchId"] == batch_id for v in items)


def test_list_vessels_pagination(app_client):
    """GET /vessels/?page=1&pageSize=1 returns correct page metadata."""
    test_init()
    batch_id = _create_batch(app_client)
    app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    v2 = _vessel_data(batch_id)
    v2["name"] = "Keg 2"
    app_client.post("/vessels", json=v2, headers=headers)

    r = app_client.get("/vessels/?page=1&pageSize=1", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["pages"] == 2
    assert len(body["items"]) == 1


def test_get_vessel(app_client):
    """GET /vessels/{id} returns the requested vessel."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    r2 = app_client.get(f"/vessels/{vessel_id}", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["id"] == vessel_id


def test_update_vessel(app_client):
    """PATCH /vessels/{id} updates vessel fields."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    r2 = app_client.patch(
        f"/vessels/{vessel_id}", json={"status": "serving", "vesselNumber": 3}, headers=headers
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "serving"
    assert r2.json()["vesselNumber"] == 3


def test_patch_soft_deleted_vessel_returns_404(app_client):
    """PATCHing a soft-deleted vessel is rejected, not silently applied —
    `update()` resolves via `get_active()`, the same primitive device/tap/batch
    `update()` use to reject an entity already treated as gone."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]
    assert app_client.delete(f"/vessels/{vessel_id}", headers=headers).status_code == 204

    r2 = app_client.patch(
        f"/vessels/{vessel_id}", json={"name": "Should not apply"}, headers=headers
    )
    assert r2.status_code == 404


def test_batch_vessels_nested_endpoint(app_client):
    """GET /batches/{id}/vessels returns vessels for a specific batch."""
    test_init()
    batch_id = _create_batch(app_client)
    app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)

    r = app_client.get(f"/batches/{batch_id}/vessels", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["batchId"] == batch_id


def test_delete_vessel(app_client):
    """DELETE /vessels/{id} soft-deletes a vessel and makes it 404."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    r2 = app_client.delete(f"/vessels/{vessel_id}", headers=headers)
    assert r2.status_code == 204

    r3 = app_client.get(f"/vessels/{vessel_id}", headers=headers)
    assert r3.status_code == 404


def test_assign_batch(app_client):
    """PATCH /vessels/{id} with batchId assigns a vessel to a batch."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    batch_id2 = _create_batch(app_client)
    r2 = app_client.patch(
        f"/vessels/{vessel_id}", json={"batchId": batch_id2}, headers=headers
    )
    assert r2.status_code == 200
    assert r2.json()["batchId"] == batch_id2


def test_unrelated_patch_does_not_disturb_batch_or_tap(app_client):
    """Renaming a vessel must not unassign its batch or its tap.

    This is the whole risk of folding assign-batch/assign-tap into PATCH: for these two
    fields null is a command ("empty the keg", "release the tap"), so a service that
    tested `is None` instead of "was this field sent" would silently clear both on every
    unrelated edit. That failure is invisible in the response, which is why it is pinned
    here rather than left to the assign tests.
    """
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    r = app_client.post("/taps", json={"name": "Tap 1", "tapNumber": 1}, headers=headers)
    tap_id = r.json()["id"]
    app_client.patch(f"/vessels/{vessel_id}", json={"tapId": tap_id}, headers=headers)

    r = app_client.patch(f"/vessels/{vessel_id}", json={"name": "Renamed"}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Renamed"
    assert body["batchId"] == batch_id
    assert body["tapId"] == tap_id


def test_explicit_nulls_clear_batch_and_tap(app_client):
    """The other half: an explicit null *is* honoured, and empties/releases the vessel."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    r = app_client.post("/taps", json={"name": "Tap 2", "tapNumber": 2}, headers=headers)
    tap_id = r.json()["id"]
    app_client.patch(f"/vessels/{vessel_id}", json={"tapId": tap_id}, headers=headers)

    r = app_client.patch(f"/vessels/{vessel_id}", json={"tapId": None}, headers=headers)
    assert r.json()["tapId"] is None

    r = app_client.patch(f"/vessels/{vessel_id}", json={"batchId": None}, headers=headers)
    assert r.json()["batchId"] is None
    assert r.json()["status"] == "clean"


def test_emptying_vessel_resets_volume_and_bottles_remaining(app_client):
    """batchId: null resets volumeRemaining/bottlesRemaining to 0, not just status.

    An emptied vessel holds nothing, so stale remaining figures from its last
    fill must not persist and read as still-full stock.
    """
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]
    assert r.json()["volumeRemaining"] == 19.0

    r = app_client.patch(f"/vessels/{vessel_id}", json={"batchId": None}, headers=headers)
    assert r.json()["batchId"] is None
    assert r.json()["volumeRemaining"] == 0.0
    assert r.json()["bottlesRemaining"] == 0


def test_assigning_a_tap_evicts_the_previous_vessel(app_client):
    """One tap holds one vessel — assigning a second one releases the first."""
    test_init()
    batch_id = _create_batch(app_client)
    first = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers).json()["id"]
    data = _vessel_data(batch_id)
    data["vesselNumber"] = 2
    data["name"] = "Keg 2"
    second = app_client.post("/vessels", json=data, headers=headers).json()["id"]

    r = app_client.post("/taps", json={"name": "Tap 3", "tapNumber": 3}, headers=headers)
    tap_id = r.json()["id"]

    app_client.patch(f"/vessels/{first}", json={"tapId": tap_id}, headers=headers)
    app_client.patch(f"/vessels/{second}", json={"tapId": tap_id}, headers=headers)

    assert app_client.get(f"/vessels/{first}", headers=headers).json()["tapId"] is None
    assert app_client.get(f"/vessels/{second}", headers=headers).json()["tapId"] == tap_id


def test_vessel_token_endpoint_removed(app_client):
    """POST /vessels/{id}/token no longer exists (404, no matching path).

    Vessels never had a token anyone could resolve — ingest resolves the *tap* token and walks
    to the current vessel, which is why the tap-level token survives keg swaps. The endpoint and
    the token/token_hash columns were removed.
    """
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    r2 = app_client.post(f"/vessels/{vessel_id}/token", headers=headers)
    assert r2.status_code == 404

    r3 = app_client.get(f"/vessels/{vessel_id}", headers=headers)
    assert "token" not in r3.json()


def _seed_temp_reading(vessel_id: str, temperature: float) -> None:
    """Insert a temp reading directly via service (no REST endpoint for writes)."""
    db = next(get_session())
    svc = TempService(db)
    svc.create(TempReadingCreate(vessel_id=uuid.UUID(vessel_id), temperature=temperature))
    db.commit()


def test_vessel_temp_latest_endpoint_is_gone(app_client):
    """`/vessels/{id}/temp/latest` no longer exists — the dashboard carries it."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    r2 = app_client.get(f"/vessels/{vessel_id}/temp/latest", headers=headers)
    assert r2.status_code in (404, 405)


def test_dashboard_carries_the_vessel_current_temp(app_client):
    """The dashboard reports a vessel's latest temperature, replacing /temp/latest."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]
    _seed_temp_reading(vessel_id, 18.5)

    dashboard = app_client.get("/dashboard", headers=headers).json()
    vessel = next(v for v in dashboard["vessels"] if v["id"] == vessel_id)
    assert vessel["currentTemp"] == 18.5


def test_dashboard_vessel_current_temp_is_null_without_readings(app_client):
    """No readings means null, not an omitted key — clients render one branch."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    dashboard = app_client.get("/dashboard", headers=headers).json()
    vessel = next(v for v in dashboard["vessels"] if v["id"] == vessel_id)
    assert vessel["currentTemp"] is None
    assert vessel["currentPressure"] is None


def test_vessel_temp_list_and_patch(app_client):
    """Vessel temperature readings list and patch like batch readings do."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]
    _seed_temp_reading(vessel_id, 18.5)

    listed = app_client.get(f"/vessels/{vessel_id}/temp", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert [i["temperature"] for i in body["items"]] == [18.5]
    reading_id = body["items"][0]["id"]

    patched = app_client.patch(
        f"/vessels/{vessel_id}/temp/{reading_id}", json={"excluded": True}, headers=headers
    )
    assert patched.status_code == 200
    assert patched.json()["excluded"] is True
    assert app_client.get(f"/vessels/{vessel_id}/temp", headers=headers).json()["items"] == []


def test_vessel_temp_bulk_insert(app_client):
    """Bulk insert exists on the vessel path too, same as the batch one."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    rows = [{"temperature": 18.0}, {"temperature": 18.4}]
    created = app_client.post(f"/vessels/{vessel_id}/temp/bulk", json=rows, headers=headers)
    assert created.status_code == 201
    assert len(created.json()) == 2
    assert len(app_client.get(f"/vessels/{vessel_id}/temp", headers=headers).json()["items"]) == 2


def test_vessel_pressure_bulk_insert(app_client):
    """POST /vessels/{id}/pressure/bulk succeeds — regression for the batch-validation
    guard in PressureService.create_list not carrying over from the single-reading
    path when batch_id is cleared to None for vessel-owned readings."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    rows = [{"pressure": 1.2}, {"pressure": 1.3}]
    created = app_client.post(f"/vessels/{vessel_id}/pressure/bulk", json=rows, headers=headers)
    assert created.status_code == 201
    assert len(created.json()) == 2
    assert len(
        app_client.get(f"/vessels/{vessel_id}/pressure", headers=headers).json()["items"]
    ) == 2


def test_vessel_temp_chart_empty(app_client):
    """GET /vessels/{id}/temp/chart returns [] when no readings exist."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    r2 = app_client.get(f"/vessels/{vessel_id}/temp/chart", headers=headers)
    assert r2.status_code == 200
    assert r2.json() == []


def test_vessel_temp_chart(app_client):
    """GET /vessels/{id}/temp/chart returns chart points for existing readings."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]
    for temp in [18.0, 18.5, 19.0]:
        _seed_temp_reading(vessel_id, temp)

    r2 = app_client.get(f"/vessels/{vessel_id}/temp/chart", headers=headers)
    assert r2.status_code == 200
    points = r2.json()
    assert len(points) == 3
    assert "t" in points[0]
    assert "temp" in points[0]


def test_record_pour_publishes_event(app_client):
    """POST /vessels/{id}/pours publishes a vessel/update SSE event."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    with patch("oss.routers.vessel_pours.notify_clients") as mock_notify:
        r2 = app_client.post(
            f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.5}, headers=headers
        )
    assert r2.status_code == 201
    mock_notify.assert_called_once_with("vessel", "update", uuid.UUID(vessel_id),
                                         DEFAULT_TENANT_ID, source="vessel")


def test_oversized_keg_pour_clamps_persisted_volume_to_zero(app_client):
    """A manual correction cannot leave a keg with negative stock."""
    test_init()
    batch_id = _create_batch(app_client)
    data = _vessel_data(batch_id)
    data["volumeRemaining"] = 0.25
    vessel_id = app_client.post("/vessels", json=data, headers=headers).json()["id"]

    response = app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 1.0}, headers=headers
    )
    assert response.status_code == 201
    assert response.json()["volumeRemaining"] == 0.0
    vessel = app_client.get(f"/vessels/{vessel_id}", headers=headers).json()
    assert vessel["volumeRemaining"] == 0.0


def test_vessel_bulk_readings_reject_more_than_one_thousand_rows(app_client):
    """Restore/import callers must send bounded chunks rather than one huge transaction."""
    test_init()
    batch_id = _create_batch(app_client)
    vessel_id = app_client.post(
        "/vessels", json=_vessel_data(batch_id), headers=headers
    ).json()["id"]
    response = app_client.post(
        f"/vessels/{vessel_id}/temp/bulk",
        json=[{"temperature": 20.0}] * 1001,
        headers=headers,
    )
    assert response.status_code == 422


def test_record_bottle_pour_publishes_event(app_client):
    """POST /vessels/{id}/pours/bottles publishes a vessel/update SSE event."""
    test_init()
    batch_id = _create_batch(app_client)
    data = _vessel_data(batch_id)
    data["vesselType"] = "bottles"
    data["bottleVolume"] = 0.33
    data["bottlesRemaining"] = 12
    r = app_client.post("/vessels", json=data, headers=headers)
    vessel_id = r.json()["id"]

    with patch("oss.routers.vessel_pours.notify_clients") as mock_notify:
        r2 = app_client.post(
            f"/vessels/{vessel_id}/pours/bottles", json={"bottleCount": 2}, headers=headers
        )
    assert r2.status_code == 201
    mock_notify.assert_called_once_with("vessel", "update", uuid.UUID(vessel_id),
                                         DEFAULT_TENANT_ID, source="vessel")


def test_vessel_temp_404_for_soft_deleted_vessel(app_client):
    """POST/GET vessel temp routes 404 once the vessel is soft-deleted.

    §16/§19: the shared active-parent resolution (`_active_vessel`) applies
    consistently across create/list/chart/bulk/update — a soft-deleted vessel
    is rejected the same way everywhere except `/restore`, whose entire
    purpose is to act on it.
    """
    test_init()
    batch_id = _create_batch(app_client)
    vessel_id = app_client.post(
        "/vessels", json=_vessel_data(batch_id), headers=headers
    ).json()["id"]
    assert app_client.delete(f"/vessels/{vessel_id}", headers=headers).status_code == 204

    assert app_client.post(
        f"/vessels/{vessel_id}/temp", json={"temperature": 18.0}, headers=headers
    ).status_code == 404
    assert app_client.get(f"/vessels/{vessel_id}/temp", headers=headers).status_code == 404
    assert app_client.get(f"/vessels/{vessel_id}/temp/chart", headers=headers).status_code == 404


def test_restore_undoes_a_vessel_delete(app_client):
    """POST /vessels/{id}/restore brings back a soft-deleted vessel."""
    test_init()
    batch_id = _create_batch(app_client)
    created = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = created.json()["id"]

    assert app_client.delete(f"/vessels/{vessel_id}", headers=headers).status_code == 204
    assert app_client.get(f"/vessels/{vessel_id}", headers=headers).status_code == 404

    r = app_client.post(f"/vessels/{vessel_id}/restore", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == vessel_id
    assert app_client.get(f"/vessels/{vessel_id}", headers=headers).status_code == 200


def test_restore_a_live_vessel_is_404(app_client):
    """Restoring something that was never deleted is an error, not a no-op."""
    test_init()
    batch_id = _create_batch(app_client)
    created = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = created.json()["id"]

    r = app_client.post(f"/vessels/{vessel_id}/restore", headers=headers)
    assert r.status_code == 404


def test_create_vessel_rejects_soft_deleted_batch(app_client):
    """POST /vessels with batchId pointing at a soft-deleted batch is rejected.

    A soft-deleted batch still satisfies the FK, so it would otherwise pass
    silently -- it must be rejected the same way an archived batch already is.
    """
    test_init()
    batch_id = _create_batch(app_client)
    assert app_client.delete(f"/batches/{batch_id}", headers=headers).status_code == 204

    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    assert r.status_code == 409


def test_update_vessel_rejects_soft_deleted_batch(app_client):
    """PATCH /vessels/{id} with batchId pointing at a soft-deleted batch is rejected."""
    test_init()
    r = app_client.post("/vessels", json={
        "vesselType": "keg", "name": "Keg", "fillDate": "2026-01-01",
        "totalVolume": 19.0, "volumeRemaining": 0.0, "status": "clean",
    }, headers=headers)
    vessel_id = r.json()["id"]

    other_batch_id = _create_batch(app_client)
    assert app_client.delete(f"/batches/{other_batch_id}", headers=headers).status_code == 204

    r2 = app_client.patch(
        f"/vessels/{vessel_id}", json={"batchId": other_batch_id}, headers=headers
    )
    assert r2.status_code == 409


def test_create_vessel_rejects_soft_deleted_tap(app_client):
    """POST /vessels with tapId pointing at a soft-deleted tap is rejected."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/taps", json={"name": "Tap 1", "tapNumber": 1}, headers=headers)
    tap_id = r.json()["id"]
    assert app_client.delete(f"/taps/{tap_id}", headers=headers).status_code == 204

    data = _vessel_data(batch_id)
    data["tapId"] = tap_id
    r2 = app_client.post("/vessels", json=data, headers=headers)
    assert r2.status_code == 409


def test_update_vessel_rejects_soft_deleted_tap(app_client):
    """PATCH /vessels/{id} with tapId pointing at a soft-deleted tap is rejected."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    r2 = app_client.post("/taps", json={"name": "Tap 1", "tapNumber": 1}, headers=headers)
    tap_id = r2.json()["id"]
    assert app_client.delete(f"/taps/{tap_id}", headers=headers).status_code == 204

    r3 = app_client.patch(f"/vessels/{vessel_id}", json={"tapId": tap_id}, headers=headers)
    assert r3.status_code == 409


def test_create_vessel_rejects_negative_total_volume(app_client):
    """POST /vessels with a negative totalVolume is a 422, not persisted."""
    test_init()
    batch_id = _create_batch(app_client)
    data = _vessel_data(batch_id)
    data["totalVolume"] = -5.0
    r = app_client.post("/vessels", json=data, headers=headers)
    assert r.status_code == 422


def test_create_vessel_rejects_negative_bottle_count(app_client):
    """POST /vessels with a negative bottleCount is a 422."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json={
        "batchId": batch_id, "vesselType": "bottles", "name": "Bottles",
        "fillDate": "2026-02-02", "totalVolume": 9.9, "volumeRemaining": 9.9,
        "bottleCount": -1, "bottlesRemaining": 0, "bottleVolume": 0.33,
    }, headers=headers)
    assert r.status_code == 422


def test_create_vessel_rejects_remaining_over_total(app_client):
    """POST /vessels with volumeRemaining > totalVolume is a 422."""
    test_init()
    batch_id = _create_batch(app_client)
    data = _vessel_data(batch_id)
    data["totalVolume"] = 10.0
    data["volumeRemaining"] = 999.0
    r = app_client.post("/vessels", json=data, headers=headers)
    assert r.status_code == 422


def test_create_vessel_rejects_bottles_remaining_over_count(app_client):
    """POST /vessels with bottlesRemaining > bottleCount is a 422."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json={
        "batchId": batch_id, "vesselType": "bottles", "name": "Bottles",
        "fillDate": "2026-02-02", "totalVolume": 9.9, "volumeRemaining": 9.9,
        "bottleCount": 12, "bottlesRemaining": 50, "bottleVolume": 0.33,
    }, headers=headers)
    assert r.status_code == 422


def test_patch_vessel_rejects_remaining_over_total(app_client):
    """PATCH /vessels/{id} with volumeRemaining > totalVolume in the same
    request is a 422."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    r2 = app_client.patch(
        f"/vessels/{vessel_id}",
        json={"totalVolume": 10.0, "volumeRemaining": 999.0},
        headers=headers,
    )
    assert r2.status_code == 422


def test_patch_vessel_rejects_negative_volume_remaining(app_client):
    """PATCH /vessels/{id} with a negative volumeRemaining is a 422."""
    test_init()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    vessel_id = r.json()["id"]

    r2 = app_client.patch(
        f"/vessels/{vessel_id}", json={"volumeRemaining": -1.0}, headers=headers
    )
    assert r2.status_code == 422
