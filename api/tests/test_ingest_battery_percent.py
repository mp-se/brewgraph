# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Battery measurements remain independent, nullable and unchanged by ingestion."""
import pytest

from core.config import get_settings
from core.db import create_session
from core.models.platform import IngestionLog
from tests.conftest import DEVICE_DEFAULTS, truncate_database

HEADERS = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def _send_reading(client, kind: str, chip_id: str, battery: float | None,
                  battery_percent: float | None) -> dict:
    device_type = "pressuremon" if kind == "pressure" else "gravitymon"
    device = client.post("/devices", json={
        "name": f"Battery {chip_id}",
        "chipId": chip_id,
        **DEVICE_DEFAULTS,
        "deviceType": device_type,
    }, headers=HEADERS).json()
    common = {"id": chip_id, "token": device["token"],
              "battery": battery, "battery_percent": battery_percent}
    if kind == "pressure":
        payload = {**common, "pressure": 10.0, "pressure_units": "kPa"}
        route = "/ingest/pressuremon"
        resource = "pressure"
    else:
        payload = {**common, "gravity": 1.05, "gravity-unit": "G"}
        route = "/ingest/gravitymon"
        resource = "gravity"
    response = client.post(route, json=payload)
    assert response.status_code == 200

    batch_id = client.get(
        f"/batches/?deviceId={device['id']}", headers=HEADERS
    ).json()["items"][0]["id"]
    return client.get(f"/batches/{batch_id}/{resource}", headers=HEADERS).json()["items"][0]


@pytest.mark.parametrize("kind", ["gravity", "pressure"])
@pytest.mark.parametrize(("battery", "battery_percent"), [
    (None, 137.12345),
    (3.85123, None),
    (3.85123, 137.12345),
    (None, None),
])
def test_battery_values_are_independent_and_store_as_received(
    app_client, kind, battery, battery_percent
):
    """Each received value persists unchanged; an absent value stays null."""
    truncate_database()
    reading = _send_reading(app_client, kind, "BATP01", battery, battery_percent)
    assert reading["battery"] == battery
    assert reading["batteryPercent"] == battery_percent


@pytest.mark.parametrize("kind", ["gravity", "pressure"])
@pytest.mark.parametrize("value", ["not-a-number", "NaN", "Infinity"])
def test_non_finite_battery_percent_is_dropped(app_client, kind, value):
    """A bad optional battery percentage is dropped while the reading is stored."""
    truncate_database()
    device_type = "pressuremon" if kind == "pressure" else "gravitymon"
    device = app_client.post("/devices", json={
        "name": "Invalid percentage", "chipId": "BATP02",
        **DEVICE_DEFAULTS, "deviceType": device_type,
    }, headers=HEADERS).json()
    common = {"id": "BATP02", "token": device["token"], "battery_percent": value}
    if kind == "pressure":
        response = app_client.post("/ingest/pressuremon", json={**common, "pressure": 10.0})
    else:
        response = app_client.post("/ingest/gravitymon", json={
            **common, "gravity": 1.05, "gravity-unit": "G",
        })
    assert response.status_code == 200
    session = create_session()
    try:
        assert "battery_percent" in session.query(IngestionLog).one().error_detail
    finally:
        session.close()
