# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for prediction endpoints."""
import uuid
from datetime import UTC, datetime, timedelta

from core.config import get_settings
from core.db import create_session
from core.enums import PredictionOutcome, PredictionType
from oss.schemas.prediction import PredictionCreate
from oss.services.prediction import PredictionService
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH_DATA = {
    "name": "Prediction Test Batch",
    "status": "fermenting",
    "og": 1.055,
    "fg": 1.010,
}

PREDICTION_DATA = {
    "batchId": None,  # filled in per test
    "outcome": "fermenting",
    "hoursLeft": 24.5,
}


def test_init():
    """Reset database state before the scenario group."""
    truncate_database()


def _svc():
    return PredictionService(create_session())


def _create_batch(app_client) -> str:
    r = app_client.post("/batches", json=BATCH_DATA, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _create_device(app_client) -> str:
    r = app_client.post(
        "/devices",
        json={"name": "PredDev", "deviceType": "gravitymon", "description": "",
              "chipFamily": "ESP32", "collectLogs": False},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


def _create_vessel(app_client, batch_id: str) -> str:
    r = app_client.post(
        "/vessels",
        json={"batchId": batch_id, "vesselNumber": 1, "vesselType": "keg",
              "name": "PredKeg", "fillDate": "2026-05-01",
              "totalVolume": 19.0, "volumeRemaining": 19.0, "status": "filled"},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_no_predictions_returns_empty(app_client):
    """GET /predictions/ for a batch with no predictions returns empty list."""
    test_init()
    batch_id = _create_batch(app_client)

    r2 = app_client.get(f"/predictions/?batchId={batch_id}", headers=headers)
    assert r2.status_code == 200
    assert r2.json() == []


# ---------------------------------------------------------------------------
# GET /api/predictions
# ---------------------------------------------------------------------------

def test_list_all_predictions_empty(app_client):
    """GET /predictions/ returns empty list when no predictions exist."""
    truncate_database()
    r = app_client.get("/predictions", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


def test_list_predictions_filtered_by_batch(app_client):
    """GET /predictions/?batchId= returns only predictions for that batch."""
    truncate_database()
    batch_id = uuid.UUID(_create_batch(app_client))
    other_batch_id = uuid.UUID(_create_batch(app_client))
    svc = _svc()
    svc.create(PredictionCreate(
        batch_id=batch_id,
        prediction_type=PredictionType.FERMENTATION_PROGRESS,
        outcome=PredictionOutcome.FERMENTING,
        hours_left=10.0,
    ))
    svc.create(PredictionCreate(
        batch_id=other_batch_id,
        prediction_type=PredictionType.FERMENTATION_PROGRESS,
        outcome=PredictionOutcome.FERMENTING,
    ))

    r = app_client.get(f"/predictions/?batchId={batch_id}", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["batchId"] == str(batch_id)


def test_list_predictions_filtered_by_device(app_client):
    """GET /predictions/?deviceId= returns only predictions for that device."""
    truncate_database()
    device_id = uuid.UUID(_create_device(app_client))
    svc = _svc()
    svc.create(PredictionCreate(
        device_id=device_id,
        prediction_type=PredictionType.BATTERY_LOW,
        outcome=PredictionOutcome.BATTERY_OK,
    ))
    other_device_id = uuid.UUID(_create_device(app_client))
    svc.create(PredictionCreate(
        device_id=other_device_id,
        prediction_type=PredictionType.BATTERY_LOW,
        outcome=PredictionOutcome.BATTERY_LOW,
    ))

    r = app_client.get(f"/predictions/?deviceId={device_id}", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["deviceId"] == str(device_id)


def test_list_predictions_filtered_by_vessel(app_client):
    """GET /predictions/?vesselId= returns only predictions for that vessel."""
    truncate_database()
    batch_id = _create_batch(app_client)
    vessel_id = uuid.UUID(_create_vessel(app_client, batch_id))
    svc = _svc()
    svc.create(PredictionCreate(
        vessel_id=vessel_id,
        prediction_type=PredictionType.KEG_EMPTY,
        outcome=PredictionOutcome.KEG_OK,
        hours_left=72.0,
    ))
    other_batch_id = _create_batch(app_client)
    other_vessel_id = uuid.UUID(_create_vessel(app_client, other_batch_id))
    svc.create(PredictionCreate(
        vessel_id=other_vessel_id,
        prediction_type=PredictionType.KEG_EMPTY,
        outcome=PredictionOutcome.KEG_LOW,
    ))

    r = app_client.get(f"/predictions/?vesselId={vessel_id}", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["vesselId"] == str(vessel_id)


def test_list_predictions_filtered_by_type(app_client):
    """GET /predictions/?type= returns only predictions of that type."""
    truncate_database()
    device_id = uuid.UUID(_create_device(app_client))
    svc = _svc()
    svc.create(PredictionCreate(
        device_id=device_id,
        prediction_type=PredictionType.BATTERY_LOW,
        outcome=PredictionOutcome.BATTERY_OK,
    ))
    batch_id = uuid.UUID(_create_batch(app_client))
    svc.create(PredictionCreate(
        batch_id=batch_id,
        prediction_type=PredictionType.FERMENTATION_PROGRESS,
        outcome=PredictionOutcome.FERMENTING,
    ))

    r = app_client.get("/predictions/?type=battery_low", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert all(i["predictionType"] == "battery_low" for i in items)


def test_device_predictions_via_filter(app_client):
    """GET /predictions/?deviceId= returns predictions for that device."""
    truncate_database()
    device_id = uuid.UUID(_create_device(app_client))
    _svc().create(PredictionCreate(
        device_id=device_id,
        prediction_type=PredictionType.BATTERY_LOW,
        outcome=PredictionOutcome.BATTERY_OK,
    ))

    r = app_client.get(f"/predictions/?deviceId={device_id}", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["deviceId"] == str(device_id)


def test_vessel_predictions_via_filter(app_client):
    """GET /predictions/?vesselId= returns predictions for that vessel."""
    truncate_database()
    batch_id = _create_batch(app_client)
    vessel_id = uuid.UUID(_create_vessel(app_client, batch_id))
    _svc().create(PredictionCreate(
        vessel_id=vessel_id,
        prediction_type=PredictionType.KEG_EMPTY,
        outcome=PredictionOutcome.KEG_OK,
        hours_left=48.0,
    ))

    r = app_client.get(f"/predictions/?vesselId={vessel_id}", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["vesselId"] == str(vessel_id)
    assert items[0]["hoursLeft"] == 48.0


# ---------------------------------------------------------------------------
# PredictionService unit tests — hasattr guard branches
# ---------------------------------------------------------------------------

def test_latest_for_batch_returns_none_when_empty():
    """latest_for_batch returns None for a batch with no predictions."""
    svc = PredictionService(create_session())
    result = svc.latest_for_batch(uuid.uuid4())
    assert result is None


def test_latest_for_device_returns_none_when_no_attr():
    """latest_for_device returns None when model lacks device_id."""
    from unittest.mock import patch  # pylint: disable=import-outside-toplevel
    import oss.services.prediction as pred_mod  # pylint: disable=import-outside-toplevel
    fake_model = type("FakePrediction", (), {"batch_id": None})
    with patch.object(pred_mod, "Prediction", fake_model):
        svc = PredictionService.__new__(PredictionService)
        result = svc.latest_for_device(uuid.uuid4())
    assert result is None


def test_history_for_device_returns_empty_when_no_attr():
    """history_for_device returns [] when model lacks device_id."""
    from unittest.mock import patch  # pylint: disable=import-outside-toplevel
    import oss.services.prediction as pred_mod  # pylint: disable=import-outside-toplevel
    fake_model = type("FakePrediction", (), {"batch_id": None})
    with patch.object(pred_mod, "Prediction", fake_model):
        svc = PredictionService.__new__(PredictionService)
        result = svc.history_for_device(uuid.uuid4())
    assert not result


def test_latest_for_vessel_returns_none_when_no_attr():
    """latest_for_vessel returns None when model lacks vessel_id."""
    from unittest.mock import patch  # pylint: disable=import-outside-toplevel
    import oss.services.prediction as pred_mod  # pylint: disable=import-outside-toplevel
    fake_model = type("FakePrediction", (), {"batch_id": None})
    with patch.object(pred_mod, "Prediction", fake_model):
        svc = PredictionService.__new__(PredictionService)
        result = svc.latest_for_vessel(uuid.uuid4())
    assert result is None


def test_history_for_vessel_returns_empty_when_no_attr():
    """history_for_vessel returns [] when model lacks vessel_id."""
    from unittest.mock import patch  # pylint: disable=import-outside-toplevel
    import oss.services.prediction as pred_mod  # pylint: disable=import-outside-toplevel
    fake_model = type("FakePrediction", (), {"batch_id": None})
    with patch.object(pred_mod, "Prediction", fake_model):
        svc = PredictionService.__new__(PredictionService)
        result = svc.history_for_vessel(uuid.uuid4())
    assert not result


def _seed(session, **kwargs):
    """Persist one prediction, defaulting the fields every row needs."""
    payload = {
        "outcome": PredictionOutcome.FERMENTING,
        "prediction_type": PredictionType.FERMENTATION_PROGRESS,
    }
    payload.update(kwargs)
    return PredictionService(session).create(PredictionCreate(**payload))


def test_delete_prediction_hides_it_everywhere(app_client):
    """DELETE soft-deletes: the row stops appearing in every read path."""
    truncate_database()
    session = create_session()
    batch_id = uuid.UUID(
        app_client.post("/batches", json=BATCH_DATA, headers=headers).json()["id"]
    )
    prediction = _seed(session, batch_id=batch_id)

    assert app_client.get(
        f"/predictions?batchId={batch_id}", headers=headers
    ).json()

    r = app_client.delete(f"/predictions/{prediction.id}", headers=headers)
    assert r.status_code == 204

    assert app_client.get(f"/predictions?batchId={batch_id}", headers=headers).json() == []
    assert app_client.get(f"/batches/{batch_id}/predictions", headers=headers).json()["items"] == []

    dashboard = app_client.get("/dashboard", headers=headers).json()
    for entry in dashboard.get("batches", []):
        assert entry.get("predictions") == []


def test_dashboard_exposes_only_the_latest_prediction_per_batch(app_client):
    """Dashboard summaries stay bounded even when historical rows exist."""
    truncate_database()
    session = create_session()
    batch_id = uuid.UUID(
        app_client.post("/batches", json=BATCH_DATA, headers=headers).json()["id"]
    )
    oldest = _seed(session, batch_id=batch_id)
    newest = _seed(session, batch_id=batch_id)
    now = datetime.now(UTC)
    oldest.created_at = now - timedelta(minutes=1)
    newest.created_at = now
    session.commit()

    dashboard = app_client.get("/dashboard", headers=headers).json()
    batch = next(item for item in dashboard["batches"] if item["id"] == str(batch_id))

    assert [prediction["id"] for prediction in batch["predictions"]] == [newest.id]


def test_delete_prediction_twice_is_404(app_client):
    """A prediction already dismissed cannot be dismissed again."""
    truncate_database()
    session = create_session()
    prediction = _seed(session)

    assert app_client.delete(f"/predictions/{prediction.id}", headers=headers).status_code == 204
    assert app_client.delete(f"/predictions/{prediction.id}", headers=headers).status_code == 404


def test_no_patch_endpoint_for_predictions(app_client):
    """Predictions are model output: they can be dismissed, never edited."""
    truncate_database()
    session = create_session()
    prediction = _seed(session)

    r = app_client.patch(
        f"/predictions/{prediction.id}", json={"outcome": "complete"}, headers=headers
    )
    assert r.status_code in (404, 405)


def test_prediction_sub_resource_per_entity(app_client):
    """Devices, taps and vessels each expose their own prediction history."""
    truncate_database()
    session = create_session()

    device = app_client.post(
        "/devices", json={"name": "Pill", "deviceType": "gravitymon"}, headers=headers
    ).json()
    tap = app_client.post("/taps", json={"name": "Tap 1"}, headers=headers).json()

    _seed(session, device_id=uuid.UUID(device["id"]),
          prediction_type=PredictionType.BATTERY_LOW,
          outcome=PredictionOutcome.BATTERY_LOW)
    _seed(session, tap_id=uuid.UUID(tap["id"]))

    device_history = app_client.get(f"/devices/{device['id']}/predictions", headers=headers)
    assert device_history.status_code == 200
    assert len(device_history.json()["items"]) == 1

    tap_history = app_client.get(f"/taps/{tap['id']}/predictions", headers=headers)
    assert tap_history.status_code == 200
    assert len(tap_history.json()["items"]) == 1


def test_tap_predictions_do_not_leak_across_taps(app_client):
    """A tap-scoped prediction belongs to its own tap, not to whatever keg is on it."""
    truncate_database()
    session = create_session()
    tap_a = app_client.post("/taps", json={"name": "A"}, headers=headers).json()
    tap_b = app_client.post("/taps", json={"name": "B"}, headers=headers).json()
    _seed(session, tap_id=uuid.UUID(tap_a["id"]))

    on_a = app_client.get(f"/taps/{tap_a['id']}/predictions", headers=headers).json()
    on_b = app_client.get(f"/taps/{tap_b['id']}/predictions", headers=headers).json()
    assert len(on_a["items"]) == 1
    assert on_b["items"] == []


def test_details_defaults_to_an_empty_object(app_client):
    """`details` is always present, so consumers never branch on absent-vs-empty."""
    truncate_database()
    session = create_session()
    prediction = _seed(session)

    session.refresh(prediction)
    assert prediction.details == {}

    listed = app_client.get("/predictions", headers=headers).json()
    assert listed[0]["details"] == {}


def test_restore_undoes_a_dismissal(app_client):
    """POST /predictions/{id}/restore puts a dismissed prediction back."""
    truncate_database()
    session = create_session()
    batch_id = uuid.UUID(
        app_client.post("/batches", json=BATCH_DATA, headers=headers).json()["id"]
    )
    prediction = _seed(session, batch_id=batch_id)

    assert app_client.delete(f"/predictions/{prediction.id}", headers=headers).status_code == 204
    assert app_client.get(f"/predictions?batchId={batch_id}", headers=headers).json() == []

    r = app_client.post(f"/predictions/{prediction.id}/restore", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == prediction.id
    listed = app_client.get(f"/predictions?batchId={batch_id}", headers=headers).json()
    assert len(listed) == 1


def test_restore_a_live_prediction_is_404(app_client):
    """Restoring something that was never dismissed is a 404, not a silent no-op."""
    truncate_database()
    session = create_session()
    prediction = _seed(session)
    r = app_client.post(f"/predictions/{prediction.id}/restore", headers=headers)
    assert r.status_code == 404


def test_prediction_history_is_cursor_paginated(app_client):
    """Per-entity prediction history pages, newest first."""
    truncate_database()
    session = create_session()
    batch_id = uuid.UUID(
        app_client.post("/batches", json=BATCH_DATA, headers=headers).json()["id"]
    )
    for _ in range(3):
        _seed(session, batch_id=batch_id)

    first = app_client.get(
        f"/batches/{batch_id}/predictions?limit=2", headers=headers
    ).json()
    assert len(first["items"]) == 2
    assert first["hasMore"] is True

    second = app_client.get(
        f"/batches/{batch_id}/predictions?limit=2&cursor={first['nextCursor']}",
        headers=headers,
    ).json()
    assert len(second["items"]) == 1
    assert second["hasMore"] is False

    seen = [i["id"] for i in first["items"]] + [i["id"] for i in second["items"]]
    assert len(set(seen)) == 3


def test_tap_prediction_history_is_cursor_paginated(app_client):
    """Regression: tap prediction history's next_cursor must decode on page 2.

    `get_tap_predictions` used to build `next_cursor` with a bare
    `.isoformat()` instead of `encode_cursor`, so the first page looked fine
    but following the returned cursor into a second request always 400'd.
    """
    truncate_database()
    session = create_session()
    tap = app_client.post("/taps", json={"name": "Cursor Tap"}, headers=headers).json()
    tap_id = uuid.UUID(tap["id"])
    for _ in range(3):
        _seed(session, tap_id=tap_id)

    first = app_client.get(
        f"/taps/{tap_id}/predictions?limit=2", headers=headers
    ).json()
    assert len(first["items"]) == 2
    assert first["hasMore"] is True

    second = app_client.get(
        f"/taps/{tap_id}/predictions?limit=2&cursor={first['nextCursor']}",
        headers=headers,
    )
    assert second.status_code == 200
    second_body = second.json()
    assert len(second_body["items"]) == 1
    assert second_body["hasMore"] is False

    seen = [i["id"] for i in first["items"]] + [i["id"] for i in second_body["items"]]
    assert len(set(seen)) == 3


def test_vessel_prediction_history_is_cursor_paginated(app_client):
    """Regression: vessel prediction history's next_cursor must decode on page 2.

    Same bare-`.isoformat()` bug as `get_tap_predictions`, in
    `get_vessel_predictions`.
    """
    truncate_database()
    session = create_session()
    batch_id = uuid.UUID(
        app_client.post("/batches", json=BATCH_DATA, headers=headers).json()["id"]
    )
    vessel_id = uuid.UUID(_create_vessel(app_client, str(batch_id)))
    for _ in range(3):
        _seed(session, vessel_id=vessel_id)

    first = app_client.get(
        f"/vessels/{vessel_id}/predictions?limit=2", headers=headers
    ).json()
    assert len(first["items"]) == 2
    assert first["hasMore"] is True

    second = app_client.get(
        f"/vessels/{vessel_id}/predictions?limit=2&cursor={first['nextCursor']}",
        headers=headers,
    )
    assert second.status_code == 200
    second_body = second.json()
    assert len(second_body["items"]) == 1
    assert second_body["hasMore"] is False

    seen = [i["id"] for i in first["items"]] + [i["id"] for i in second_body["items"]]
    assert len(set(seen)) == 3
