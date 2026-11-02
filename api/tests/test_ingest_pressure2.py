# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""PressureMon's second pressure sensor is stored in kPa and never exposed."""
import pytest
from sqlalchemy import text

from core.config import get_settings
from core.db import create_session, engine
from core.models.platform import IngestionLog
from oss.schemas.ingest import PressureIngestRequest
from tests.conftest import DEVICE_DEFAULTS, truncate_database

HEADERS = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

# A PressureMon whose second sensor is not fitted: pressure2 is sent as null.
OWNER_SAMPLE = {
    "name": "PressureMon", "id": "PRS2OW", "interval": 900,
    "temperature": 21.5, "temperature-unit": "C",
    "pressure": 101.2, "pressure-unit": "kPa", "pressure2": None,
    "battery": 3.9, "rssi": -70, "run-time": 4.2,
}


def _register(client, chip_id: str) -> str:
    device = client.post("/devices", json={
        "name": f"Pressure2 {chip_id}", "chipId": chip_id,
        **DEVICE_DEFAULTS, "deviceType": "pressuremon",
    }, headers=HEADERS).json()
    return device["token"]


def _stored() -> list:
    with engine.connect() as con:
        return list(con.execute(text(
            "SELECT pressure, pressure2, temperature, battery, run_time FROM pressure_reading"
        )))


def _post(client, chip_id: str, route: str = "/ingest/pressuremon", **fields):
    payload = {**OWNER_SAMPLE, "id": chip_id, "token": _register(client, chip_id), **fields}
    return client.post(route, json=payload)


@pytest.mark.parametrize(("unit", "sent", "expected"), [
    ("kPa", 12.5, 12.5),
    ("bar", 1.5, 150.0),
    ("PSI", 10.0, 68.9476),
])
def test_pressure2_is_converted_with_the_pressure_unit(app_client, unit, sent, expected):
    """pressure2 uses the same unit as pressure and is stored as kPa."""
    truncate_database()
    response = _post(app_client, "PRS2U1", **{"pressure-unit": unit, "pressure2": sent})
    assert response.status_code == 200
    assert _stored()[0].pressure2 == pytest.approx(expected, abs=0.01)


def test_pressure2_stored_through_dispatch(app_client):
    """The generic dispatch route stores it too."""
    truncate_database()
    response = _post(app_client, "PRS2D1", "/ingest/dispatch", pressure2=7.0)
    assert response.status_code == 200
    assert _stored()[0].pressure2 == pytest.approx(7.0)


def test_owner_sample_null_pressure2_is_stored_as_null(app_client):
    """The owner's sample (second sensor null) stores the other fields unchanged."""
    truncate_database()
    assert _post(app_client, "PRS2N1").status_code == 200
    row = _stored()[0]
    assert row.pressure2 is None
    assert (row.pressure, row.temperature, row.battery, row.run_time) == (101.2, 21.5, 3.9, 4.2)


def test_absent_pressure2_is_stored_as_null(app_client):
    """A payload without pressure2 is unchanged."""
    truncate_database()
    payload = {k: v for k, v in OWNER_SAMPLE.items() if k != "pressure2"}
    payload.update(id="PRS2A1", token=_register(app_client, "PRS2A1"))
    assert app_client.post("/ingest/pressuremon", json=payload).status_code == 200
    row = _stored()[0]
    assert row.pressure2 is None
    assert row.pressure == 101.2


@pytest.mark.parametrize("value", ["not-a-number", "NaN", "Infinity"])
def test_non_number_pressure2_is_dropped_like_other_optional_fields(app_client, value):
    """An unusable optional value is dropped while the primary pressure is stored."""
    truncate_database()
    assert _post(app_client, "PRS2X1", pressure2=value).status_code == 200
    assert _stored()[0].pressure2 is None
    session = create_session()
    try:
        assert "pressure2" in session.query(IngestionLog).one().error_detail
    finally:
        session.close()


def test_pressure2_is_not_in_the_api_response(app_client):
    """Stored only: the batch pressure listing carries no pressure2."""
    truncate_database()
    token = _register(app_client, "PRS2R1")
    payload = {**OWNER_SAMPLE, "id": "PRS2R1", "token": token, "pressure2": 5.0}
    assert app_client.post("/ingest/pressuremon", json=payload).status_code == 200
    batch = app_client.get("/batches/", headers=HEADERS).json()["items"][0]
    item = app_client.get(f"/batches/{batch['id']}/pressure", headers=HEADERS).json()["items"][0]
    assert "pressure2" not in item


@pytest.mark.parametrize("wire_names", [
    ("pressure_units", "temp_units"),
    ("pressure-unit", "temperature-unit"),
    ("pressure_unit", "temp_unit"),
])
@pytest.mark.parametrize("token_form", ["body", "query", "path", "dispatch"])
@pytest.mark.parametrize(("first_sensor", "expected"), [
    ({"pressure1": 14.5}, 99.97402),
    ({"pressure": 2.0, "pressure1": 14.5}, 13.78952),
    ({"pressure": None, "pressure1": 14.5}, None),
])
def test_pressuremon_aliases_store_canonical_values(
    app_client, wire_names, token_form, first_sensor, expected
):
    """Wire aliases preserve unit conversion, sensor precedence and every token placement."""
    truncate_database()
    token = _register(app_client, "ALIAS01")
    route = "/ingest/pressuremon"
    unit_key, temp_key = wire_names
    payload = {**first_sensor, "pressure2": 29.0, unit_key: "PSI",
               "temperature": 68.0, temp_key: "F"}
    if token_form in ("body", "dispatch"):
        payload["token"] = token
    elif token_form == "query":
        route += f"?token={token}"
    else:
        route += f"/{token}"
    if token_form == "dispatch":
        route = route.replace("pressuremon", "dispatch")
    response = app_client.post(route, json=payload)
    assert response.status_code == 200, response.text
    row = _stored()[0]
    if expected is None:
        assert row.pressure is None
    else:
        assert row.pressure == pytest.approx(expected, abs=0.01)
    assert row.pressure2 == pytest.approx(199.94804, abs=0.01)
    assert row.temperature == pytest.approx(20.0)


@pytest.mark.parametrize("fields", [
    {"pressure_unit": "PSI", "pressure2": 14.5},
    {"pressure1": 99.97},
])
def test_dispatch_recognises_each_pressuremon_alias(app_client, fields):
    """Either alias identifies pressure telemetry without a canonical pressure key."""
    truncate_database()
    token = _register(app_client, "ALIAS02")
    response = app_client.post("/ingest/dispatch", json={"token": token, **fields})
    assert response.status_code == 200, response.text
    row = _stored()[0]
    assert (row.pressure2 if "pressure2" in fields else row.pressure) == pytest.approx(99.97)


def test_pressuremon_openapi_example_is_canonicalised(app_client):
    """The documented wire example validates into canonical service keys."""
    schema = app_client.app.openapi()["components"]["schemas"]["PressureIngestRequest"]
    example = schema["examples"][0]
    payload = PressureIngestRequest.model_validate(example).model_dump(by_alias=True)
    assert payload["pressure"] == 14.5
    assert payload["pressure_units"] == "psi"
    assert payload["temp_units"] == "F"
    assert not {"pressure1", "pressure_unit", "temp_unit"} & payload.keys()
