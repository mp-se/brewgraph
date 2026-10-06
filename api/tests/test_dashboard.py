# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for GET /api/dashboard endpoint."""
import json

import pytest

from core.config import get_settings
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH_DATA = {
    "name": "Dashboard Test Batch",
    "status": "fermenting",
    "og": 1.055,
    "fg": 1.010,
}

GRAVITY_DATA = {
    "temperature": 20.0,
    "gravity": 1.050,
    "battery": 3.8,
    "rssi": -75.0,
    "excluded": False,
}


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate database before each test."""
    truncate_database()


def _create_batch(app_client, **kwargs) -> str:
    """Create a batch and return its id."""
    data = {**BATCH_DATA, **kwargs}
    r = app_client.post("/batches", json=data, headers=headers)
    assert r.status_code == 201
    return json.loads(r.text)["id"]


def _create_device(app_client, name="DashDev") -> dict:
    """Create a device and return its JSON response."""
    r = app_client.post(
        "/devices",
        json={"name": name, "deviceType": "gravitymon", "description": "", "chipFamily": "ESP32",
              "collectLogs": False},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()


def test_dashboard_empty(app_client):
    """Fresh database returns 200 with empty lists for all dashboard keys."""
    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "devices" in body
    assert "batches" in body
    assert "taps" in body
    assert "vessels" in body
    assert body["devices"] == []
    assert body["batches"] == []
    assert body["taps"] == []
    assert body["vessels"] == []


def test_dashboard_with_device(app_client):
    """Device created via POST appears in dashboard devices list."""
    dev = _create_device(app_client, name="DashDevice1")
    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    ids = [d["id"] for d in body["devices"]]
    assert dev["id"] in ids


def test_dashboard_with_active_batch(app_client):
    """Batch with accept_ingest=True appears in dashboard batches list."""
    batch_id = _create_batch(app_client, name="ActiveBatch", accept_ingest=True)

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    ids = [b["id"] for b in body["batches"]]
    assert batch_id in ids


def test_dashboard_with_tap(app_client):
    """Tap created via POST appears in dashboard taps list."""
    r = app_client.post(
        "/taps",
        json={"name": "Main Tap", "tapNumber": 1, "location": "Kegerator"},
        headers=headers,
    )
    assert r.status_code == 201
    tap_id = r.json()["id"]

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    ids = [t["id"] for t in body["taps"]]
    assert tap_id in ids


def test_dashboard_tap_includes_vessel_id(app_client):
    """Tap with an assigned vessel exposes the vessel's id in the dashboard response."""
    r = app_client.post(
        "/taps",
        json={"name": "Vessel Tap", "tapNumber": 2, "location": "Kegerator"},
        headers=headers,
    )
    assert r.status_code == 201
    tap_id = r.json()["id"]

    r = app_client.post(
        "/vessels",
        json={
            "vesselNumber": 2,
            "vesselType": "keg",
            "name": "TapKeg",
            "fillDate": "2026-05-01",
            "totalVolume": 19.0,
            "volumeRemaining": 19.0,
            "status": "filled",
        },
        headers=headers,
    )
    assert r.status_code == 201
    vessel_id = r.json()["id"]

    r = app_client.patch(
        f"/vessels/{vessel_id}",
        json={"tapId": tap_id},
        headers=headers,
    )
    assert r.status_code == 200

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    match = next(t for t in body["taps"] if t["id"] == tap_id)
    assert match["vesselId"] == vessel_id


def test_dashboard_batch_with_brew_date(app_client):
    """Active batch with brew_date produces a non-None day_count in dashboard response."""
    _create_batch(app_client, name="BrewDateBatch", accept_ingest=True, brew_date="2026-04-01")
    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    batches = r.json()["batches"]
    assert any(b["dayCount"] is not None for b in batches)


def test_dashboard_device_with_gravity_reading(app_client):
    """Device with batch_role=gravity and a reading has latest_reading populated."""
    import uuid  # pylint: disable=import-outside-toplevel

    from core.db import \
        create_session  # pylint: disable=import-outside-toplevel
    from oss.schemas.gravity_reading import \
        GravityReadingCreate  # pylint: disable=import-outside-toplevel
    from oss.services.device import \
        DeviceService  # pylint: disable=import-outside-toplevel
    from oss.services.gravity import \
        GravityService  # pylint: disable=import-outside-toplevel

    batch_id = _create_batch(app_client, accept_ingest=True)
    dev = _create_device(app_client, name="GravityDev")
    dev_id = uuid.UUID(dev["id"])

    session = create_session()
    device = DeviceService(session).get(dev_id)
    device.batch_role = "gravity"
    device.batch_id = uuid.UUID(batch_id)
    session.commit()

    GravityService(session).create(GravityReadingCreate(
        batch_id=uuid.UUID(batch_id),
        device_id=dev_id,
        gravity=1.048,
        temperature=19.5,
    ))

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    devices = r.json()["devices"]
    match = next((d for d in devices if d["id"] == str(dev_id)), None)
    assert match is not None
    assert match["latestReading"] is not None
    assert match["latestReading"]["gravity"] == 1.048


