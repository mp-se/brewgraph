# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for device endpoints."""
import json
import uuid

from core.config import get_settings
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

DEVICE_DATA = {
    "name": "Test Device",
    "chipId": "AAAAAA",
    "deviceType": "gravitymon",
    "mdns": "gravitymon-aaaaaa",
    "description": "A test device",
    "chipFamily": "ESP32",
    "url": "http://gravitymon.local",
    "config": "",
    "deviceColor": "white",
    "collectLogs": False,
}


def test_init():
    """Reset database state before test scenarios."""
    truncate_database()


def test_add(app_client):
    """Creating a device returns 201 with a UUID id and a 32-char token."""
    test_init()

    r = app_client.post("/devices", json=DEVICE_DATA, headers=headers)
    assert r.status_code == 201
    data = json.loads(r.text)

    # id must be a valid UUID
    device_id = data["id"]
    assert uuid.UUID(device_id)

    # core fields
    assert data["chipId"] == DEVICE_DATA["chipId"]
    assert data["name"] == DEVICE_DATA["name"]
    assert data["deviceType"] == DEVICE_DATA["deviceType"]
    assert data["mdns"] == DEVICE_DATA["mdns"]
    assert data["description"] == DEVICE_DATA["description"]
    assert data["chipFamily"] == DEVICE_DATA["chipFamily"]
    assert data["url"] == DEVICE_DATA["url"]
    assert data["collectLogs"] == DEVICE_DATA["collectLogs"]
    assert data["deviceColor"] == "white"

    # token auto-generated on creation
    assert "token" in data
    assert len(data["token"]) == 32

    # timestamps present
    assert "createdAt" in data
    assert "updatedAt" in data


def test_config_survives_list_and_get(app_client):
    """`config` must round-trip through both GET /devices/{id} and GET /devices/ —
    Backup & Restore collects devices wholesale from GET /api/devices/, so config is
    only preserved if the serializer emits it on every read path, not just GET by id.
    """
    test_init()
    fetched = {
        "fetched_at": "2026-07-25T14:03:00Z",
        "status": {"id": "aabbcc"},
        "config": {"interval": 900},
        "feature": {"platform": "esp32", "app_ver": "1.2.3"},
        "format": {"template": "x"},
    }
    data = DEVICE_DATA.copy()
    data["config"] = fetched
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    device_id = json.loads(r.text)["id"]

    r = app_client.get(f"/devices/{device_id}", headers=headers)
    assert r.status_code == 200
    stored = json.loads(r.text)["config"]
    assert stored["kind"] == "device-config"
    assert stored["data"] == fetched

    r = app_client.get("/devices", headers=headers)
    assert r.status_code == 200
    items = json.loads(r.text)["items"]
    match = next(item for item in items if item["id"] == device_id)
    assert match["config"]["data"] == fetched


def test_config_accepts_a_firmware_that_answers_with_text(app_client):
    """proxy_fetch falls back to res.text, so a non-JSON config must still store."""
    test_init()
    data = DEVICE_DATA.copy()
    data["chipId"] = "textcfg1"
    data["config"] = "interval=900\nplatform=esp32"
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201

    stored = json.loads(r.text)["config"]
    assert stored["kind"] == "device-config"
    assert stored["data"]["raw"].startswith("interval=900")


def test_config_is_not_double_wrapped_on_update(app_client):
    """Re-sending a stored envelope keeps one envelope, not an envelope of an envelope."""
    test_init()
    data = DEVICE_DATA.copy()
    data["chipId"] = "rewrap01"
    data["config"] = {"interval": 900}
    device = json.loads(
        app_client.post("/devices", json=data, headers=headers).text
    )

    r = app_client.patch(
        f"/devices/{device['id']}", json={"config": device["config"]}, headers=headers
    )
    assert r.status_code == 200
    assert json.loads(r.text)["config"]["data"] == {"interval": 900}


def test_list(app_client):
    """Listing devices returns at least the device created above."""
    r = app_client.get("/devices", headers=headers)
    assert r.status_code == 200
    body = json.loads(r.text)
    data = body["items"]
    assert len(data) >= 1
    # Every item must have a UUID id
    for item in data:
        assert uuid.UUID(item["id"])


