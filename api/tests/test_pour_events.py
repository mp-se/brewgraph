# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for pour event endpoints."""
import uuid
from urllib.parse import quote

from core.config import get_settings
from core.db import create_session
from core.models.registry import resolve_model
from oss.services.pour_event import PourEventService
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def _setup(app_client) -> str:
    """Create a batch and a keg vessel, return vessel_id."""
    truncate_database()
    batch_id = app_client.post(
        "/batches", json={"name": "Pour Test Batch", "status": "packaged"}, headers=headers
    ).json()["id"]
    vessel_id = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselType": "keg",
            "name": "Test Keg",
            "fillDate": "2026-05-01",
            "totalVolume": 19.0,
            "volumeRemaining": 19.0,
            "status": "serving",
        },
        headers=headers,
    ).json()["id"]
    return vessel_id


def _setup_tapped_vessel(app_client) -> tuple:
    """Create a batch, a tap, and a keg vessel assigned to that tap."""
    vessel_id = _setup(app_client)
    tap_id = app_client.post("/taps", json={"name": "Counter Tap"}, headers=headers).json()["id"]
    app_client.patch(f"/vessels/{vessel_id}", json={"tapId": tap_id}, headers=headers)
    return vessel_id, tap_id


def _tap_counters(tap_id):
    """Read Tap.total_volume_poured directly (not on TapResponse)."""
    tap_model = resolve_model("Tap")
    s = create_session()
    try:
        tap = s.get(tap_model, uuid.UUID(tap_id))
        return tap.total_volume_poured
    finally:
        s.remove()


def _pour_event(vessel_id, pour_id):
    """Fetch one PourEvent row directly (tap_id is not on PourEventResponse)."""
    s = create_session()
    try:
        events = PourEventService(s).list_for_vessel(uuid.UUID(vessel_id))
        return next(e.tap_id for e in events if str(e.id) == pour_id)
    finally:
        s.remove()


def test_list_pours_empty(app_client):
    """GET /vessels/{id}/pours returns an empty cursor page when no pours exist."""
    vessel_id = _setup(app_client)
    r = app_client.get(f"/vessels/{vessel_id}/pours", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["hasMore"] is False


def test_record_pour(app_client):
    """POST /vessels/{id}/pours records a pour and returns updated volume."""
    vessel_id = _setup(app_client)
    r = app_client.post(
        f"/vessels/{vessel_id}/pours",
        json={"pourAmount": 0.5},
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["pourAmount"] == 0.5
    assert data["volumeRemaining"] == 18.5
    assert "id" in data


def test_pour_can_be_dated(app_client):
    """A pour or a bottle pour logged with createdAt is stored at that time; without it, now."""
    vessel_id = _setup(app_client)
    when = "2026-03-02T18:30:00Z"
    r = app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.5, "createdAt": when}, headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["createdAt"].startswith("2026-03-02T18:30:00")

    now_pour = app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.5}, headers=headers,
    ).json()
    assert not now_pour["createdAt"].startswith("2026-03-02")

    bottles = _setup_bottle_vessel(app_client)
    r = app_client.post(
        f"/vessels/{bottles}/pours/bottles", json={"bottleCount": 1, "createdAt": when}, headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["createdAt"].startswith("2026-03-02T18:30:00")


def test_pour_decrements_volume(app_client):
    """Multiple pours cumulatively decrement the vessel's volume_remaining."""
    vessel_id = _setup(app_client)
    app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 1.0}, headers=headers
    )
    app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 2.0}, headers=headers
    )

    r = app_client.get(f"/vessels/{vessel_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["volumeRemaining"] == 16.0


def test_pour_list_oldest_first(app_client):
    """GET /vessels/{id}/pours returns pours oldest-first.

    Pagination is always ascending (created_at ASC), oldest first, per the
    API's cursor contract. The UI sorts for display instead.
    """
    vessel_id = _setup(app_client)
    for amount in [0.3, 0.5, 1.0]:
        app_client.post(
            f"/vessels/{vessel_id}/pours", json={"pourAmount": amount}, headers=headers
        )

    r = app_client.get(f"/vessels/{vessel_id}/pours", headers=headers)
    pours = r.json()["items"]
    assert len(pours) == 3
    assert pours[0]["pourAmount"] == 0.3
    assert pours[-1]["pourAmount"] == 1.0


def test_pour_list_pagination(app_client):
    """GET /vessels/{id}/pours?limit=2 returns correct cursor page."""
    vessel_id = _setup(app_client)
    for amount in [0.3, 0.5, 1.0]:
        app_client.post(
            f"/vessels/{vessel_id}/pours", json={"pourAmount": amount}, headers=headers
        )

    r = app_client.get(f"/vessels/{vessel_id}/pours?limit=2", headers=headers)
    body = r.json()
    assert len(body["items"]) == 2
    assert body["hasMore"] is True
    assert body["nextCursor"] is not None

    r2 = app_client.get(
        f"/vessels/{vessel_id}/pours?limit=2&cursor={quote(body['nextCursor'])}",
        headers=headers,
    )
    body2 = r2.json()
    assert len(body2["items"]) == 1
    assert body2["hasMore"] is False


def test_pour_on_bottle_vessel_rejected(app_client):
    """POST /vessels/{id}/pours returns 400 when the vessel is a bottle batch."""
    truncate_database()
    batch_id = app_client.post(
        "/batches", json={"name": "Bottle Batch", "status": "packaged"}, headers=headers
    ).json()["id"]
    vessel_id = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselType": "bottles",
            "name": "330ml bottles",
            "fillDate": "2026-05-01",
            "totalVolume": 10.0,
            "volumeRemaining": 10.0,
        },
        headers=headers,
    ).json()["id"]

    r = app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.33}, headers=headers
    )
    assert r.status_code == 400


