# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for chamber/temperature ingestion endpoints."""
import uuid
from unittest.mock import patch

import pytest

from starlette.exceptions import HTTPException

from core.config import get_settings
from core.db import create_session
from core.enums import DeviceType, IngestionSource
from core.models.platform import IngestionLog
from core.models.registry import resolve_model
from oss.routers.ingest import _detect_device_type
from oss.routers.ingest.chamber import _parse_temp
from tests.conftest import DEVICE_DEFAULTS, truncate_database

Device = resolve_model("Device")
Batch = resolve_model("Batch")
TempReading = resolve_model("TempReading")

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def _create_device(app_client, chip_id: str, device_type: str = "gravitymon") -> dict:
    # `deviceType` must come *after* the splat: DEVICE_DEFAULTS carries its own key
    # of the same name, which would otherwise silently override this argument.
    data = {
        "name": f"Device {chip_id}",
        "chipId": chip_id,
        **DEVICE_DEFAULTS,
        "deviceType": device_type,
    }
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# _detect_device_type chamber detection tests
# ---------------------------------------------------------------------------

def test_detect_chamber():
    """Temperature-only payload -> CHAMBER_CONTROLLER."""
    assert _detect_device_type({"beer_temperature": 18.5}) == \
        DeviceType.CHAMBER_CONTROLLER


def test_detect_chamber_with_fridge_temp():
    """Chamber detection with fridge-temp field."""
    assert _detect_device_type({"beer_temperature": 18.5, "fridge_temperature": 4.2}) == \
        DeviceType.CHAMBER_CONTROLLER


def test_detect_chamber_ignores_angle():
    """Payload with temperature and angle -> ISPINDEL, not CHAMBER_CONTROLLER."""
    assert _detect_device_type({"beer_temperature": 18.5, "angle": 25.0}) == \
        DeviceType.CHAMBER_CONTROLLER


def test_detect_chamber_ignores_gravity():
    """Payload with temperature and gravity -> ISPINDEL, not CHAMBER_CONTROLLER."""
    assert _detect_device_type({"beer_temperature": 18.5, "gravity": 1.050}) == \
        DeviceType.CHAMBER_CONTROLLER


def test_detect_chamber_ignores_gravity_unit():
    """Payload with temperature and gravity-unit -> GRAVITYMON, not CHAMBER_CONTROLLER."""
    assert _detect_device_type({"beer_temperature": 18.5, "gravity-unit": "SG"}) == \
        DeviceType.CHAMBER_CONTROLLER


def test_detect_chamber_ignores_pour():
    """Payload with temperature and pour_volume -> KEGMON, not CHAMBER_CONTROLLER."""
    assert _detect_device_type({"beer_temperature": 18.5, "pour_volume": 0.5}) == \
        DeviceType.CHAMBER_CONTROLLER


# ---------------------------------------------------------------------------
# _parse_temp unit conversion and error handling
# ---------------------------------------------------------------------------

def test_parse_temp_celsius():
    """Temperature in Celsius is returned as-is."""
    result = _parse_temp(20.5, "C")
    assert result == 20.5


def test_parse_temp_fahrenheit():
    """Temperature in Fahrenheit is converted to Celsius."""
    result = _parse_temp(68.0, "F")
    assert abs(result - 20.0) < 0.01


def test_parse_temp_fahrenheit_case_insensitive():
    """Unit 'f' (lowercase) is also recognized for Fahrenheit."""
    result = _parse_temp(32.0, "f")
    assert abs(result - 0.0) < 0.01


def test_parse_temp_invalid_string_raises_422():
    """Non-numeric temperature string raises HTTP 422."""
    with pytest.raises(HTTPException) as exc_info:
        _parse_temp("not-a-number", "C")
    assert exc_info.value.status_code == 422
    assert "must be a number" in exc_info.value.detail


def test_parse_temp_none_raises_422():
    """None as temperature raises HTTP 422."""
    with pytest.raises(HTTPException) as exc_info:
        _parse_temp(None, "C")
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# Chamber endpoint tests
# ---------------------------------------------------------------------------

def test_chamber_ingest_with_device_token(app_client):
    """POST /ingest/chamber with device token writes temp if device has active batch/vessel."""
    truncate_database()
    device = _create_device(app_client, "CHMD01", "gravitymon")
    token = device["token"]

    payload = {
        "current_mode": "R", "token": token,
        "beer_temperature": 18.5,
        "temp_units": "C",
    }
    r = app_client.post("/ingest/chamber", json=payload)
    # Returns 200 even if no batch (write_temp silently drops if no active batch)
    assert r.status_code == 200