def test_dashboard_temp_probe_only_batch_reports_current_temp(app_client):
    """A batch with only a nominated temp_device_id (no gravity/pressure device) still
    gets current_temp populated — sourced from that device, not guessed from a reading
    that doesn't exist."""
    import uuid  # pylint: disable=import-outside-toplevel

    from core.db import \
        create_session  # pylint: disable=import-outside-toplevel
    from oss.schemas.temp_reading import \
        TempReadingCreate  # pylint: disable=import-outside-toplevel
    from oss.services.batch import \
        BatchService  # pylint: disable=import-outside-toplevel
    from oss.services.temp_reading import \
        TempService  # pylint: disable=import-outside-toplevel

    batch_id = _create_batch(app_client, name="TempProbeOnlyBatch", accept_ingest=True)
    dev = _create_device(app_client, name="TempOnlyDev")
    dev_id = uuid.UUID(dev["id"])
    batch_uuid = uuid.UUID(batch_id)

    session = create_session()
    batch = BatchService(session).get(batch_uuid)
    batch.temp_device_id = dev_id
    session.commit()

    TempService(session).create(TempReadingCreate(
        batch_id=batch_uuid,
        device_id=dev_id,
        temperature=18.4,
        battery=None,
        rssi=-60.0,
    ))

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    batches = r.json()["batches"]
    match = next(b for b in batches if b["id"] == batch_id)
    assert match["currentGravity"] is None
    assert match["currentPressure"] is None
    assert match["currentTemp"] == 18.4
    assert match["tempDeviceId"] == str(dev_id)
    assert match["rssi"] == -60.0
    assert match["lastReadingAt"] is not None


def test_dashboard_batch_first_gravity(app_client):
    """Batch with multiple gravity readings exposes the earliest reading as first_gravity."""
    batch_id = _create_batch(app_client, name="FirstGravityBatch", accept_ingest=True)

    r = app_client.post(
        f"/batches/{batch_id}/gravity",
        json={**GRAVITY_DATA, "gravity": 1.052, "createdAt": "2026-04-01T08:00:00Z"},
        headers=headers,
    )
    assert r.status_code == 201
    r = app_client.post(
        f"/batches/{batch_id}/gravity",
        json={**GRAVITY_DATA, "gravity": 1.020, "createdAt": "2026-04-05T08:00:00Z"},
        headers=headers,
    )
    assert r.status_code == 201

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    batches = r.json()["batches"]
    match = next(b for b in batches if b["id"] == batch_id)
    assert match["firstGravity"] == 1.052


def test_dashboard_batch_first_gravity_null_without_readings(app_client):
    """Batch with no gravity readings has first_gravity == None in the dashboard response."""
    batch_id = _create_batch(app_client, name="NoGravityBatch", accept_ingest=True)

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    batches = r.json()["batches"]
    match = next(b for b in batches if b["id"] == batch_id)
    assert match["firstGravity"] is None
    assert match["firstReadingAt"] is None


def test_dashboard_batch_first_reading_at_uses_earliest_measurement(app_client):
    """The dashboard age anchor is the first reading across every batch stream."""
    batch_id = _create_batch(app_client, name="FirstMeasurementBatch", accept_ingest=True)

    gravity = app_client.post(
        f"/batches/{batch_id}/gravity",
        json={**GRAVITY_DATA, "createdAt": "2026-04-02T08:00:00Z"},
        headers=headers,
    )
    assert gravity.status_code == 201
    pressure = app_client.post(
        f"/batches/{batch_id}/pressure",
        json={"pressure": 101.3, "createdAt": "2026-04-01T08:00:00Z"},
        headers=headers,
    )
    assert pressure.status_code == 201
    temperature = app_client.post(
        f"/batches/{batch_id}/temp",
        json={"temperature": 19.5, "createdAt": "2026-03-31T08:00:00Z"},
        headers=headers,
    )
    assert temperature.status_code == 201

    response = app_client.get("/dashboard", headers=headers)
    assert response.status_code == 200
    match = next(b for b in response.json()["batches"] if b["id"] == batch_id)
    assert match["firstReadingAt"] == "2026-03-31T08:00:00Z"


