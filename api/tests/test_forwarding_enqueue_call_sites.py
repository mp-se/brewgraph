# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for enqueue_forward calls in the pressure, pour, and temperature
ingest paths. Verifies the fire-and-forget
background_tasks.add_task(enqueue_forward, ...) call actually fires with the
right subject id (device_id for pressure/temp, tap_id for pour) alongside
each path's existing background tasks."""
import hashlib
import uuid
from unittest.mock import patch

from core.config import get_settings
from core.db import get_session
from core.models.registry import resolve_model
from oss.extensions.tenant import DEFAULT_TENANT_ID
from tests.conftest import DEVICE_DEFAULTS, truncate_database

Tap = resolve_model("Tap")

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def test_init():
    """Reset database state before the scenario group."""
    truncate_database()


def _create_device(app_client, chip_id: str, device_type: str) -> dict:
    data = {
        "name": f"Device {chip_id}",
        "chipId": chip_id,
        **DEVICE_DEFAULTS,
        "deviceType": device_type,
    }
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


def _create_tap_with_token(app_client, token: str) -> dict:
    r = app_client.post("/taps", json={"name": "Test Tap", "tapNumber": 1}, headers=headers)
    assert r.status_code == 201
    tap_id = r.json()["id"]
    db = next(get_session())
    tap = db.get(Tap, uuid.UUID(tap_id))
    tap.token = token
    tap.token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.commit()
    return {"id": tap_id, "token": token}


def _setup_tap_with_vessel(app_client, token: str) -> dict:
    tap = _create_tap_with_token(app_client, token)
    batch_id = app_client.post(
        "/batches", json={"name": "Forward Enqueue Test Batch"}, headers=headers
    ).json()["id"]
    vessel_id = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselType": "keg",
            "name": "Forward Enqueue Test Keg",
            "fillDate": "2026-05-01",
            "totalVolume": 20.0,
            "volumeRemaining": 20.0,
            "status": "serving",
        },
        headers=headers,
    ).json()["id"]
    app_client.patch(f"/vessels/{vessel_id}", json={"tapId": tap["id"]}, headers=headers)
    return tap


# ---------------------------------------------------------------------------
# pressure.py's _process_pressure
# ---------------------------------------------------------------------------

def test_pressure_ingest_enqueues_forward(app_client):
    """POST /ingest/pressuremon calls enqueue_forward(device.id, DEFAULT_TENANT_ID)
    alongside its existing notify_clients background task."""
    test_init()
    device = _create_device(app_client, "PFWD01", "pressuremon")
    payload = {
        "name": "PressureMon Enqueue Test", "id": "PFWD01", "token": device["token"],
        "pressure": 12.5, "pressure_units": "psi",
        "temperature": 4.0, "battery": 3.8, "rssi": -70,
    }
    with patch("oss.routers.ingest.pressure.enqueue_forward") as mock_enqueue:
        r = app_client.post("/ingest/pressuremon", json=payload)
    assert r.status_code == 200
    mock_enqueue.assert_called_once_with(uuid.UUID(device["id"]), DEFAULT_TENANT_ID)


# ---------------------------------------------------------------------------
# pour.py's _process_pour
# ---------------------------------------------------------------------------

def test_kegmon_pour_enqueues_forward(app_client):
    """POST /ingest/kegmon calls enqueue_forward(tap.id, DEFAULT_TENANT_ID) --
    tap-keyed, not device-keyed, right after write_pour succeeds."""
    test_init()
    tap = _setup_tap_with_vessel(app_client, "pour-fwd-token")
    payload = {"token": tap["token"], "pour": 0.33, "volume": 19.67, "maxVolume": 20.0}
    with patch("oss.routers.ingest.pour.enqueue_forward") as mock_enqueue:
        r = app_client.post("/ingest/kegmon", json=payload)
    assert r.status_code == 200
    mock_enqueue.assert_called_once_with(uuid.UUID(tap["id"]), DEFAULT_TENANT_ID)


# ---------------------------------------------------------------------------
# __init__.py's ingest_temp (the dedicated /ingest/chamber endpoint)
# ---------------------------------------------------------------------------

def test_chamber_direct_endpoint_enqueues_temp_forward(app_client):
    """POST /ingest/chamber (the __init__.py ingest_temp handler) delegates to
    chamber.py's _process_chamber -- the two are no longer separate bodies --
    which calls enqueue_forward(device.id, DEFAULT_TENANT_ID) after write_temp
    succeeds."""
    test_init()
    device = _create_device(app_client, "TFWD01", "chamber_controller")
    payload = {
        "current_mode": "R", "token": device["token"],
        "beer_temperature": 18.5, "temp_units": "C",
    }
    with patch("oss.routers.ingest.chamber.enqueue_forward") as mock_enqueue:
        r = app_client.post("/ingest/chamber", json=payload)
    assert r.status_code == 200
    mock_enqueue.assert_called_once_with(uuid.UUID(device["id"]), DEFAULT_TENANT_ID)


# ---------------------------------------------------------------------------
# chamber.py's _process_chamber (reached via /ingest/dispatch)
# ---------------------------------------------------------------------------

def test_dispatch_chamber_enqueues_temp_forward(app_client):
    """POST /ingest/dispatch with a chamber-shaped payload routes to
    chamber.py's _process_chamber, which must also call enqueue_forward --
    both of temp's two call sites write_temp, both need it."""
    test_init()
    device = _create_device(app_client, "TFWD02", "chamber_controller")
    payload = {
        "current_mode": "R", "token": device["token"],
        "beer_temperature": 19.0, "temp_units": "C",
    }
    with patch("oss.routers.ingest.chamber.enqueue_forward") as mock_enqueue:
        r = app_client.post("/ingest/dispatch", json=payload)
    assert r.status_code == 200
    mock_enqueue.assert_called_once_with(uuid.UUID(device["id"]), DEFAULT_TENANT_ID)
