# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for per-object creation quota enforcement via AuthContext."""
from contextlib import contextmanager

from core.config import get_settings
from core.middleware.auth import AuthContext, api_key_auth
from main_oss import app
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH_DATA = {
    "name": "Quota Test Batch",
    "description": "",
    "brewDate": "2024-01-01",
    "style": "IPA",
    "brewer": "Magnus",
    "brewfatherBatchId": "",
    "status": "fermenting",
    "abv": 5.5,
    "ebc": 20,
    "ibu": 40,
    "fg": 1.010,
    "og": 1.055,
}

DEVICE_DATA = {
    "name": "Quota Device",
    "chipId": "QUOTA1",
    "deviceType": "gravitymon",
    "mdns": "quota-device",
    "description": "",
    "chipFamily": "ESP32",
    "url": "",
    "config": "",
    "deviceColor": "white",
    "collectLogs": False,
}

TAP_DATA = {"name": "Quota Tap", "tapNumber": 99, "location": "Test Bar"}

_VESSEL_BATCH_DATA = {"name": "Vessel Batch", "status": "packaged"}


def _vessel_data(batch_id: str) -> dict:
    return {
        "batchId": batch_id,
        "vesselType": "keg",
        "name": "Quota Keg",
        "fillDate": "2026-05-01",
        "totalVolume": 19.0,
        "volumeRemaining": 19.0,
    }


@contextmanager
def quota_override(auth: AuthContext):
    """Override api_key_auth for the duration of the block."""
    app.dependency_overrides[api_key_auth] = lambda: auth
    try:
        yield
    finally:
        app.dependency_overrides.pop(api_key_auth, None)


def test_init():
    """Truncate the database before quota integration tests."""
    truncate_database()


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------

def test_batch_quota_allows_up_to_limit(app_client):
    """First batch succeeds when quota is 1."""
    truncate_database()
    with quota_override(AuthContext(quota_limits={"batches": 1})):
        r = app_client.post("/batches", json=BATCH_DATA, headers=headers)
    assert r.status_code == 201


def test_batch_quota_blocks_at_limit(app_client):
    """Second batch is rejected with 403 when quota is 1."""
    truncate_database()
    with quota_override(AuthContext(quota_limits={"batches": 1})):
        app_client.post("/batches", json=BATCH_DATA, headers=headers)
        r = app_client.post("/batches", json={**BATCH_DATA, "name": "Extra"}, headers=headers)
    assert r.status_code == 403
    assert "quota" in r.json()["message"].lower()


def test_batch_quota_unlimited_by_default(app_client):
    """Default AuthContext (no limits set) never blocks."""
    truncate_database()
    for i in range(3):
        r = app_client.post("/batches", json={**BATCH_DATA, "name": f"Batch {i}"}, headers=headers)
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

def test_device_quota_allows_up_to_limit(app_client):
    """First device succeeds when quota is 1."""
    truncate_database()
    with quota_override(AuthContext(quota_limits={"devices": 1})):
        r = app_client.post("/devices", json=DEVICE_DATA, headers=headers)
    assert r.status_code == 201


def test_device_quota_blocks_at_limit(app_client):
    """Second device is rejected with 403 when quota is 1."""
    truncate_database()
    with quota_override(AuthContext(quota_limits={"devices": 1})):
        app_client.post("/devices", json=DEVICE_DATA, headers=headers)
        r = app_client.post("/devices", json={**DEVICE_DATA, "chipId": "QUOTA2"}, headers=headers)
    assert r.status_code == 403
    assert "quota" in r.json()["message"].lower()


def test_device_quota_unlimited_by_default(app_client):
    """Default AuthContext never blocks device creation."""
    truncate_database()
    for i in range(3):
        r = app_client.post(
            "/devices", json={**DEVICE_DATA, "chipId": f"DEV00{i}"}, headers=headers
        )
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# Taps
# ---------------------------------------------------------------------------

def test_tap_quota_allows_up_to_limit(app_client):
    """First tap succeeds when quota is 1."""
    truncate_database()
    with quota_override(AuthContext(quota_limits={"taps": 1})):
        r = app_client.post("/taps", json=TAP_DATA, headers=headers)
    assert r.status_code == 201


def test_tap_quota_blocks_at_limit(app_client):
    """Second tap is rejected with 403 when quota is 1."""
    truncate_database()
    with quota_override(AuthContext(quota_limits={"taps": 1})):
        app_client.post("/taps", json=TAP_DATA, headers=headers)
        r = app_client.post("/taps", json={**TAP_DATA, "tapNumber": 100}, headers=headers)
    assert r.status_code == 403
    assert "quota" in r.json()["message"].lower()


def test_tap_quota_unlimited_by_default(app_client):
    """Default AuthContext never blocks tap creation."""
    truncate_database()
    for i in range(3):
        r = app_client.post("/taps", json={**TAP_DATA, "tapNumber": i + 1}, headers=headers)
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# Vessels
# ---------------------------------------------------------------------------

def test_vessel_quota_allows_up_to_limit(app_client):
    """First vessel succeeds when quota is 1."""
    truncate_database()
    batch_id = app_client.post("/batches", json=_VESSEL_BATCH_DATA, headers=headers).json()["id"]
    with quota_override(AuthContext(quota_limits={"vessels": 1})):
        r = app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
    assert r.status_code == 201


def test_vessel_quota_blocks_at_limit(app_client):
    """Second vessel is rejected with 403 when quota is 1."""
    truncate_database()
    batch_id = app_client.post("/batches", json=_VESSEL_BATCH_DATA, headers=headers).json()["id"]
    with quota_override(AuthContext(quota_limits={"vessels": 1})):
        app_client.post("/vessels", json=_vessel_data(batch_id), headers=headers)
        r = app_client.post(
            "/vessels", json={**_vessel_data(batch_id), "name": "Keg 2"}, headers=headers
        )
    assert r.status_code == 403
    assert "quota" in r.json()["message"].lower()


def test_vessel_quota_unlimited_by_default(app_client):
    """Default AuthContext never blocks vessel creation."""
    truncate_database()
    batch_id = app_client.post("/batches", json=_VESSEL_BATCH_DATA, headers=headers).json()["id"]
    for i in range(3):
        r = app_client.post(
            "/vessels", json={**_vessel_data(batch_id), "name": f"Keg {i}"}, headers=headers
        )
        assert r.status_code == 201