def test_dashboard_device_with_pressure_reading(app_client):
    """Device with batch_role=pressure and a reading has latest_reading populated."""
    import uuid  # pylint: disable=import-outside-toplevel

    from core.db import \
        create_session  # pylint: disable=import-outside-toplevel
    from oss.schemas.pressure_reading import \
        PressureReadingCreate  # pylint: disable=import-outside-toplevel
    from oss.services.device import \
        DeviceService  # pylint: disable=import-outside-toplevel
    from oss.services.pressure import \
        PressureService  # pylint: disable=import-outside-toplevel

    batch_id = _create_batch(app_client, accept_ingest=True)
    dev = _create_device(app_client, name="PressureDev")
    dev_id = uuid.UUID(dev["id"])

    session = create_session()
    device = DeviceService(session).get(dev_id)
    device.batch_role = "pressure"
    device.batch_id = uuid.UUID(batch_id)
    session.commit()

    PressureService(session).create(PressureReadingCreate(
        batch_id=uuid.UUID(batch_id),
        device_id=dev_id,
        pressure=105.0,
        temperature=18.0,
    ))

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    devices = r.json()["devices"]
    match = next((d for d in devices if d["id"] == str(dev_id)), None)
    assert match is not None
    assert match["latestReading"] is not None
    assert match["latestReading"]["pressure"] == 105.0


def test_dashboard_with_vessel(app_client):
    """Vessel linked to a batch appears in dashboard vessels list."""
    batch_id = _create_batch(app_client, name="VesselBatch", status="packaged")
    r = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselNumber": 1,
            "vesselType": "keg",
            "name": "DashKeg",
            "fillDate": "2026-05-01",
            "totalVolume": 19.0,
            "volumeRemaining": 19.0,
            "status": "filled",
        },
        headers=headers,
    )
    assert r.status_code == 201
    vessel_id = r.json()["id"]

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    ids = [v["id"] for v in body["vessels"]]
    assert vessel_id in ids

def test_dashboard_ready_batch_appears(app_client):
    """Packaged batch with ready_date <= today appears in ready_batches."""
    r = app_client.post(
        "/batches",
        json={
            "name": "ReadyBatch",
            "status": "packaged",
            "packageDate": "2026-01-01",
            "conditioningDays": 14,
        },
        headers=headers,
    )
    assert r.status_code == 201
    batch_id = r.json()["id"]

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "readyBatches" in body
    ids = [b["id"] for b in body["readyBatches"]]
    assert batch_id in ids
    match = next(b for b in body["readyBatches"] if b["id"] == batch_id)
    assert match["kind"] == "batch"
    assert match["readyDate"] is not None


def test_dashboard_not_yet_ready_batch_excluded(app_client):
    """Packaged batch with future ready_date does not appear in ready_batches."""
    r = app_client.post(
        "/batches",
        json={
            "name": "NotYetBatch",
            "status": "packaged",
            "packageDate": "2099-01-01",
            "conditioningDays": 14,
        },
        headers=headers,
    )
    assert r.status_code == 201
    batch_id = r.json()["id"]

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()["readyBatches"]]
    assert batch_id not in ids


def test_dashboard_archived_batch_excluded_from_ready(app_client):
    """Archived batch does not appear in ready_batches even if past ready_date."""
    r = app_client.post(
        "/batches",
        json={
            "name": "ArchivedBatch",
            "status": "packaged",
            "packageDate": "2026-01-01",
            "conditioningDays": 14,
        },
        headers=headers,
    )
    assert r.status_code == 201
    batch_id = r.json()["id"]

    app_client.patch(f"/batches/{batch_id}", json={"status": "archived"}, headers=headers)

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()["readyBatches"]]
    assert batch_id not in ids


def test_dashboard_batch_missing_conditioning_days_excluded(app_client):
    """Packaged batch without conditioning_days does not appear in ready_batches."""
    r = app_client.post(
        "/batches",
        json={
            "name": "NoDaysBatch",
            "status": "packaged",
            "packageDate": "2026-01-01",
        },
        headers=headers,
    )
    assert r.status_code == 201
    batch_id = r.json()["id"]

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()["readyBatches"]]
    assert batch_id not in ids


