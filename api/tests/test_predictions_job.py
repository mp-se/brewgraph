# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for core/jobs/predictions.py — ML prediction background job."""
from unittest.mock import MagicMock, patch

import pytest

from core.config import get_settings
from core.enums import PredictionOutcome
from oss.jobs.predictions import _hours_left_to_outcome, task_update_predictions
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


# ---------------------------------------------------------------------------
# _hours_left_to_outcome
# ---------------------------------------------------------------------------

class TestHoursLeftToOutcome:
    """Tests for the _hours_left_to_outcome classification function."""

    def test_none_returns_fermenting(self):
        """Returns FERMENTING when hours_left is None (no prediction yet)."""
        assert _hours_left_to_outcome(None) == PredictionOutcome.FERMENTING

    def test_zero_returns_complete(self):
        """Returns COMPLETE when hours_left is 0."""
        assert _hours_left_to_outcome(0.0) == PredictionOutcome.COMPLETE

    def test_half_hour_returns_complete(self):
        """Returns COMPLETE when hours_left is less than 1."""
        assert _hours_left_to_outcome(0.5) == PredictionOutcome.COMPLETE

    def test_one_hour_returns_done_soon(self):
        """Returns DONE_SOON at exactly 1 hour remaining."""
        assert _hours_left_to_outcome(1.0) == PredictionOutcome.DONE_SOON

    def test_two_hours_returns_done_soon(self):
        """Returns DONE_SOON within the 1-2 hour range."""
        assert _hours_left_to_outcome(2.0) == PredictionOutcome.DONE_SOON

    def test_twelve_hours_returns_near_done(self):
        """Returns NEAR_DONE at 12 hours remaining."""
        assert _hours_left_to_outcome(12.0) == PredictionOutcome.NEAR_DONE

    def test_twenty_four_hours_returns_near_done(self):
        """Returns NEAR_DONE at 24 hours remaining."""
        assert _hours_left_to_outcome(24.0) == PredictionOutcome.NEAR_DONE

    def test_forty_eight_hours_returns_fermenting(self):
        """Returns FERMENTING when more than 24 hours remain."""
        assert _hours_left_to_outcome(48.0) == PredictionOutcome.FERMENTING


# ---------------------------------------------------------------------------
# task_update_predictions — integration with real DB
# ---------------------------------------------------------------------------

def test_init():
    """Truncate the database before integration tests."""
    truncate_database()


@pytest.mark.asyncio
async def test_task_no_accepting_batches():
    """Job exits early and does not crash when no batches accept ingest."""
    test_init()
    await task_update_predictions()


@pytest.mark.asyncio
async def test_task_batch_with_too_few_readings(app_client):
    """Job skips batches with fewer than 2 gravity readings."""
    test_init()
    app_client.post(
        "/batches", json={"name": "FewReadings", "acceptIngest": True}, headers=headers
    )
    await task_update_predictions()


