# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
# pylint: disable=redefined-outer-name

"""Tests for manual pressure/temperature reading entry on storage vessels."""

from datetime import datetime, timedelta, timezone

from core.config import get_settings
from main_oss import app
from oss.extensions.retention import oss_retention_provider
from tests.conftest import app_client, truncate_database  # noqa: F401  # pylint: disable=unused-import


HDR = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

def _create_vessel(client, name="Test Keg") -> dict:
    r = client.post("/vessels", json={"name": name, "vesselType": "keg",
                                            "totalVolume": 19.0, "status": "clean"}, headers=HDR)
    assert r.status_code == 201
    return r.json()


def test_create_vessel_pressure_reading(app_client):
    """POST /vessels/{id}/pressure creates a reading scoped to the vessel."""
    truncate_database()
    vessel = _create_vessel(app_client)
    r = app_client.post(
        f"/vessels/{vessel['id']}/pressure",
        json={"pressure": 103.5, "deviceId": "11111111-1111-1111-1111-111111111111",
              "batchId": "22222222-2222-2222-2222-222222222222"},
        headers=HDR,
    )
    assert r.status_code == 201
    result = r.json()
    assert result["vesselId"] == vessel["id"]
    assert result["batchId"] is None
    assert result["deviceId"] is None
    assert result["pressure"] == 103.5
    assert result["createdAt"] is not None


def test_create_vessel_pressure_reading_preserves_created_at(app_client):
    """POST /vessels/{id}/pressure keeps an explicit createdAt when provided."""
    truncate_database()
    vessel = _create_vessel(app_client)
    r = app_client.post(
        f"/vessels/{vessel['id']}/pressure",
        json={"pressure": 103.5, "createdAt": "2024-06-01T12:00:00+00:00"},
        headers=HDR,
    )
    assert r.status_code == 201
    assert r.json()["createdAt"].startswith("2024-06-01T12:00:00")


def test_create_vessel_temp_reading(app_client):
    """POST /vessels/{id}/temp creates a reading scoped to the vessel."""
    truncate_database()
    vessel = _create_vessel(app_client)
    r = app_client.post(
        f"/vessels/{vessel['id']}/temp",
        json={"temperature": 4.2, "deviceId": "11111111-1111-1111-1111-111111111111",
              "batchId": "22222222-2222-2222-2222-222222222222"},
        headers=HDR,
    )
    assert r.status_code == 201
    result = r.json()
    assert result["vesselId"] == vessel["id"]
    assert result["batchId"] is None
    assert result["deviceId"] is None
    assert result["temperature"] == 4.2
    assert result["createdAt"] is not None


def test_create_vessel_temp_reading_preserves_created_at(app_client):
    """POST /vessels/{id}/temp keeps an explicit createdAt when provided."""
    truncate_database()
    vessel = _create_vessel(app_client)
    r = app_client.post(
        f"/vessels/{vessel['id']}/temp",
        json={"temperature": 4.2, "createdAt": "2024-06-01T12:00:00+00:00"},
        headers=HDR,
    )
    assert r.status_code == 201
    assert r.json()["createdAt"].startswith("2024-06-01T12:00:00")


def test_vessel_pressure_chart_applies_retention_cutoff(app_client):
    """GET /vessels/{id}/pressure/chart drops points before the retention cutoff.

    Vessel-linked pressure readings are subject to retention the same as
    batch-linked ones and the sibling vessel temp chart — this endpoint must
    apply the same `retention_cutoff` dependency those already use.
    """
    truncate_database()
    vessel = _create_vessel(app_client)

    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    for created_at in (old, recent):
        r = app_client.post(
            f"/vessels/{vessel['id']}/pressure",
            json={"pressure": 105.0, "createdAt": created_at},
            headers=HDR,
        )
        assert r.status_code == 201

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    app.dependency_overrides[oss_retention_provider] = lambda: cutoff
    try:
        r = app_client.get(f"/vessels/{vessel['id']}/pressure/chart", headers=HDR)
    finally:
        del app.dependency_overrides[oss_retention_provider]
    assert r.status_code == 200
    assert len(r.json()) == 1