def test_get_by_id(app_client):
    """GET by UUID id returns the device."""
    test_init()
    r = app_client.post("/devices", json=DEVICE_DATA, headers=headers)
    device_id = json.loads(r.text)["id"]

    r = app_client.get(f"/devices/{device_id}", headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert data["id"] == device_id

    # Non-existent UUID returns 404
    r = app_client.get(f"/devices/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404


def test_update(app_client):
    """PATCH updates mutable fields and returns 200."""
    test_init()
    r = app_client.post("/devices", json=DEVICE_DATA, headers=headers)
    device_id = json.loads(r.text)["id"]

    update = {
        "name": "Updated Device",
        "deviceType": "ispindel",
        "mdns": "ispindel-aaaaaa",
        "description": "Updated description",
        "chipFamily": "ESP8266",
        "url": "http://ispindel.local",
        "config": "{}",
        "deviceColor": "red",
        "collectLogs": True,
    }
    r = app_client.patch(f"/devices/{device_id}", json=update, headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert data["name"] == "Updated Device"
    assert data["deviceType"] == "ispindel"
    assert data["deviceColor"] == "red"
    assert data["collectLogs"] is True

    # Non-existent UUID returns 404
    r = app_client.patch(f"/devices/{uuid.uuid4()}", json=update, headers=headers)
    assert r.status_code == 404


def test_device_color_rejects_values_outside_palette(app_client):
    """Device writes accept only the closed preset color palette."""
    test_init()
    data = DEVICE_DATA.copy()
    data["deviceColor"] = "teal"

    r = app_client.post("/devices", json=data, headers=headers)

    assert r.status_code == 422


def test_delete(app_client):
    """DELETE soft-deletes the device; it disappears from list and GET returns 404."""
    test_init()
    r = app_client.post("/devices", json=DEVICE_DATA, headers=headers)
    device_id = json.loads(r.text)["id"]

    r = app_client.delete(f"/devices/{device_id}", headers=headers)
    assert r.status_code == 204

    # Must not appear in list
    r = app_client.get("/devices", headers=headers)
    ids = [d["id"] for d in json.loads(r.text)["items"]]
    assert device_id not in ids

    # GET by id must 404
    r = app_client.get(f"/devices/{device_id}", headers=headers)
    assert r.status_code == 404


def test_patch_soft_deleted_device_returns_404(app_client):
    """PATCHing a soft-deleted device is rejected, not silently applied."""
    test_init()
    r = app_client.post("/devices", json=DEVICE_DATA, headers=headers)
    device_id = json.loads(r.text)["id"]
    assert app_client.delete(f"/devices/{device_id}", headers=headers).status_code == 204

    r2 = app_client.patch(
        f"/devices/{device_id}", json={"name": "Should not apply"}, headers=headers
    )
    assert r2.status_code == 404


def test_search(app_client):
    """GET /devices/ returns paginated envelope with all registered devices."""
    test_init()

    r = app_client.post("/devices", json=DEVICE_DATA, headers=headers)
    assert r.status_code == 201

    d2 = DEVICE_DATA.copy()
    d2["chipId"] = "BBBBBB"
    r = app_client.post("/devices", json=d2, headers=headers)
    assert r.status_code == 201

    r = app_client.get("/devices", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert "pages" in body
    assert len(body["items"]) == 2


def test_search_pagination(app_client):
    """GET /devices/?page=1&pageSize=1 returns correct page metadata."""
    test_init()

    r = app_client.post("/devices", json=DEVICE_DATA, headers=headers)
    assert r.status_code == 201

    d2 = DEVICE_DATA.copy()
    d2["chipId"] = "BBBBBB"
    app_client.post("/devices", json=d2, headers=headers)

    r = app_client.get("/devices/?page=1&pageSize=1", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["pages"] == 2
    assert len(body["items"]) == 1


def test_token_generation(app_client):
    """POST /devices/{id}/token returns a fresh 32-char token."""
    test_init()
    r = app_client.post("/devices", json=DEVICE_DATA, headers=headers)
    assert r.status_code == 201
    device_id = json.loads(r.text)["id"]

    r = app_client.post(f"/devices/{device_id}/token", headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert "token" in data
    assert len(data["token"]) == 32

    # Non-existent UUID returns 404
    r = app_client.post(f"/devices/{uuid.uuid4()}/token", headers=headers)
    assert r.status_code == 404


def test_get_token(app_client):
    """GET /devices/{id}/token returns the device's current token."""
    test_init()
    r = app_client.post("/devices", json=DEVICE_DATA, headers=headers)
    assert r.status_code == 201
    device_id = json.loads(r.text)["id"]
    created_token = json.loads(r.text)["token"]

    r = app_client.get(f"/devices/{device_id}/token", headers=headers)
    assert r.status_code == 200
    assert json.loads(r.text)["token"] == created_token

    # Non-existent UUID returns 404
    r = app_client.get(f"/devices/{uuid.uuid4()}/token", headers=headers)
    assert r.status_code == 404


def test_delete_device_not_found(app_client):
    """DELETE /devices/{unknown_id} returns 404."""
    r = app_client.delete(f"/devices/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404


def test_device_logs_list(app_client):
    """GET /devices/logs/ returns a list of log files."""
    r = app_client.get("/devices/logs", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_proxy_fetch_connect_error(app_client):
    """POST /devices/proxy-fetch returns 400 when the remote host is unreachable."""
    r = app_client.post(
        "/devices/proxy-fetch",
        json={"url": "http://192.0.2.1/data", "method": "GET", "body": "", "header": ""},
        headers=headers,
    )
    assert r.status_code == 400


def test_proxy_fetch_get(app_client):
    """POST /devices/proxy-fetch with a valid URL returns data."""
    from unittest.mock import (  # pylint: disable=import-outside-toplevel
        AsyncMock, MagicMock, patch)
    mock_response = MagicMock(status_code=200)
    async def response_chunks():
        yield b'{"ok": true}'
    mock_response.aiter_bytes = response_chunks
    mock_response.aclose = AsyncMock()

    with patch(
        "core.utils.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("192.168.1.100", 0))],
    ), \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.build_request = MagicMock()
        mock_client.send = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        r = app_client.post(
            "/devices/proxy-fetch",
            json={"url": "http://device.local/api", "method": "GET", "body": "", "header": ""},
            headers=headers,
        )
    assert r.status_code == 200


def test_config_over_the_size_cap_is_rejected(app_client):
    """An oversized config is refused, not truncated — a truncated config is not a backup."""
    test_init()
    data = DEVICE_DATA.copy()
    data["chipId"] = "toobig01"
    data["config"] = {"blob": "x" * 20000}

    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 422
    assert json.loads(r.text)["error"] == "payload_too_large"


def test_config_cap_is_configurable(app_client, monkeypatch):
    """The cap comes from MAX_ENVELOPE_BYTES, so an operator can raise it."""
    from core.schemas.envelope import max_envelope_bytes

    get_settings.cache_clear()
    monkeypatch.setenv("MAX_ENVELOPE_BYTES", "64")
    try:
        assert max_envelope_bytes() == 64
    finally:
        monkeypatch.delenv("MAX_ENVELOPE_BYTES", raising=False)
        get_settings.cache_clear()