@pytest.mark.asyncio
async def test_task_runs_prediction_and_persists(app_client):
    """Job runs the predictor and saves a Prediction row when ≥2 readings exist."""
    test_init()
    batch = app_client.post("/batches", json={
        "name": "PredBatch", "acceptIngest": True, "og": 1.060, "fg": 1.012,
    }, headers=headers).json()
    batch_id = batch["id"]

    dev = app_client.post("/devices", json={
        "name": "PredDev", "deviceType": "gravitymon", "chipId": "PRD01",
        "mdns": "", "description": "",
        "chipFamily": "ESP32", "url": "", "config": "", "collectLogs": False,
    }, headers=headers).json()

    for i, (grav, temp) in enumerate([(1.060, 20.0), (1.050, 20.5), (1.040, 21.0)]):
        app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[{
            "batchId": batch_id,
            "deviceId": dev["id"],
            "gravity": grav,
            "temperature": temp,
            "battery": 3.8,
            "rssi": -65,
            "angle": 30.0,
            "excluded": False,
            "createdAt": f"2024-01-0{i + 1}T12:00:00",
        }], headers=headers)

    mock_predictor = MagicMock()
    mock_predictor.predict.return_value = 10.0

    with patch("oss.jobs.predictions._get_predictor", return_value=mock_predictor):
        await task_update_predictions()
        await task_update_predictions()

    r = app_client.get(f"/predictions/?batchId={batch_id}", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    mock_predictor.predict.assert_called_once()

    packaged = app_client.patch(
        f"/batches/{batch_id}", json={"status": "packaged"}, headers=headers
    )
    assert packaged.status_code == 200
    with patch("oss.jobs.predictions._get_predictor", return_value=mock_predictor):
        await task_update_predictions()
    assert mock_predictor.predict.call_count == 1


@pytest.mark.asyncio
async def test_task_skips_batch_with_no_fg(app_client):
    """Job skips a batch whose fg is None — no prediction written."""
    truncate_database()
    batch = app_client.post("/batches", json={
        "name": "NoFG", "acceptIngest": True, "og": 1.060,
    }, headers=headers).json()
    batch_id = batch["id"]

    dev = app_client.post("/devices", json={
        "name": "NoFGDev", "deviceType": "gravitymon", "chipId": "NOFG1",
        "mdns": "", "description": "",
        "chipFamily": "ESP32", "url": "", "config": "", "collectLogs": False,
    }, headers=headers).json()

    for i, grav in enumerate([1.060, 1.050, 1.040]):
        app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[{
            "batchId": batch_id,
            "deviceId": dev["id"],
            "gravity": grav,
            "temperature": 20.0,
            "battery": 3.8,
            "rssi": -65,
            "angle": 30.0,
            "excluded": False,
            "createdAt": f"2024-02-0{i + 1}T12:00:00",
        }], headers=headers)

    await task_update_predictions()

    r = app_client.get(f"/predictions/?batchId={batch_id}", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_task_skips_batch_with_no_og(app_client):
    """Job skips a batch whose og is None — no prediction written."""
    truncate_database()
    batch = app_client.post("/batches", json={
        "name": "NoOG", "acceptIngest": True, "fg": 1.012,
    }, headers=headers).json()
    batch_id = batch["id"]

    dev = app_client.post("/devices", json={
        "name": "NoOGDev", "deviceType": "gravitymon", "chipId": "NOOG1",
        "mdns": "", "description": "",
        "chipFamily": "ESP32", "url": "", "config": "", "collectLogs": False,
    }, headers=headers).json()

    for i, grav in enumerate([1.060, 1.050]):
        app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[{
            "batchId": batch_id,
            "deviceId": dev["id"],
            "gravity": grav,
            "temperature": 20.0,
            "battery": 3.8,
            "rssi": -65,
            "angle": 30.0,
            "excluded": False,
            "createdAt": f"2024-03-0{i + 1}T12:00:00",
        }], headers=headers)

    await task_update_predictions()

    r = app_client.get(f"/predictions/?batchId={batch_id}", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_task_skips_batch_with_no_og_and_no_fg(app_client):
    """Job skips a batch with neither og nor fg set."""
    truncate_database()
    batch = app_client.post("/batches", json={
        "name": "NeitherOGFG", "acceptIngest": True,
    }, headers=headers).json()
    batch_id = batch["id"]

    dev = app_client.post("/devices", json={
        "name": "NoDev", "deviceType": "gravitymon", "chipId": "NOFG2",
        "mdns": "", "description": "",
        "chipFamily": "ESP32", "url": "", "config": "", "collectLogs": False,
    }, headers=headers).json()

    for i, grav in enumerate([1.060, 1.050]):
        app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[{
            "batchId": batch_id,
            "deviceId": dev["id"],
            "gravity": grav,
            "temperature": 20.0,
            "battery": 3.8,
            "rssi": -65,
            "angle": 30.0,
            "excluded": False,
            "createdAt": f"2024-04-0{i + 1}T12:00:00",
        }], headers=headers)

    await task_update_predictions()

    r = app_client.get(f"/predictions/?batchId={batch_id}", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_task_runs_prediction_with_both_og_and_fg(app_client):
    """Job calls predictor only when both og and fg are set, passing exact values."""
    truncate_database()
    batch = app_client.post("/batches", json={
        "name": "FullBatch", "acceptIngest": True, "og": 1.055, "fg": 1.010,
    }, headers=headers).json()
    batch_id = batch["id"]

    dev = app_client.post("/devices", json={
        "name": "FullDev", "deviceType": "gravitymon", "chipId": "FULL1",
        "mdns": "", "description": "",
        "chipFamily": "ESP32", "url": "", "config": "", "collectLogs": False,
    }, headers=headers).json()

    for i, grav in enumerate([1.055, 1.040, 1.025]):
        app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[{
            "batchId": batch_id,
            "deviceId": dev["id"],
            "gravity": grav,
            "temperature": 20.0,
            "battery": 3.8,
            "rssi": -65,
            "angle": 30.0,
            "excluded": False,
            "createdAt": f"2024-05-0{i + 1}T12:00:00",
        }], headers=headers)

    mock_predictor = MagicMock()
    mock_predictor.predict.return_value = 36.0

    with patch("oss.jobs.predictions._get_predictor", return_value=mock_predictor):
        await task_update_predictions()

    call_kwargs = mock_predictor.predict.call_args.kwargs
    assert call_kwargs["start_gravity"] == pytest.approx(1.055)
    assert call_kwargs["plateau_gravity"] == pytest.approx(1.010)

    r = app_client.get(f"/predictions/?batchId={batch_id}", headers=headers)
    assert len(r.json()) == 1
    assert r.json()[0]["outcome"] == "fermenting"


