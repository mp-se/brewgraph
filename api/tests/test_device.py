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
from oss.gravity_formula import GRAVITY_FORMULA_MAX_LENGTH
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


def test_gravity_formula_data_round_trips_for_supported_device_types(app_client):
    """Formula and SG calibration points persist as explicit device fields."""
    test_init()
    points = [
        {"angle": 15, "gravity": 0.98},
        {"angle": 90, "gravity": 1.25},
    ]

    for index, device_type in enumerate(("gravitymon", "ispindel")):
        data = DEVICE_DATA.copy()
        data.update({
            "chipId": f"CAL{index:03d}",
            "deviceType": device_type,
            "gravityFormula": "1.08 - 0.001 * tilt",
            "gravityCalibrationData": points,
        })
        response = app_client.post("/devices", json=data, headers=headers)
        assert response.status_code == 201
        device_id = response.json()["id"]

        fetched = app_client.get(f"/devices/{device_id}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["gravityFormula"] == data["gravityFormula"]
        assert fetched.json()["gravityCalibrationData"] == points

        replacement = [{"angle": 30, "gravity": 1.075}]
        updated = app_client.patch(
            f"/devices/{device_id}",
            json={"gravityCalibrationData": replacement},
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["gravityCalibrationData"] == replacement


def test_gravity_calibration_accepts_twenty_points_and_rejects_twenty_one(app_client):
    """The API accepts the per-device cap and rejects, rather than truncates, overflow."""
    test_init()
    points = [
        {"angle": 20 + index, "gravity": 1.1 - (index / 1000)}
        for index in range(20)
    ]
    data = DEVICE_DATA.copy()
    data["gravityCalibrationData"] = points
    accepted = app_client.post("/devices", json=data, headers=headers)
    assert accepted.status_code == 201
    assert len(accepted.json()["gravityCalibrationData"]) == 20

    overflow = DEVICE_DATA.copy()
    overflow["chipId"] = "OVER20"
    overflow["gravityCalibrationData"] = points + [{"angle": 45, "gravity": 1.05}]
    rejected = app_client.post("/devices", json=overflow, headers=headers)
    assert rejected.status_code == 422
    updated = app_client.patch(
        f"/devices/{accepted.json()['id']}",
        json={"gravityCalibrationData": overflow["gravityCalibrationData"]},
        headers=headers,
    )
    assert updated.status_code == 422


def test_gravity_calibration_rejects_invalid_point_values(app_client):
    """Calibration values must be finite and within supported physical bounds."""
    test_init()
    data = DEVICE_DATA.copy()
    data["gravityCalibrationData"] = [{"angle": 14.99, "gravity": 1.05}]
    assert app_client.post("/devices", json=data, headers=headers).status_code == 422

    data["chipId"] = "BADSG1"
    data["gravityCalibrationData"] = [{"angle": 45, "gravity": 1.26}]
    assert app_client.post("/devices", json=data, headers=headers).status_code == 422

    data["chipId"] = "BADANG1"
    data["gravityCalibrationData"] = [{"angle": 90.01, "gravity": 1.05}]
    assert app_client.post("/devices", json=data, headers=headers).status_code == 422

    data["chipId"] = "BADFORM"
    data.pop("gravityCalibrationData")
    data["gravityFormula"] = "x" * 257
    assert app_client.post("/devices", json=data, headers=headers).status_code == 422


def test_gravity_calibration_is_restricted_to_supported_device_types(app_client):
    """Other device types cannot create or retain Gravitymon/iSpindel calibration data."""
    test_init()
    data = DEVICE_DATA.copy()
    data["deviceType"] = "pressuremon"
    data["gravityFormula"] = "tilt"
    assert app_client.post("/devices", json=data, headers=headers).status_code == 422

    data = DEVICE_DATA.copy()
    device = app_client.post("/devices", json=data, headers=headers).json()
    configured = app_client.patch(
        f"/devices/{device['id']}",
        json={
            "gravityFormula": "tilt",
            "gravityCalibrationData": [{"angle": 45, "gravity": 1.05}],
        },
        headers=headers,
    )
    assert configured.status_code == 200
    rejected = app_client.patch(
        f"/devices/{device['id']}", json={"deviceType": "pressuremon"}, headers=headers
    )
    assert rejected.status_code == 422

    cleared = app_client.patch(
        f"/devices/{device['id']}",
        json={
            "deviceType": "pressuremon",
            "gravityFormula": None,
            "gravityCalibrationData": [],
        },
        headers=headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["gravityFormula"] is None
    assert cleared.json()["gravityCalibrationData"] == []


def _post_calibrated(app_client, chip_id, **fields):
    """POST a device with the shared fixture data plus the given overrides."""
    data = DEVICE_DATA.copy()
    data["chipId"] = chip_id
    data.update(fields)
    return app_client.post("/devices", json=data, headers=headers)


def test_gravity_calibration_rejects_duplicate_angle(app_client):
    """Two points at the same angle are a validation error on create and update."""
    test_init()
    duplicate = [{"angle": 45, "gravity": 1.05}, {"angle": 45.0, "gravity": 1.06}]
    assert _post_calibrated(
        app_client, "DUP001", gravityCalibrationData=duplicate
    ).status_code == 422

    created = _post_calibrated(app_client, "DUP002")
    assert created.status_code == 201
    rejected = app_client.patch(
        f"/devices/{created.json()['id']}",
        json={"gravityCalibrationData": duplicate},
        headers=headers,
    )
    assert rejected.status_code == 422
    unchanged = app_client.get(f"/devices/{created.json()['id']}", headers=headers)
    assert unchanged.json()["gravityCalibrationData"] == []


def test_gravity_calibration_null_is_stored_as_empty_array(app_client):
    """Omitted and null calibration data both read back as []."""
    test_init()
    omitted = _post_calibrated(app_client, "NUL001")
    assert omitted.status_code == 201
    assert omitted.json()["gravityCalibrationData"] == []

    explicit = _post_calibrated(app_client, "NUL002", gravityCalibrationData=None)
    assert explicit.status_code == 201
    assert explicit.json()["gravityCalibrationData"] == []
    fetched = app_client.get(f"/devices/{explicit.json()['id']}", headers=headers)
    assert fetched.json()["gravityCalibrationData"] == []


def test_gravity_calibration_patch_omitted_untouched_and_null_clears(app_client):
    """PATCH leaves omitted calibration data alone; an explicit null clears it to []."""
    test_init()
    points = [{"angle": 30, "gravity": 1.07}]
    created = _post_calibrated(
        app_client, "PAT001", gravityCalibrationData=points, gravityFormula="tilt"
    )
    device_id = created.json()["id"]

    other = app_client.patch(f"/devices/{device_id}", json={"name": "renamed"}, headers=headers)
    assert other.status_code == 200
    assert other.json()["gravityCalibrationData"] == points
    assert other.json()["gravityFormula"] == "tilt"

    cleared = app_client.patch(
        f"/devices/{device_id}",
        json={"gravityCalibrationData": None, "gravityFormula": None},
        headers=headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["gravityCalibrationData"] == []
    assert cleared.json()["gravityFormula"] is None


def test_gravity_formula_blank_is_stored_as_null(app_client):
    """An empty or whitespace-only formula means no formula."""
    test_init()
    for index, blank in enumerate(("", "   \t")):
        created = _post_calibrated(app_client, f"BLK00{index}", gravityFormula=blank)
        assert created.status_code == 201
        assert created.json()["gravityFormula"] is None

    withformula = _post_calibrated(app_client, "BLK009", gravityFormula="tilt")
    patched = app_client.patch(
        f"/devices/{withformula.json()['id']}", json={"gravityFormula": "  "}, headers=headers
    )
    assert patched.status_code == 200
    assert patched.json()["gravityFormula"] is None


def test_gravity_calibration_boundaries(app_client):
    """Angle 15..90 and gravity 0.98..1.25 are inclusive; just outside is rejected."""
    test_init()
    cases = [
        ({"angle": 14.99, "gravity": 1.05}, 422),
        ({"angle": 15, "gravity": 1.05}, 201),
        ({"angle": 90, "gravity": 1.05}, 201),
        ({"angle": 90.01, "gravity": 1.05}, 422),
        ({"angle": 45, "gravity": 0.979}, 422),
        ({"angle": 45, "gravity": 0.98}, 201),
        ({"angle": 45, "gravity": 1.25}, 201),
        ({"angle": 45, "gravity": 1.251}, 422),
    ]
    for index, (point, expected) in enumerate(cases):
        response = _post_calibrated(
            app_client, f"BND{index:03d}", gravityCalibrationData=[point]
        )
        assert response.status_code == expected, point


def test_gravity_calibration_rejected_on_gateway_device(app_client):
    """The gateway stores nothing itself, so it accepts neither formula nor points."""
    test_init()
    assert _post_calibrated(
        app_client, "GW0001", deviceType="gravitymon_gateway", gravityFormula="tilt"
    ).status_code == 422
    assert _post_calibrated(
        app_client,
        "GW0002",
        deviceType="gravitymon_gateway",
        gravityCalibrationData=[{"angle": 45, "gravity": 1.05}],
    ).status_code == 422
    plain = _post_calibrated(app_client, "GW0003", deviceType="gravitymon_gateway")
    assert plain.status_code == 201


def test_gravity_calibration_accepted_when_device_type_unknown(app_client):
    """A device whose type is not yet known may carry calibration."""
    test_init()
    created = _post_calibrated(
        app_client, "UNK001", deviceType=None, gravityFormula="tilt"
    )
    assert created.status_code == 201


def test_gravity_fields_round_trip_through_list_and_restore(app_client):
    """What a backup reads from GET /devices can be POSTed back unchanged and validated."""
    test_init()
    points = [{"angle": 20, "gravity": 1.1}, {"angle": 60, "gravity": 1.02}]
    original = _post_calibrated(
        app_client, "RST001", gravityFormula="1.1 - 0.001 * tilt", gravityCalibrationData=points
    )
    assert original.status_code == 201

    listed = app_client.get("/devices", headers=headers).json()
    items = listed["items"] if isinstance(listed, dict) else listed
    exported = next(d for d in items if d["chipId"] == "RST001")
    assert exported["gravityFormula"] == "1.1 - 0.001 * tilt"
    assert exported["gravityCalibrationData"] == points

    restore = {k: exported[k] for k in (
        "name", "deviceType", "gravityFormula", "gravityCalibrationData"
    )}
    restore["chipId"] = "RST003"  # the original row still holds RST001
    restored = app_client.post("/devices", json=restore, headers=headers)
    assert restored.status_code == 201
    assert restored.json()["gravityFormula"] == exported["gravityFormula"]
    assert restored.json()["gravityCalibrationData"] == points

    tampered = dict(restore, chipId="RST002", gravityCalibrationData=points + points[:1])
    assert app_client.post("/devices", json=tampered, headers=headers).status_code == 422


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


def _unit(response):
    """The gravityFormulaUnit of a successful device response."""
    assert response.status_code in (200, 201), response.text
    return response.json()["gravityFormulaUnit"]


def test_formula_unit_defaults_follow_the_family(app_client):
    """A stored null reads back as the family default: sg, plato, or sg for `[SG]` names."""
    test_init()
    cases = [
        ("gravitymon", "Gravitymon", "sg"),
        ("ispindel", "iSpindel", "plato"),
        ("ispindel", "[SG] iSpindel", "sg"),
        ("ispindel", "My [SG] iSpindel", "plato"),
        (None, "Unknown", "sg"),
    ]
    for index, (device_type, name, expected) in enumerate(cases):
        created = _post_calibrated(
            app_client, f"UNT{index:03d}", deviceType=device_type, name=name
        )
        assert _unit(created) == expected
        fetched = app_client.get(f"/devices/{created.json()['id']}", headers=headers)
        assert _unit(fetched) == expected


def test_formula_unit_explicit_values_and_null_reset(app_client):
    """An iSpindel keeps an explicit sg or plato; writing null selects the default again."""
    test_init()
    device = _post_calibrated(
        app_client, "UNT100", deviceType="ispindel", name="Plain", gravityFormulaUnit="sg"
    )
    assert _unit(device) == "sg"
    url = f"/devices/{device.json()['id']}"

    assert _unit(app_client.patch(url, json={"gravityFormulaUnit": "plato"}, headers=headers)) == "plato"
    # An unrelated update leaves the stored unit alone.
    assert _unit(app_client.patch(url, json={"description": "x"}, headers=headers)) == "plato"
    assert _unit(app_client.patch(url, json={"gravityFormulaUnit": None}, headers=headers)) == "plato"
    sg_named = app_client.patch(
        url, json={"gravityFormulaUnit": "sg", "name": "[SG] Plain"}, headers=headers
    )
    assert _unit(sg_named) == "sg"
    assert _unit(app_client.patch(url, json={"gravityFormulaUnit": None}, headers=headers)) == "sg"

    assert app_client.patch(
        url, json={"gravityFormulaUnit": "brix"}, headers=headers
    ).status_code == 422


def test_formula_unit_is_the_users_choice_on_every_gravity_device(app_client):
    """SG and plato are both accepted on Gravitymon and iSpindel; null returns the family default."""
    test_init()
    for index, device_type in enumerate(("gravitymon", "ispindel")):
        device = _post_calibrated(
            app_client, f"UNT20{index}", deviceType=device_type, gravityFormulaUnit="plato"
        )
        assert _unit(device) == "plato"
        url = f"/devices/{device.json()['id']}"
        assert _unit(app_client.patch(
            url, json={"gravityFormulaUnit": "sg"}, headers=headers
        )) == "sg"
        assert _unit(app_client.patch(
            url, json={"gravityFormulaUnit": None}, headers=headers
        )) == ("sg" if device_type == "gravitymon" else "plato")


def test_formula_unit_revalidated_when_device_type_changes(app_client):
    """Changing the type must not leave a formula unit on a device outside the formula scope."""
    test_init()
    device = _post_calibrated(
        app_client, "UNT300", deviceType="ispindel", gravityFormulaUnit="plato"
    )
    url = f"/devices/{device.json()['id']}"
    assert app_client.patch(
        url, json={"deviceType": "pressuremon"}, headers=headers
    ).status_code == 422
    moved = app_client.patch(url, json={"deviceType": "gravitymon"}, headers=headers)
    assert moved.status_code == 200
    assert _unit(moved) == "plato"


def test_formula_unit_rejected_on_non_gravity_device(app_client):
    """A unit on a device type outside the formula scope is rejected; none is reported."""
    test_init()
    for index, device_type in enumerate(("pressuremon", "gravitymon_gateway")):
        assert _post_calibrated(
            app_client, f"UNT40{index}", deviceType=device_type, gravityFormulaUnit="sg"
        ).status_code == 422
    plain = _post_calibrated(app_client, "UNT410", deviceType="pressuremon")
    assert plain.status_code == 201
    assert plain.json()["gravityFormulaUnit"] is None


def test_formula_unit_default_follows_name_change_while_stored_null(app_client):
    """Renaming to or from the `[SG]` prefix moves the effective unit of a null-stored device."""
    test_init()
    device = _post_calibrated(app_client, "UNT500", deviceType="ispindel", name="Tilt")
    url = f"/devices/{device.json()['id']}"
    assert _unit(device) == "plato"
    assert _unit(app_client.patch(url, json={"name": "[SG] Tilt"}, headers=headers)) == "sg"
    assert _unit(app_client.patch(url, json={"name": "Tilt"}, headers=headers)) == "plato"
    # Changing the type also moves it.
    assert _unit(
        app_client.patch(url, json={"deviceType": "gravitymon"}, headers=headers)
    ) == "sg"


def test_formula_unit_round_trips_through_list(app_client):
    """The effective unit in a list read can be POSTed back unchanged."""
    test_init()
    _post_calibrated(app_client, "UNT600", deviceType="ispindel", name="Round")
    listed = app_client.get("/devices", headers=headers).json()
    items = listed["items"] if isinstance(listed, dict) else listed
    exported = next(d for d in items if d["chipId"] == "UNT600")
    assert exported["gravityFormulaUnit"] == "plato"
    restore = {k: exported[k] for k in ("name", "deviceType", "gravityFormulaUnit")}
    restore["chipId"] = "UNT601"
    assert _unit(app_client.post("/devices", json=restore, headers=headers)) == "plato"


def test_formula_language_is_validated_on_create_and_update(app_client):
    """The API stores only formulas in the shared bounded language."""
    test_init()
    for index, formula in enumerate(("tilt + unknown", "tilt^7", "tilt;1", "1 +")):
        response = _post_calibrated(
            app_client, f"LANG{index:02d}", deviceType="gravitymon", gravityFormula=formula
        )
        assert response.status_code == 422, response.text

    formula = "tilt" + " " * (GRAVITY_FORMULA_MAX_LENGTH - len("tilt"))
    device = _post_calibrated(
        app_client, "LANG50", deviceType="gravitymon", gravityFormula=formula
    )
    assert device.status_code == 201, device.text
    url = f"/devices/{device.json()['id']}"
    assert app_client.patch(
        url, json={"gravityFormula": "tilt + constructor"}, headers=headers
    ).status_code == 422
    assert app_client.get(url, headers=headers).json()["gravityFormula"] == formula
    assert _post_calibrated(
        app_client, "LANG51", deviceType="gravitymon", gravityFormula=formula + " "
    ).status_code == 422