def _setup_bottle_vessel(app_client) -> str:
    """Create a batch and a bottle vessel with bottle_volume and bottles_remaining."""
    truncate_database()
    batch_id = app_client.post(
        "/batches", json={"name": "Bottle Batch", "status": "packaged"}, headers=headers
    ).json()["id"]
    vessel_id = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselType": "bottles",
            "name": "330ml Bottles",
            "fillDate": "2026-05-01",
            "totalVolume": 9.9,
            "volumeRemaining": 9.9,
            "bottleVolume": 0.33,
            "bottlesRemaining": 30,
        },
        headers=headers,
    ).json()["id"]
    return vessel_id



def test_pour_not_found(app_client):
    """POST /vessels/{bad_id}/pours returns 404 when vessel does not exist."""
    _setup(app_client)
    r = app_client.post(
        f"/vessels/{uuid.uuid4()}/pours", json={"pourAmount": 0.5}, headers=headers
    )
    assert r.status_code == 404


def test_record_bottle_pour(app_client):
    """POST /vessels/{id}/pours/bottles decrements bottles_remaining and volume."""
    vessel_id = _setup_bottle_vessel(app_client)
    r = app_client.post(
        f"/vessels/{vessel_id}/pours/bottles",
        json={"bottleCount": 2},
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["isManual"] is True
    assert round(data["pourAmount"], 4) == round(2 * 0.33, 4)


def test_bottle_pour_on_keg_rejected(app_client):
    """POST /vessels/{id}/pours/bottles returns 400 for a keg vessel."""
    vessel_id = _setup(app_client)
    r = app_client.post(
        f"/vessels/{vessel_id}/pours/bottles",
        json={"bottleCount": 1},
        headers=headers,
    )
    assert r.status_code == 400


def test_bottle_pour_not_found(app_client):
    """POST /vessels/{bad_id}/pours/bottles returns 404 when vessel does not exist."""
    _setup(app_client)
    r = app_client.post(
        f"/vessels/{uuid.uuid4()}/pours/bottles",
        json={"bottleCount": 1},
        headers=headers,
    )
    assert r.status_code == 404


def test_bulk_insert_pours(app_client):
    """POST /vessels/{id}/pours/bulk inserts historical pour records."""
    vessel_id = _setup(app_client)
    rows = [
        {"pourAmount": 0.5, "volumeRemaining": 18.5, "isManual": False,
         "createdAt": "2026-01-01T12:00:00Z"},
        {"pourAmount": 1.0, "volumeRemaining": 17.5, "isManual": True,
         "createdAt": "2026-01-02T12:00:00Z"},
    ]
    r = app_client.post(
        f"/vessels/{vessel_id}/pours/bulk", json=rows, headers=headers
    )
    assert r.status_code == 201
    data = r.json()
    assert len(data) == 2
    amounts = {d["pourAmount"] for d in data}
    assert amounts == {0.5, 1.0}


def test_pour_drains_keg_to_empty(app_client):
    """Pouring the full volume brings volumeRemaining to 0 and unassigns the tap."""
    vessel_id = _setup(app_client)
    tap_id = app_client.post("/taps", json={"name": "Drain Tap"}, headers=headers).json()["id"]
    app_client.patch(f"/vessels/{vessel_id}", json={"tapId": tap_id}, headers=headers)

    r = app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 19.0}, headers=headers
    )
    assert r.status_code == 201
    assert r.json()["volumeRemaining"] == 0.0
    vessel = app_client.get(f"/vessels/{vessel_id}", headers=headers).json()
    assert vessel["volumeRemaining"] == 0.0
    assert vessel["tapId"] is None  # tap unassigned when depleted
    assert vessel["status"] == "serving"  # empty is computed, not stored


