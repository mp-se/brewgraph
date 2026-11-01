# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Gravity and pressure devices may send their token in the body, the query or the path."""
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy import text
from starlette.exceptions import HTTPException

from core.config import get_settings
from core.db import create_session, engine
from core.models.registry import resolve_model
from main_oss import app
from tests.conftest import DEVICE_DEFAULTS, truncate_database

Device = resolve_model("Device")

HEADERS = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

PAYLOADS = {
    "ispindel": {
        "name": "[SG] Spindel", "gravity": 1.05, "temperature": 20.0,
        "temp_units": "C", "angle": 34.45, "battery": 3.85, "RSSI": -76,
    },
    "gravitymon": {
        "name": "GravityMon", "gravity": 1.05, "gravity-unit": "G", "temperature": 20.0,
        "temperature-unit": "C", "angle": 34.45, "battery": 3.85, "RSSI": -76,
    },
    "pressuremon": {
        "name": "PressureMon", "interval": 900, "temperature": 21.5,
        "temperature-unit": "C", "pressure": 101.2, "pressure-unit": "kPa",
        "battery": 3.9, "rssi": -70, "run-time": 4.2,
    },
}
FORMS = ["body", "query", "path"]
DEVICES = list(PAYLOADS)


def _register(client, device_type: str, chip_id: str) -> dict:
    return client.post("/devices", json={
        "name": f"{device_type} {chip_id}", "chipId": chip_id,
        **DEVICE_DEFAULTS, "deviceType": device_type,
    }, headers=HEADERS).json()


def _send(client, device_type: str, form: str, token: str, body_token: str | None = None):
    payload = dict(PAYLOADS[device_type])
    route = f"/ingest/{device_type}"
    if form == "body":
        payload["token"] = token
    elif form == "query":
        route += f"?token={token}"
    else:
        route += f"/{token}"
    if body_token is not None:
        payload["token"] = body_token
    return client.post(route, json=payload)


def _last_seen(device_id: str):
    session = create_session()
    try:
        return session.get(Device, UUID(device_id)).last_seen
    finally:
        session.close()


def _log_rows() -> list:
    with engine.connect() as con:
        return [" ".join(str(v) for v in row) for row in con.execute(text(
            "SELECT error_detail, payload, reason FROM ingestion_log"
        ))]


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("device_type", DEVICES)
def test_each_form_resolves_the_same_device(app_client, device_type, form):
    """Body, query and path tokens identify the device and stamp last-seen."""
    truncate_database()
    device = _register(app_client, device_type, "TKS001")
    assert _last_seen(device["id"]) is None
    response = _send(app_client, device_type, form, device["token"])
    assert response.status_code == 200
    assert device["token"] not in response.text
    assert _last_seen(device["id"]) is not None


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("device_type", DEVICES)
def test_unknown_token_is_401_and_never_logged(app_client, device_type, form):
    """An unknown token is 401 in every form and does not reach the ingestion log."""
    truncate_database()
    secret = "UNKNOWN-TOKEN-SECRET"
    response = _send(app_client, device_type, form, secret)
    assert response.status_code == 401
    assert secret not in response.text
    rows = _log_rows()
    assert rows
    assert all(secret not in row for row in rows)


@pytest.mark.parametrize("device_type", DEVICES)
def test_body_token_wins_over_query_and_path(app_client, device_type):
    """When the body names a device, a different query or path token is ignored."""
    truncate_database()
    mine = _register(app_client, device_type, "TKS002")
    other = _register(app_client, device_type, "TKS003")
    for form in ("query", "path"):
        response = _send(app_client, device_type, form, other["token"], body_token=mine["token"])
        assert response.status_code == 200
    assert _last_seen(mine["id"]) is not None
    assert _last_seen(other["id"]) is None
    # A bad body token is not rescued by a good URL token.
    rescued = _send(app_client, device_type, "query", mine["token"], body_token="bad")
    assert rescued.status_code == 401


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("device_type", DEVICES)
def test_interval_throttle_is_429_in_every_form(app_client, device_type, form):
    """A request inside the interval is 429, and the token stays out of the log."""
    truncate_database()
    device = _register(app_client, device_type, "TKS004")
    busy = HTTPException(status_code=429, detail="Too many requests — throttle interval active")
    with patch("oss.routers.ingest._check_throttle", side_effect=busy):
        response = _send(app_client, device_type, form, device["token"])
    assert response.status_code == 429
    assert device["token"] not in response.text
    assert _last_seen(device["id"]) is not None
    assert all(device["token"] not in row for row in _log_rows())


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("device_type", DEVICES)
def test_request_rate_ceiling_applies_to_every_form(app_client, device_type, form):
    """The per-device request ceiling keys on the token whichever way it arrives."""
    truncate_database()
    device = _register(app_client, device_type, "TKS005")
    with patch("core.middleware.auth.increment_key", return_value=61):
        response = _send(app_client, device_type, form, device["token"])
    assert response.status_code == 429


def test_path_token_is_not_logged(app_client, caplog):
    """Error logs name the route template, not the token in the path."""
    truncate_database()
    secret = "PATH-TOKEN-SECRET"
    with caplog.at_level("WARNING"):
        assert _send(app_client, "ispindel", "path", secret).status_code == 401
    assert secret not in caplog.text


def test_route_table_has_no_collision():
    """Each ingest method and path is registered once; kegmon/beer and dispatch survive."""
    seen = [
        (method, route.path) for route in app.routes
        if route.path.startswith("/api/ingest")
        for method in getattr(route, "methods", ())
    ]
    assert len(seen) == len(set(seen))
    paths = {path for _, path in seen}
    for device in DEVICES:
        assert {f"/api/ingest/{device}", f"/api/ingest/{device}/{{token}}"} <= paths
    assert {"/api/ingest/kegmon/beer", "/api/ingest/dispatch", "/api/ingest/chamber",
            "/api/ingest/kegmon", "/api/ingest/endpoints"} <= paths


def test_openapi_documents_query_and_path_token():
    """The schema lists the optional query token and the path routes."""
    spec = app.openapi()
    plain = spec["paths"]["/api/ingest/ispindel"]["post"]["parameters"]
    assert any(p["name"] == "token" and p["in"] == "query" and not p["required"] for p in plain)
    with_path = spec["paths"]["/api/ingest/ispindel/{token}"]["post"]["parameters"]
    assert any(p["name"] == "token" and p["in"] == "path" for p in with_path)


def test_kegmon_beer_and_dispatch_still_work(app_client):
    """The neighbouring token-in-body routes are unaffected."""
    truncate_database()
    device = _register(app_client, "pressuremon", "TKS006")
    payload = dict(PAYLOADS["pressuremon"], token=device["token"])
    assert app_client.post("/ingest/dispatch", json=payload).status_code == 200
    assert app_client.post("/ingest/kegmon/beer", json={"token": "nope"}).status_code in (401, 404)