def test_dashboard_ready_vessel_appears(app_client):
    """Filled vessel with conditioning complete appears in ready_vessels."""
    batch_id = _create_batch(app_client, name="VBatch", status="packaged")
    r = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselNumber": 1,
            "vesselType": "keg",
            "name": "ReadyKeg",
            "fillDate": "2026-01-01",
            "conditioningDays": 14,
            "totalVolume": 19.0,
            "volumeRemaining": 19.0,
            "status": "filled",
        },
        headers=headers,
    )
    assert r.status_code == 201
    vessel_id = r.json()["id"]

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "readyVessels" in body
    ids = [v["id"] for v in body["readyVessels"]]
    assert vessel_id in ids
    match = next(v for v in body["readyVessels"] if v["id"] == vessel_id)
    assert match["kind"] == "vessel"
    assert match["readyDate"] is not None


def test_dashboard_vessel_wrong_status_excluded(app_client):
    """Vessel with status != filled does not appear in ready_vessels."""
    batch_id = _create_batch(app_client, name="VBatch2", status="packaged")
    r = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselNumber": 2,
            "vesselType": "keg",
            "name": "ServingKeg",
            "fillDate": "2026-01-01",
            "conditioningDays": 14,
            "totalVolume": 19.0,
            "volumeRemaining": 15.0,
            "status": "serving",
        },
        headers=headers,
    )
    assert r.status_code == 201
    vessel_id = r.json()["id"]

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    ids = [v["id"] for v in r.json()["readyVessels"]]
    assert vessel_id not in ids


def test_dashboard_vessel_missing_conditioning_days_excluded(app_client):
    """Filled vessel without conditioning_days does not appear in ready_vessels."""
    batch_id = _create_batch(app_client, name="VBatch3", status="packaged")
    r = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselNumber": 3,
            "vesselType": "keg",
            "name": "NoDaysKeg",
            "fillDate": "2026-01-01",
            "totalVolume": 19.0,
            "volumeRemaining": 19.0,
            "status": "filled",
        },
        headers=headers,
    )
    assert r.status_code == 201
    vessel_id = r.json()["id"]

    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    ids = [v["id"] for v in r.json()["readyVessels"]]
    assert vessel_id not in ids


def test_dashboard_ready_empty_lists_by_default(app_client):
    """Fresh dashboard includes readyBatches and readyVessels keys (empty)."""
    r = app_client.get("/dashboard", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "readyBatches" in body
    assert "readyVessels" in body
    assert body["readyBatches"] == []
    assert body["readyVessels"] == []


def _count_dashboard_queries(app_client, entity_count: int) -> int:
    """Build `entity_count` of each entity, then count statements for one request."""
    from sqlalchemy import event

    from core.db import engine

    for i in range(entity_count):
        batch_id = _create_batch(app_client, name=f"Budget Batch {i}")
        dev = _create_device(app_client, name=f"BudgetDev{i}")
        app_client.patch(
            f"/devices/{dev['id']}",
            json={"batchId": batch_id, "batchRole": "gravity"},
            headers=headers,
        )
        app_client.post(
            "/vessels",
            json={"vesselType": "keg", "name": f"Budget Keg {i}", "fillDate": "2026-01-01",
                  "totalVolume": 19.0, "volumeRemaining": 19.0, "status": "clean"},
            headers=headers,
        )
        app_client.post(
            "/taps",
            json={"name": f"Budget Tap {i}", "tapNumber": i + 1},
            headers=headers,
        )

    statements = []

    def _record(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        r = app_client.get("/dashboard", headers=headers)
        assert r.status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", _record)
    return len(statements)


def test_dashboard_query_count_does_not_grow_with_entity_count(app_client):
    """The home screen must not be O(entities) in round trips.

    It was: ~2.8 queries per entity, so 229 statements for twenty of each thing.
    A count assertion is the only kind of test that catches an N+1 — every query
    involved is individually cheap and correctly indexed, and the endpoint returns
    the same body either way.

    The assertion is on the *slope*, not an absolute number, so ordinary changes to
    the endpoint do not have to keep re-baselining a magic constant.
    """
    truncate_database()
    small = _count_dashboard_queries(app_client, 3)
    truncate_database()
    large = _count_dashboard_queries(app_client, 12)

    growth_per_entity = (large - small) / 9
    assert growth_per_entity <= 0.5, (
        f"dashboard queries grow {growth_per_entity:.1f} per entity "
        f"({small} at 3, {large} at 12) — a relation is still being fetched per row"
    )