def test_get_predictor_instantiates_once(monkeypatch):
    """_get_predictor returns a FermentationCompletionPredictor and caches it."""
    import oss.jobs.predictions as pred_mod  # pylint: disable=import-outside-toplevel
    from oss.jobs.predictions import _get_predictor  # pylint: disable=import-outside-toplevel
    from core.ml.fermentation_completion_predictor import FermentationCompletionPredictor  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(pred_mod, "_PREDICTOR", None)
    p1 = _get_predictor()
    p2 = _get_predictor()
    assert isinstance(p1, FermentationCompletionPredictor)
    assert p1 is p2


@pytest.mark.asyncio
async def test_task_skips_batch_when_all_readings_excluded(app_client):
    """Job skips a batch where all readings are excluded (history < 2 after filter)."""
    truncate_database()
    batch = app_client.post("/batches", json={
        "name": "AllExcluded", "acceptIngest": True, "og": 1.060, "fg": 1.012,
    }, headers=headers).json()
    batch_id = batch["id"]

    dev = app_client.post("/devices", json={
        "name": "ExclDev", "deviceType": "gravitymon", "chipId": "EXCL1",
        "mdns": "", "description": "",
        "chipFamily": "ESP32", "url": "", "config": "", "collectLogs": False,
    }, headers=headers).json()

    for i, grav in enumerate([1.060, 1.050]):
        app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[{
            "batchId": batch_id,
            "deviceId": dev["id"],
            "gravity": grav,
            "temperature": 20.0,
            "battery": 3.8,
            "rssi": -65,
            "angle": 30.0,
            "excluded": True,
            "createdAt": f"2024-06-0{i + 1}T12:00:00",
        }], headers=headers)

    await task_update_predictions()

    r = app_client.get(f"/predictions/?batchId={batch_id}", headers=headers)
    assert r.json() == []


@pytest.mark.asyncio
async def test_task_handles_predictor_exception(app_client):
    """Per-batch exception is caught and does not abort the job."""
    truncate_database()
    batch = app_client.post("/batches", json={
        "name": "ErrBatch", "acceptIngest": True, "og": 1.060, "fg": 1.012,
    }, headers=headers).json()
    batch_id = batch["id"]

    dev = app_client.post("/devices", json={
        "name": "ErrDev", "deviceType": "gravitymon", "chipId": "ERR01",
        "mdns": "", "description": "",
        "chipFamily": "ESP32", "url": "", "config": "", "collectLogs": False,
    }, headers=headers).json()

    for i, grav in enumerate([1.060, 1.050, 1.040]):
        app_client.post(f"/batches/{batch_id}/gravity/bulk", json=[{
            "batchId": batch_id,
            "deviceId": dev["id"],
            "gravity": grav,
            "temperature": 20.0,
            "battery": 3.8,
            "rssi": -65,
            "angle": 30.0,
            "excluded": False,
            "createdAt": f"2024-07-0{i + 1}T12:00:00",
        }], headers=headers)

    mock_predictor = MagicMock()
    mock_predictor.predict.side_effect = RuntimeError("model exploded")

    with patch("oss.jobs.predictions._get_predictor", return_value=mock_predictor):
        await task_update_predictions()  # must not raise

    r = app_client.get(f"/predictions/?batchId={batch_id}", headers=headers)
    assert r.json() == []


@pytest.mark.asyncio
async def test_task_handles_outer_db_exception():
    """Outer DB failure is caught and does not propagate."""
    mock_db = MagicMock()
    mock_db.scalars.side_effect = RuntimeError("db gone")
    with patch("oss.jobs.predictions.create_session", return_value=mock_db):
        await task_update_predictions()  # must not raise