def test_chamber_direct_endpoint_enforces_device_request_quota(app_client):
    """POST /ingest/chamber (the dedicated route) must reject an over-quota
    device the same way /ingest/dispatch's chamber path already does —
    regression for the asymmetry where this route bypassed
    `_check_device_request_quota` entirely."""
    truncate_database()
    device = _create_device(app_client, "CHQ001", "gravitymon")
    payload = {
        "current_mode": "R", "token": device["token"],
        "beer_temperature": 18.5, "temp_units": "C",
    }
    with patch("core.middleware.auth.increment_key", return_value=61):
        r = app_client.post("/ingest/chamber", json=payload)
    assert r.status_code == 429


def test_dispatch_chamber_path_enforces_device_request_quota(app_client):
    """POST /ingest/dispatch with a chamber payload rejects the same
    over-quota device — the parity counterpart of the direct-route test above,
    now sharing the exact same `_process_chamber` code path."""
    truncate_database()
    device = _create_device(app_client, "CHQ002", "gravitymon")
    payload = {
        "current_mode": "R", "token": device["token"],
        "beer_temperature": 18.5, "temp_units": "C",
    }
    with patch("core.middleware.auth.increment_key", return_value=61):
        r = app_client.post("/ingest/dispatch", json=payload)
    assert r.status_code == 429


def _assign_device_to_batch(app_client, device_id: str, batch_id: str) -> None:
    r = app_client.patch(
        f"/devices/{device_id}", json={"batchId": batch_id}, headers=headers
    )
    assert r.status_code == 200


def _temp_rows(**filters):
    session = create_session()
    q = session.query(TempReading)
    for key, value in filters.items():
        q = q.filter(getattr(TempReading, key) == uuid.UUID(value))
    return q.order_by(TempReading.temp_type).all()


def test_chamber_writes_both_beer_and_fridge_temps(app_client):
    """Both beer-temp and fridge-temp are stored, tagged beer and chamber.

    Previously write_temp collapsed them with `temperature if not None else fridge_temp`
    and wrote a single row, so the chamber reading was discarded whenever a beer reading
    was also present.
    """
    truncate_database()
    device = _create_device(app_client, "CHMB01", "gravitymon")
    batch = app_client.post("/batches", json={"name": "Ambient B"}, headers=headers).json()
    _assign_device_to_batch(app_client, device["id"], batch["id"])

    r = app_client.post("/ingest/chamber", json={
        "current_mode": "R", "token": device["token"],
        "beer_temperature": 18.5, "fridge_temperature": 4.25,
        "temp_units": "C",
    })
    assert r.status_code == 200

    rows = _temp_rows(batch_id=batch["id"])
    assert [(x.temp_type, x.temperature) for x in rows] == [
        ("beer", 18.5), ("chamber", 4.25),
    ]

def test_chamber_battery_persists_when_reported(app_client):
    """A chamber poll carrying a battery value stores it, on every row it produces.

    Regression guard for TempReading having no battery column at all: this asserts
    the real numeric value round-trips, not just that the field exists.
    """
    truncate_database()
    device = _create_device(app_client, "CHMB02", "gravitymon")
    batch = app_client.post("/batches", json={"name": "Battery B"}, headers=headers).json()
    _assign_device_to_batch(app_client, device["id"], batch["id"])

    r = app_client.post("/ingest/chamber", json={
        "current_mode": "R", "token": device["token"],
        "beer_temperature": 18.5, "fridge_temperature": 4.25,
        "temp_units": "C", "battery": 3.87,
    })
    assert r.status_code == 200

    rows = _temp_rows(batch_id=batch["id"])
    assert [(x.temp_type, x.battery) for x in rows] == [
        ("beer", 3.87), ("chamber", 3.87),
    ]


def test_chamber_without_battery_still_ingests(app_client):
    """A chamber poll with no battery field still ingests, and stores battery=None."""
    truncate_database()
    device = _create_device(app_client, "CHMB03", "gravitymon")
    batch = app_client.post("/batches", json={"name": "No Battery B"}, headers=headers).json()
    _assign_device_to_batch(app_client, device["id"], batch["id"])

    r = app_client.post("/ingest/chamber", json={
        "current_mode": "R", "token": device["token"],
        "beer_temperature": 18.5, "fridge_temperature": 4.25,
        "temp_units": "C",
    })
    assert r.status_code == 200

    rows = _temp_rows(batch_id=batch["id"])
    assert [(x.temp_type, x.battery) for x in rows] == [
        ("beer", None), ("chamber", None),
    ]