def test_bottle_pour_drains_to_empty(app_client):
    """Consuming all bottles brings volumeRemaining to 0; status unchanged (empty is computed)."""
    vessel_id = _setup_bottle_vessel(app_client)
    r = app_client.post(
        f"/vessels/{vessel_id}/pours/bottles",
        json={"bottleCount": 30},
        headers=headers,
    )
    assert r.status_code == 201
    vessel = app_client.get(f"/vessels/{vessel_id}", headers=headers).json()
    assert vessel["volumeRemaining"] == 0.0
    assert vessel["status"] == "filled"  # status unchanged; empty is computed


def test_bottle_pour_no_bottle_volume(app_client):
    """POST /vessels/{id}/pours/bottles returns 400 when bottle_volume is not set."""
    truncate_database()
    batch_id = app_client.post(
        "/batches", json={"name": "No-Vol Batch", "status": "packaged"}, headers=headers
    ).json()["id"]
    vessel_id = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselType": "bottles",
            "name": "Bottles without volume",
            "fillDate": "2026-05-01",
            "totalVolume": 5.0,
            "volumeRemaining": 5.0,
            "bottlesRemaining": 10,
        },
        headers=headers,
    ).json()["id"]
    r = app_client.post(
        f"/vessels/{vessel_id}/pours/bottles",
        json={"bottleCount": 1},
        headers=headers,
    )
    assert r.status_code == 400


def test_list_vessels_empty_covers_count_shortcut(app_client):
    """GET /vessels/ with no vessels exercises count_by_vessel_ids([]) early-return."""
    truncate_database()
    r = app_client.get("/vessels", headers=headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_latest_global_pours(app_client):
    """PourEventService.latest_global returns most recent pour events across all vessels."""
    vessel_id = _setup(app_client)
    for amount in [0.3, 0.5, 1.0]:
        app_client.post(
            f"/vessels/{vessel_id}/pours", json={"pourAmount": amount}, headers=headers
        )
    s = create_session()
    try:
        results = PourEventService(s).latest_global(limit=2)
        assert len(results) == 2
    finally:
        s.remove()


def test_count_by_batch_ids_direct(app_client):
    """PourEventService.count_by_batch_ids returns correct count per batch."""
    truncate_database()
    batch_id_str = app_client.post(
        "/batches", json={"name": "Count Batch"}, headers=headers
    ).json()["id"]
    batch_id = uuid.UUID(batch_id_str)
    vessel_id = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id_str,
            "vesselType": "keg",
            "name": "Count Keg",
            "fillDate": "2026-05-01",
            "totalVolume": 10.0,
            "volumeRemaining": 10.0,
            "status": "serving",
        },
        headers=headers,
    ).json()["id"]
    app_client.post(f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.5}, headers=headers)
    app_client.post(f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.5}, headers=headers)

    s = create_session()
    try:
        counts = PourEventService(s).count_by_batch_ids([batch_id])
        assert counts.get(batch_id, 0) == 2
        # Empty list returns early with empty dict
        assert PourEventService(s).count_by_batch_ids([]) == {}
    finally:
        s.remove()


def test_toggle_pour_excluded(app_client):
    """PATCH /vessels/{id}/pours/{pour_id} toggles the excluded flag."""
    vessel_id = _setup(app_client)
    pour_id = app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.5}, headers=headers
    ).json()["id"]

    r = app_client.patch(f"/vessels/{vessel_id}/pours/{pour_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["excluded"] is True

    r2 = app_client.patch(f"/vessels/{vessel_id}/pours/{pour_id}", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["excluded"] is False


def test_toggle_pour_excluded_not_found(app_client):
    """PATCH /vessels/{id}/pours/{bad_pour_id} returns 404."""
    vessel_id = _setup(app_client)
    r = app_client.patch(f"/vessels/{vessel_id}/pours/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404


def test_bottle_pour_no_bottles_remaining(app_client):
    """POST /vessels/{id}/pours/bottles returns 400 when bottles_remaining is None."""
    truncate_database()
    batch_id = app_client.post(
        "/batches", json={"name": "No Remaining", "status": "packaged"}, headers=headers
    ).json()["id"]
    vessel_id = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselType": "bottles",
            "name": "Bottles no remaining",
            "fillDate": "2026-05-01",
            "totalVolume": 5.0,
            "volumeRemaining": 5.0,
            "bottleVolume": 0.33,
        },
        headers=headers,
    ).json()["id"]
    r = app_client.post(
        f"/vessels/{vessel_id}/pours/bottles",
        json={"bottleCount": 1},
        headers=headers,
    )
    assert r.status_code == 400


def test_pour_advances_tap_throughput_counter(app_client):
    """A pour through a tapped keg advances Tap.total_volume_poured."""
    vessel_id, tap_id = _setup_tapped_vessel(app_client)
    app_client.post(f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.5}, headers=headers)
    app_client.post(f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.3}, headers=headers)

    assert round(_tap_counters(tap_id), 4) == 0.8


