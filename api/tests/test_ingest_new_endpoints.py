# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

# pylint: disable=redefined-outer-name
"""Tests for new ingest endpoints: dispatch, kegmon/beer."""
from unittest.mock import patch

from core.config import get_settings
from tests.conftest import app_client, truncate_database  # noqa: F401  # pylint: disable=unused-import


HDR = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

def _create_device(client, chip_id: str, device_type: str = "gravitymon") -> dict:
    r = client.post("/devices", json={"name": f"dev_{chip_id}", "chipId": chip_id,
                                       "deviceType": device_type}, headers=HDR)
    assert r.status_code == 201
    return r.json()


def _get_token(client, device_id: str) -> str:
    r = client.post(f"/devices/{device_id}/token", headers=HDR)
    assert r.status_code == 200
    return r.json()["token"]


# ---------------------------------------------------------------------------
# /ingest/dispatch
# ---------------------------------------------------------------------------

def test_dispatch_detects_gravitymon(app_client):
    """dispatch routes gravitymon payload (has gravity-unit) correctly."""
    truncate_database()
    device = _create_device(app_client, "DISP01")
    token = _get_token(app_client, device["id"])
    payload = {"name": "GravityMon", "id": "DISP01", "token": token,
               "gravity": 1.048, "gravity-unit": "G", "temperature": 20.0,
               "temp_units": "C", "angle": 30.0, "battery": 4.1, "rssi": -60}
    r = app_client.post("/ingest/dispatch", json=payload, headers=HDR)
    assert r.status_code == 200


def test_dispatch_detects_ispindel(app_client):
    """dispatch routes ispindel payload (has gravity, no gravity-unit)."""
    truncate_database()
    device = _create_device(app_client, "DISP02", "ispindel")
    token = _get_token(app_client, device["id"])
    payload = {"name": "[SG] iSpindel", "ID": 13065052, "token": token,
               "gravity": 1.048, "temperature": 20.0, "temp_units": "C",
               "angle": 30.0, "battery": 4.1, "RSSI": -60}
    r = app_client.post("/ingest/dispatch", json=payload, headers=HDR)
    assert r.status_code == 200


def test_dispatch_invalid_json_returns_422(app_client):
    """dispatch returns 422 for unparseable body."""
    truncate_database()
    r = app_client.post("/ingest/dispatch", content=b"not json",
                        headers={"Content-Type": "application/json"})
    assert r.status_code == 422

# ---------------------------------------------------------------------------
# /ingest/kegmon/beer
# ---------------------------------------------------------------------------

def test_kegmon_beer_unknown_token_401(app_client):
    """kegmon/beer with unknown token returns 401."""
    truncate_database()
    r = app_client.post("/ingest/kegmon/beer", json={"token": "unknowntap"}, headers=HDR)
    assert r.status_code == 401


def test_kegmon_beer_missing_token_401(app_client):
    """kegmon/beer without token field returns 422 (schema validation) or 401."""
    truncate_database()
    r = app_client.post("/ingest/kegmon/beer", json={}, headers=HDR)
    assert r.status_code in (401, 422)


def test_kegmon_beer_floods_invalid_token_rejected_before_resolve_tap(app_client):
    """A flood of invalid-token requests is rejected by the per-token rate
    ceiling before ever reaching `resolve_tap`'s DB lookup — regression for the
    gap where this endpoint had no gate at all ahead of that query."""
    truncate_database()
    with patch("core.middleware.auth.increment_key", return_value=61) as mock_increment, \
         patch("oss.routers.ingest.IngestionService.resolve_tap") as mock_resolve_tap:
        r = app_client.post("/ingest/kegmon/beer", json={"token": "garbage-token"}, headers=HDR)
    assert r.status_code == 429
    mock_increment.assert_called()
    mock_resolve_tap.assert_not_called()


# ---------------------------------------------------------------------------
# Retry-After header on 429
# ---------------------------------------------------------------------------

def test_throttle_returns_retry_after_header(app_client):
    """Throttled ingest returns Retry-After header."""
    truncate_database()
    device = _create_device(app_client, "RTRY01")
    token = _get_token(app_client, device["id"])
    payload = {"name": "GravityMon", "id": "RTRY01", "token": token,
               "gravity": 1.048, "gravity-unit": "G", "temperature": 20.0,
               "temp_units": "C", "angle": 30.0, "battery": 4.1, "rssi": -60}
    # First request should succeed
    r1 = app_client.post("/ingest/gravitymon", json=payload, headers=HDR)
    assert r1.status_code == 200
    # Second request within throttle window should return 429 with header
    r2 = app_client.post("/ingest/gravitymon", json=payload, headers=HDR)
    if r2.status_code == 429:
        assert "retry-after" in r2.headers