def test_chamber_fridge_only_is_tagged_chamber_not_beer(app_client):
    """A lone fridge-temp is stored as `chamber`, not mislabelled `beer`."""
    truncate_database()
    device = _create_device(app_client, "CHMB02", "gravitymon")
    batch = app_client.post("/batches", json={"name": "Fridge only"}, headers=headers).json()
    _assign_device_to_batch(app_client, device["id"], batch["id"])

    r = app_client.post("/ingest/chamber", json={
        "current_mode": "R", "token": device["token"], "fridge_temperature": 3.5, "temp_units": "C",
    })
    assert r.status_code == 200

    rows = _temp_rows(batch_id=batch["id"])
    assert len(rows) == 1
    assert rows[0].temp_type == "chamber"
    assert rows[0].temperature == 3.5


def test_vessel_without_batch_still_records(app_client):
    """A keg in storage with no batch records its temperature with batch_id NULL.

    This is the primary use case for a vessel-linked probe -- a storage fridge with no
    active fermentation. write_temp records these readings unconditionally; this test
    covers the case where batch_id is NULL because a keg is emptied.
    """
    truncate_database()
    device = _create_device(app_client, "CHMB03", "gravitymon")
    batch = app_client.post("/batches", json={"name": "Kegged"}, headers=headers).json()
    vessel = app_client.post("/vessels", json={
        "batchId": batch["id"], "vesselNumber": 1, "vesselType": "keg", "name": "Storage Keg",
        "fillDate": "2026-05-01", "totalVolume": 19.0, "volumeRemaining": 19.0,
        "status": "filled",
    }, headers=headers).json()

    # Empty the keg: clears batch_id, sets status clean.
    assert app_client.patch(
        f"/vessels/{vessel['id']}", json={"batchId": None}, headers=headers
    ).status_code == 200

    assert app_client.patch(
        f"/devices/{device['id']}", json={"vesselId": vessel["id"]}, headers=headers
    ).status_code == 200

    r = app_client.post("/ingest/chamber", json={
        "current_mode": "R", "token": device["token"], "beer_temperature": 5.5, "temp_units": "C",
    })
    assert r.status_code == 200

    rows = _temp_rows(vessel_id=vessel["id"])
    assert len(rows) == 1, "storage temp for a batchless keg must be recorded, not dropped"
    assert rows[0].batch_id is None
    assert rows[0].temperature == 5.5


def test_chamber_fahrenheit_conversion(app_client):
    """POST /ingest/chamber converts Fahrenheit to Celsius."""
    truncate_database()
    device = _create_device(app_client, "CHMF01", "gravitymon")
    token = device["token"]

    payload = {
        "name": "PressureMon",
        "current_mode": "R", "token": token,
        "beer_temperature": 68.0,
        "temp_units": "F",
    }
    r = app_client.post("/ingest/chamber", json=payload)
    assert r.status_code == 200


