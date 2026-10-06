# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for the ingest-handler registry and a regression guard proving every
currently-served ingest endpoint still accepts a valid payload."""
import hashlib
import uuid as _uuid
from unittest.mock import patch
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from core.config import get_settings
from core.db import get_session
from core.enums import DeviceType
from core.models.registry import resolve_model
from main_oss import app
from oss.registries.ingest_handlers import (
    TypedIngestHandler,
    UntypedIngestHandler,
    ingest_handler_registry,
)
from oss.schemas.ingest import (
    ChamberIngestRequest,
    GravityIngestRequest,
    IspindelIngestRequest,
    KegmonBeerRequest,
    KegmonIngestRequest,
    PressureIngestRequest,
)
from tests.conftest import DEVICE_DEFAULTS, truncate_database

Tap = resolve_model("Tap")
GravityReading = resolve_model("GravityReading")
PressureReading = resolve_model("PressureReading")

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def test_init():
    """Reset database state before test scenarios."""
    truncate_database()


def _create_device(
    app_client, chip_id: str, device_type: str = "gravitymon", device_color: str = "white"
) -> dict:
    data = {
        **DEVICE_DEFAULTS,
        "name": f"Device {chip_id}",
        "deviceType": device_type,
        "chipId": chip_id,
        "deviceColor": device_color,
    }
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


def _create_tap_with_token(app_client, token: str) -> dict:
    r = app_client.post("/taps", json={"name": "Test Tap", "tapNumber": 1}, headers=headers)
    assert r.status_code == 201
    tap_id = r.json()["id"]
    db = next(get_session())
    tap = db.get(Tap, _uuid.UUID(tap_id))
    tap.token = token
    tap.token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.commit()
    return {"id": tap_id, "token": token}


# ---------------------------------------------------------------------------
# Registry membership — one assertion per registered source
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("source,schema,device_type", [
    ("gravitymon", GravityIngestRequest, DeviceType.GRAVITYMON),
    ("ispindel", IspindelIngestRequest, DeviceType.ISPINDEL),
    ("pressuremon", PressureIngestRequest, DeviceType.PRESSUREMON),
    ("chamber", ChamberIngestRequest, DeviceType.CHAMBER_CONTROLLER),
])
def test_typed_source_registered_with_expected_shape(source, schema, device_type):
    """Each device-type-producing ingest source is a ``TypedIngestHandler``
    with its payload schema and device_type — the field is always present."""
    handler = ingest_handler_registry.get(source)
    assert handler is not None
    assert isinstance(handler, TypedIngestHandler)
    assert not isinstance(handler, UntypedIngestHandler)
    assert handler.payload_schema is schema
    assert handler.auth == "device_token"
    assert handler.device_type == device_type


@pytest.mark.parametrize("source,schema,auth", [
    ("kegmon", KegmonIngestRequest, "tap_token"),
    ("kegmon-beer", KegmonBeerRequest, "tap_token"),
])
def test_untyped_source_registered_with_expected_shape(source, schema, auth):
    """Each source with no device type of its own is an ``UntypedIngestHandler``
    — ``device_type`` is structurally absent, not present-and-``None``."""
    handler = ingest_handler_registry.get(source)
    assert handler is not None
    assert isinstance(handler, UntypedIngestHandler)
    assert not isinstance(handler, TypedIngestHandler)
    assert handler.payload_schema is schema
    assert handler.auth == auth
    assert not hasattr(handler, "device_type")


def test_registry_has_no_unexpected_extra_sources():
    """Registers exactly its own sources, nothing beyond them."""
    assert set(ingest_handler_registry.all().keys()) == {
        "gravitymon", "ispindel", "pressuremon", "chamber",
        "kegmon", "kegmon-beer",
    }


def test_unregistered_source_returns_none():
    """A source that was never registered is simply absent, not an error."""
    assert ingest_handler_registry.get("not-a-real-source") is None


# ---------------------------------------------------------------------------
# Regression guard: all listed ingest endpoints still accept a valid
# payload exactly as before the registry was added.
# ---------------------------------------------------------------------------

def test_endpoints_listing_still_works(app_client, monkeypatch):
    """GET /ingest/endpoints still lists all endpoints, as the short public URLs."""
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    test_init()
    r = app_client.get("/ingest/endpoints", headers=headers)
    assert r.status_code == 200
    urls = {e["device"]: urlparse(e["url"]).path for e in r.json()}
    assert {"gravitymon", "ispindel", "pressuremon", "kegmon",
            "chamber", "dispatch"} <= urls.keys()
    # Devices are told the short URL the web proxy exposes, not the canonical
    # /api/ingest/<device> route it rewrites to.
    assert urls == {device: f"/ingest/{device}" for device in urls}


def test_gravitymon_endpoint_still_works(app_client):
    """POST /ingest/gravitymon still accepts a valid payload."""
    test_init()
    device = _create_device(app_client, "REGGM1", "gravitymon")
    payload = {"name": "GravityMon", "id": "REGGM1", "token": device["token"],
               "gravity": 1.050, "gravity-unit": "G", "temperature": 20.0,
               "temp_units": "C", "angle": 30.0, "battery": 4.1, "rssi": -60}
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200


def test_tilt_payload_uses_mapped_device_token_before_storing(app_client):
    """A sidecar-mapped Tilt payload follows the standard device-token identity path."""
    test_init()
    device = _create_device(app_client, "TILT01", device_color="red")
    payload = {
        "name": "GravityMon", "id": "TILT01", "gravity-unit": "G",
        "token": device["token"],
        "gravity": 1.048,
        "temperature": 68.0,
        "temp_units": "F", "rssi": -59,
    }

    response = app_client.post("/ingest/gravitymon", json=payload, headers=headers)

    assert response.status_code == 200, response.text
    db = next(get_session())
    reading = db.scalars(select(GravityReading)).one()
    assert str(reading.device_id) == device["id"]
    assert reading.gravity == pytest.approx(1.048)
    assert reading.temperature == pytest.approx(20.0)


def test_valid_token_wins_over_conflicting_gravitymon_id(app_client):
    """A valid token remains authoritative when uppercase ID names another device."""
    test_init()
    token_device = _create_device(app_client, "TOK001", "gravitymon")
    id_device = _create_device(app_client, "ID0001", "gravitymon")
    payload = {
        "token": token_device["token"],
        "id": id_device["chipId"], "name": "GravityMon",
        "gravity": 1.052, "gravity-unit": "G",
    }

    response = app_client.post("/ingest/gravitymon", json=payload, headers=headers)

    assert response.status_code == 200, response.text
    reading = next(get_session()).scalars(select(GravityReading)).one()
    assert str(reading.device_id) == token_device["id"]


def test_gravitymon_missing_token_falls_back_to_uppercase_id(app_client):
    """A GravityMon measurement may use its unique configured ID on a trusted LAN."""
    test_init()
    device = _create_device(app_client, "GMF001", "gravitymon")

    response = app_client.post(
        "/ingest/gravitymon",
        json={"id": device["chipId"], "name": "GravityMon",
              "gravity": 1.049, "gravity-unit": "G"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    reading = next(get_session()).scalars(select(GravityReading)).one()
    assert str(reading.device_id) == device["id"]


def test_pressuremon_invalid_token_falls_back_to_uppercase_id(app_client):
    """A failed token lookup falls back to a unique PressureMon ID on a trusted LAN."""
    test_init()
    device = _create_device(app_client, "PMF001", "pressuremon")
    payload = {
        "token": "invalid-device-token",
        "id": device["chipId"], "name": "PressureMon",
        "pressure": 14.7, "pressure_units": "psi",
    }

    response = app_client.post("/ingest/pressuremon", json=payload, headers=headers)

    assert response.status_code == 200, response.text
    reading = next(get_session()).scalars(select(PressureReading)).one()
    assert str(reading.device_id) == device["id"]


@pytest.mark.parametrize(
    "identity",
    [
        {},
        {"token": "invalid-device-token", "ID": "UNKNOWN-ID"},
    ],
)
def test_gravitymon_missing_or_invalid_identity_is_rejected(app_client, identity):
    """Missing, unknown, and lowercase-only identity fields preserve the existing 401."""
    test_init()
    _create_device(app_client, "LOWER1", "gravitymon")

    response = app_client.post(
        "/ingest/gravitymon",
        json={**identity, "name": "GravityMon", "gravity": 1.050,
              "gravity-unit": "G"},
        headers=headers,
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Device not registered"


def test_gravitymon_id_fallback_is_type_scoped(app_client):
    """An ID configured for another device type cannot identify a GravityMon reading."""
    test_init()
    device = _create_device(app_client, "TYPE01", "pressuremon")

    response = app_client.post(
        "/ingest/gravitymon",
        json={"id": device["chipId"], "name": "GravityMon",
              "gravity": 1.050, "gravity-unit": "G"},
        headers=headers,
    )

    assert response.status_code == 401


def test_pressuremon_duplicate_chip_id_rejected_at_creation(app_client):
    """Two PressureMon devices configured with the same ID can no longer coexist —
    a DB-level unique index on `(device_type, chip_id)` rejects the second
    `POST /devices` outright, so the ambiguous state that would otherwise reach
    ingest-time device resolution (`resolve_device` → `search_device_identifier`)
    can never exist. Assert the constraint directly.
    """
    test_init()
    _create_device(app_client, "DUP001", "pressuremon")

    data = {
        **DEVICE_DEFAULTS,
        "name": "Device DUP001 (2)",
        "deviceType": "pressuremon",
        "chipId": "DUP001",
        "deviceColor": "white",
    }
    response = app_client.post("/devices", json=data, headers=headers)

    assert response.status_code == 409


def test_device_duplicate_token_collision_surfaces_as_409():
    """A forced `device.token` collision is rejected and translated to 409.

    §9 added a DB-level unique index on `device.token`
    (`uq_device_token`, `api/migrations/versions/000_initial_schema.py`) and
    `BaseService.create()`/`commit()` (used by `DeviceService.create()`) already
    translate an `IntegrityError` at commit into a 409 — that's what the
    sibling test above exercises for `(device_type, chip_id)`. But `token` is
    never set through `DeviceCreate` (see `oss/schemas/device.py` — no `token`
    field); it's assigned afterward by `DeviceService.generate_token()`, called
    separately by `POST /devices` right after `create()` succeeds.
    `generate_token()`'s own commit applies the same
    `IntegrityError` -> `HTTPException(409)` translation `BaseService.create()`/
    `commit()` use.
    Token collisions are practically unreachable in production (24 bytes of
    `secrets.token_urlsafe` entropy per device) — forced here via a patched
    RNG to exercise the real code path rather than assert a status code that
    doesn't match current behavior.
    """
    test_init()
    with TestClient(
        app, base_url="http://testserver/api", raise_server_exceptions=False
    ) as client, patch(
        "oss.services.device.secrets.token_urlsafe", return_value="FIXEDTOKENVALUE"
    ):
        first = _create_device(client, "TOK001")
        assert first["token"] == "FIXEDTOKENVALUE"

        data = {
            **DEVICE_DEFAULTS,
            "name": "Device TOK002",
            "deviceType": "gravitymon",
            "chipId": "TOK002",
            "deviceColor": "white",
        }
        response = client.post("/devices", json=data, headers=headers)

    assert response.status_code == 409


def test_ispindel_endpoint_still_works(app_client):
    """POST /ingest/ispindel still accepts a valid payload."""
    test_init()
    device = _create_device(app_client, "REGIS1", "ispindel")
    payload = {"name": "[SG] iSpindel", "token": device["token"],
               "ID": 13065051, "gravity": 1.050, "temp_units": "C",
               "temperature": 20.0, "angle": 30.0, "battery": 4.1, "RSSI": -60}
    r = app_client.post("/ingest/ispindel", json=payload)
    assert r.status_code == 200


def test_pressuremon_endpoint_still_works(app_client):
    """POST /ingest/pressuremon still accepts a valid payload."""
    test_init()
    device = _create_device(app_client, "REGPR1", "pressuremon")
    payload = {"token": device["token"], "id": "REGPR1", "pressure": 14.7,
               "name": "PressureMon", "pressure_units": "psi", "temp_units": "C",
               "temperature": 21.0, "battery": 3.5, "rssi": -80}
    r = app_client.post("/ingest/pressuremon", json=payload)
    assert r.status_code == 200


def test_chamber_endpoint_still_works(app_client):
    """POST /ingest/chamber still accepts a valid payload."""
    test_init()
    device = _create_device(app_client, "REGCH1", "gravitymon")
    payload = {"token": device["token"], "beer_temperature": 18.5,
               "fridge_temperature": 4.2, "temp_units": "C",
               "current_mode": "B", "current_target": 18.5}
    r = app_client.post("/ingest/chamber", json=payload)
    assert r.status_code == 200


def _setup_tap_with_vessel(app_client, token: str) -> dict:
    """Create a tap with a token and an active vessel assigned to it."""
    tap = _create_tap_with_token(app_client, token)
    batch_id = app_client.post(
        "/batches", json={"name": "Registry Test Batch"}, headers=headers
    ).json()["id"]
    vessel_id = app_client.post(
        "/vessels",
        json={
            "batchId": batch_id,
            "vesselType": "keg",
            "name": "Registry Test Keg",
            "fillDate": "2026-05-01",
            "totalVolume": 20.0,
            "volumeRemaining": 20.0,
            "status": "serving",
        },
        headers=headers,
    ).json()["id"]
    app_client.patch(f"/vessels/{vessel_id}", json={"tapId": tap['id']}, headers=headers)
    return {"id": tap["id"], "token": token, "vessel_id": vessel_id}


def test_kegmon_endpoint_still_works(app_client):
    """POST /ingest/kegmon still accepts a valid payload against a tapped vessel."""
    test_init()
    tap = _setup_tap_with_vessel(app_client, "reg-kegmon-token")
    payload = {"token": tap["token"], "pour": 0.33,
               "volume": 19.67, "maxVolume": 20.0}
    r = app_client.post("/ingest/kegmon", json=payload)
    assert r.status_code == 200


def test_kegmon_pour_is_stamped_with_the_tapped_vessels_batch(app_client):
    """An ingested pour carries the vessel's batch_id, so it appears in the default
    (current-fill) pours list, which filters on PourEvent.batch_id.
    """
    test_init()
    tap = _setup_tap_with_vessel(app_client, "reg-kegmon-batch-token")
    payload = {"token": tap["token"], "pour": 0.33, "volume": 19.67, "maxVolume": 20.0}
    assert app_client.post("/ingest/kegmon", json=payload).status_code == 200

    r = app_client.get(f"/vessels/{tap['vessel_id']}/pours", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


def test_kegmon_pour_with_unresolvable_device_token_still_records(app_client):
    """An unresolvable device_token is ignored, never rejected.

    The pour must still be written and volume_remaining still decremented —
    device_token is supplementary attribution, not authentication.
    """
    test_init()
    tap = _setup_tap_with_vessel(app_client, "reg-kegmon-devtok-token")
    before = app_client.get(f"/vessels/{tap['vessel_id']}", headers=headers).json()
    payload = {
        "token": tap["token"],
        "pour": 0.33, "volume": 19.67, "maxVolume": 20.0,
    }
    r = app_client.post("/ingest/kegmon", json=payload)
    assert r.status_code == 200
    after = app_client.get(f"/vessels/{tap['vessel_id']}", headers=headers).json()
    assert after["volumeRemaining"] < before["volumeRemaining"]


def test_kegmon_beer_endpoint_still_works(app_client):
    """POST /ingest/kegmon/beer still resolves an active tapped vessel's beer info."""
    test_init()
    tap = _setup_tap_with_vessel(app_client, "reg-kegmon-beer-token")
    r = app_client.post("/ingest/kegmon/beer", json={"token": tap["token"]})
    assert r.status_code == 200


def test_dispatch_endpoint_still_works(app_client):
    """POST /ingest/dispatch still auto-detects and accepts a valid payload."""
    test_init()
    device = _create_device(app_client, "REGDS1", "gravitymon")
    payload = {"name": "GravityMon", "id": "REGDS1", "token": device["token"],
               "gravity": 1.050, "gravity-unit": "G", "temperature": 20.0,
               "temp_units": "C", "angle": 30.0, "battery": 4.1, "rssi": -60}
    r = app_client.post("/ingest/dispatch", json=payload)
    assert r.status_code == 200