def test_pour_on_untapped_vessel_does_not_touch_any_counter(app_client):
    """A pour through a vessel with no tap assigned raises no error and no orphan write."""
    vessel_id = _setup(app_client)
    r = app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.5}, headers=headers
    )
    assert r.status_code == 201


def test_bottle_pour_advances_tap_throughput_counter_when_tapped(app_client):
    """record_bottle_pour advances the same counter as record_pour when tapped."""
    truncate_database()
    batch_id = app_client.post(
        "/batches", json={"name": "Bottle Tap Batch", "status": "packaged"}, headers=headers
    ).json()["id"]
    vessel_id = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselType": "bottles",
            "name": "330ml bottles",
            "fillDate": "2026-05-01",
            "totalVolume": 9.9,
            "volumeRemaining": 9.9,
            "bottleVolume": 0.33,
            "bottlesRemaining": 30,
        },
        headers=headers,
    ).json()["id"]
    tap_id = app_client.post("/taps", json={"name": "Bottle Tap"}, headers=headers).json()["id"]
    app_client.patch(f"/vessels/{vessel_id}", json={"tapId": tap_id}, headers=headers)

    app_client.post(
        f"/vessels/{vessel_id}/pours/bottles", json={"bottleCount": 2}, headers=headers
    )
    assert round(_tap_counters(tap_id), 4) == round(2 * 0.33, 4)


def test_excluding_a_pour_removes_it_from_the_tap_counter(app_client):
    """Toggling excluded on/off adjusts the tap's throughput counter accordingly.

    An excluded pour is judged not to have really happened, so it shouldn't
    count.
    """
    vessel_id, tap_id = _setup_tapped_vessel(app_client)
    pour_id = app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.5}, headers=headers
    ).json()["id"]
    assert round(_tap_counters(tap_id), 4) == 0.5

    r = app_client.patch(f"/vessels/{vessel_id}/pours/{pour_id}", headers=headers)
    assert r.json()["excluded"] is True
    assert _tap_counters(tap_id) == 0.0

    r2 = app_client.patch(f"/vessels/{vessel_id}/pours/{pour_id}", headers=headers)
    assert r2.json()["excluded"] is False
    assert round(_tap_counters(tap_id), 4) == 0.5


def test_pour_event_tap_id_stamped_from_vessel(app_client):
    """PourEvent.tap_id is stamped from the vessel's tap at pour time."""
    vessel_id, tap_id = _setup_tapped_vessel(app_client)
    pour_id = app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.5}, headers=headers
    ).json()["id"]

    assert str(_pour_event(vessel_id, pour_id)) == tap_id


def test_pour_event_tap_id_survives_vessel_being_unassigned(app_client):
    """PourEvent.tap_id stays set even after the vessel drains and loses its tap.

    record_pour clears StorageVessel.tap_id on drain-to-empty, but the pour
    still went through this tap -- the stamped id must not follow it to None.
    """
    vessel_id, tap_id = _setup_tapped_vessel(app_client)
    pour_id = app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 19.0}, headers=headers
    ).json()["id"]

    vessel = app_client.get(f"/vessels/{vessel_id}", headers=headers).json()
    assert vessel["tapId"] is None  # confirms the drain-to-empty branch fired

    assert str(_pour_event(vessel_id, pour_id)) == tap_id


def test_pour_event_tap_id_is_null_when_vessel_has_no_tap(app_client):
    """A pour recorded against an untapped vessel stamps a null tap_id."""
    vessel_id = _setup(app_client)
    pour_id = app_client.post(
        f"/vessels/{vessel_id}/pours", json={"pourAmount": 0.5}, headers=headers
    ).json()["id"]

    assert _pour_event(vessel_id, pour_id) is None