def test_chamber_missing_temperature_returns_422(app_client):
    """POST /ingest/chamber without temperature returns 422 with the normative envelope.

    The raw per-field validation detail is logged server-side, not returned to the client — this
    only checks the status and envelope shape, not the field-level text.
    """
    truncate_database()
    r = app_client.post("/ingest/chamber", json={"current_mode": "R", "token": "some-token"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "validation_error"
    assert "requestId" in body


def test_chamber_invalid_temperature_returns_422(app_client):
    """POST /ingest/chamber with non-numeric temperature returns 422."""
    truncate_database()
    r = app_client.post(
        "/ingest/chamber",
        json={"current_mode": "R", "token": "some-token", "beer_temperature": "not-a-number"}
    )
    assert r.status_code == 422


def test_chamber_invalid_fridge_temp_returns_422(app_client):
    """POST /ingest/chamber with non-numeric fridge-temp returns 422."""
    truncate_database()
    truncate_database()
    device = _create_device(app_client, "CHMC01", "gravitymon")
    r = app_client.post(
        "/ingest/chamber",
        json={
            "current_mode": "R", "token": device["token"],
            "beer_temperature": 20.0,
            "fridge_temperature": "invalid"
        }
    )
    assert r.status_code == 422


def test_chamber_unknown_token_returns_401(app_client):
    """POST /ingest/chamber with unregistered token returns 401.

    This route (``ingest_temp``) delegates into ``_process_chamber``, the same
    core logic ``/ingest/dispatch`` uses for chamber payloads, which logs
    ``log_ingestion_error`` synchronously rather than via
    ``background_tasks.add_task`` before raising ``HTTPException`` — the app's
    global exception handler builds a fresh ``JSONResponse`` with no background
    tasks attached, so a queued task would never run and no ``IngestionLog``
    row would ever be written for this endpoint.
    """
    truncate_database()
    r = app_client.post(
        "/ingest/chamber",
        json={"current_mode": "R", "token": "unknown-token", "beer_temperature": 20.0}
    )
    assert r.status_code == 401

    session = create_session()
    try:
        rows = session.query(IngestionLog).filter(
            IngestionLog.source_type == IngestionSource.CHAMBER.value,
            IngestionLog.reason == "unknown_token",
        ).all()
        assert len(rows) == 1, (
            "unknown-token drop on /ingest/chamber must write an IngestionLog row"
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Chip-ID fallback
#
# `chamber_controller` joined {ispindel, gravitymon, pressuremon} in
# `resolve_device`'s fallback set so a BLE chamber broadcast — a chip ID and two
# temperatures, nothing else — can be bridged without a per-device token. Like the
# other members this is a trusted-LAN convenience, not authentication.
# ---------------------------------------------------------------------------

def test_chamber_ingest_resolves_by_chip_id_without_token(app_client):
    """A chamber with no token supplied resolves by its unique configured chip ID."""
    truncate_database()
    _create_device(app_client, "CHMBLE1", DeviceType.CHAMBER_CONTROLLER.value)

    r = app_client.post(
        "/ingest/chamber",
        json={"current_mode": "O", "id": "CHMBLE1", "beer_temperature": 18.5},
    )
    assert r.status_code == 200


def test_chamber_chip_id_fallback_is_device_type_scoped(app_client):
    """A gravitymon with the same chip ID must not answer a chamber post.

    The fallback matches on (chip_id, device_type). Without the type scope a
    chamber reading could be attributed to a hydrometer that happens to share an ID.
    """
    truncate_database()
    _create_device(app_client, "SHARED1", "gravitymon")

    r = app_client.post(
        "/ingest/chamber",
        json={"current_mode": "O", "id": "SHARED1", "beer_temperature": 18.5},
    )
    assert r.status_code == 401


def test_chamber_unknown_chip_id_returns_401(app_client):
    """An unregistered chip ID is refused, exactly as an unregistered token is."""
    truncate_database()
    r = app_client.post(
        "/ingest/chamber",
        json={"current_mode": "O", "id": "NOSUCH1", "beer_temperature": 18.5},
    )
    assert r.status_code == 401


def test_chamber_accepts_a_poll_with_no_current_mode(app_client):
    """`current_mode` is optional.

    It is read by nothing — `resolve_chamber_mode` derives the returned
    setpoint entirely from batch state, so a controller's self-reported mode
    never influences the answer. Requiring it would force producers that
    genuinely have no mode, such as a BLE bridge seeing two temperatures in a
    broadcast, to invent one.
    """
    truncate_database()
    device = _create_device(app_client, "CHMNM01", DeviceType.CHAMBER_CONTROLLER.value)

    r = app_client.post(
        "/ingest/chamber",
        json={"token": device["token"], "beer_temperature": 18.5},
    )
    assert r.status_code == 200
    # The response still carries a mode: it is the server's instruction, not an echo.
    assert "mode" in r.json()


def test_chamber_still_rejects_an_invalid_current_mode(app_client):
    """Optional is not unvalidated — a value outside the enum is still refused."""
    truncate_database()
    device = _create_device(app_client, "CHMNM02", DeviceType.CHAMBER_CONTROLLER.value)

    r = app_client.post(
        "/ingest/chamber",
        json={"token": device["token"], "beer_temperature": 18.5, "current_mode": "Z"},
    )
    assert r.status_code == 422


def test_chamber_without_token_or_id_returns_422(app_client):
    """A poll identifying no device at all is rejected by the schema, not by a 401."""
    truncate_database()
    r = app_client.post(
        "/ingest/chamber",
        json={"current_mode": "O", "beer_temperature": 18.5},
    )
    assert r.status_code == 422


def test_chamber_valid_token_wins_over_id(app_client):
    """When both are sent the token decides, so a stale `id` cannot redirect a reading."""
    truncate_database()
    device = _create_device(app_client, "CHMTOK1", DeviceType.CHAMBER_CONTROLLER.value)
    _create_device(app_client, "CHMOTH1", DeviceType.CHAMBER_CONTROLLER.value)

    batch = app_client.post(
        "/batches",
        json={"name": "Chamber batch", "brewDate": "2026-08-19", "acceptIngest": True},
        headers=headers,
    )
    assert batch.status_code == 201
    _assign_device_to_batch(app_client, device["id"], batch.json()["id"])

    r = app_client.post(
        "/ingest/chamber",
        json={
            "current_mode": "O",
            "token": device["token"],
            "id": "CHMOTH1",
            "beer_temperature": 18.5,
        },
    )
    assert r.status_code == 200

    rows = _temp_rows(batch_id=batch.json()["id"])
    assert len(rows) == 1
    assert str(rows[0].device_id) == device["id"]


def test_chamber_parse_error_returns_422(app_client):
    """POST /ingest/chamber with invalid JSON returns 422."""
    r = app_client.post(
        "/ingest/chamber",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


def test_chamber_with_source_field(app_client):
    """POST /ingest/chamber respects the 'source' field in payload."""
    truncate_database()
    device = _create_device(app_client, "CHMS01", "gravitymon")
    payload = {
        "current_mode": "R", "token": device["token"],
        "beer_temperature": 19.5,
        "temp_units": "C",
        "source": "mqtt",
    }
    r = app_client.post("/ingest/chamber", json=payload)
    assert r.status_code == 200


def test_chamber_default_source_is_push(app_client):
    """POST /ingest/chamber defaults to 'push' source when not provided."""
    truncate_database()
    device = _create_device(app_client, "CHMU01", "gravitymon")
    payload = {
        "current_mode": "R", "token": device["token"],
        "beer_temperature": 19.5,
        "temp_units": "C",
    }
    r = app_client.post("/ingest/chamber", json=payload)
    assert r.status_code == 200


def test_chamber_default_unit_is_celsius(app_client):
    """POST /ingest/chamber defaults to Celsius when temp-unit not provided."""
    truncate_database()
    device = _create_device(app_client, "CHME01", "gravitymon")
    payload = {
        "current_mode": "R", "token": device["token"],
        "beer_temperature": 20.0,
    }
    r = app_client.post("/ingest/chamber", json=payload)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Dispatch with chamber payload
# ---------------------------------------------------------------------------

def test_dispatch_chamber_payload(app_client):
    """POST /ingest/dispatch routes chamber payload correctly."""
    truncate_database()
    device = _create_device(app_client, "DSCH01", "gravitymon")
    payload = {
        "current_mode": "R", "token": device["token"],
        "beer_temperature": 18.5,
        "fridge_temperature": 4.2,
    }
    r = app_client.post("/ingest/dispatch", json=payload)
    assert r.status_code == 200


def test_dispatch_chamber_unknown_token_returns_401(app_client):
    """POST /ingest/dispatch with chamber payload and unknown token returns 401."""
    truncate_database()
    r = app_client.post(
        "/ingest/dispatch",
        json={"beer_temperature": 20.0, "current_mode": "R", "token": "unknown-chamber-token"}
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Pressuremon with active vessel (vessel_id branch)
# ---------------------------------------------------------------------------

def test_pressuremon_without_vessel_creates_batch(app_client):
    """PressureMon without vessel_id creates a batch before writing pressure."""
    truncate_database()
    device = _create_device(app_client, "PRNV01", "pressuremon")
    token = device["token"]
    device_id = device["id"]

    payload = {
        "name": "PressureMon",
        "current_mode": "R", "token": token,
        "id": "PRNV01",
        "beer_temperature": 20.0,
        "temp_units": "C",
        "pressure": 10.0,
        "pressure_units": "kPa",
        "battery": 3.5,
    }
    r = app_client.post("/ingest/pressuremon", json=payload)
    assert r.status_code == 200

    # Verify batch was created
    batches = app_client.get(f"/batches/?deviceId={device_id}", headers=headers).json()["items"]
    assert len(batches) == 1


# ---------------------------------------------------------------------------
# Edge cases and error paths
# ---------------------------------------------------------------------------

def test_dispatch_parse_error_with_exception(app_client):
    """POST /ingest/dispatch with various invalid content types."""
    r = app_client.post(
        "/ingest/dispatch",
        content=b"\x80\x81\x82",  # Invalid UTF-8
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


def test_chamber_fridge_temp_fahrenheit_conversion(app_client):
    """POST /ingest/chamber converts fridge-temp from Fahrenheit to Celsius."""
    truncate_database()
    device = _create_device(app_client, "CHFF01", "gravitymon")
    payload = {
        "current_mode": "R", "token": device["token"],
        "beer_temperature": 68.0,
        "fridge_temperature": 39.2,
        "temp_units": "F",
    }
    r = app_client.post("/ingest/chamber", json=payload)
    assert r.status_code == 200
