# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for ingestion unit conversions and error paths."""
import json

import pytest

from core.config import get_settings
from core.db import create_session
from core.models.platform import IngestionLog
from core.models.registry import resolve_model
from tests.conftest import DEVICE_DEFAULTS, truncate_database

Device = resolve_model("Device")

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

DEVICE_BASE = {
    "name": "Conv Device",
    "deviceType": "gravitymon",
    "chipId": "CONV01",
    **DEVICE_DEFAULTS,
}

GRAVITY_BASE = {
    "name": "Conv Test",
    "id": "CONV01",
    "interval": 10,
    "temperature": 68.0,
    "temp_units": "F",
    "gravity": 1.050,
    "angle": 34.0,
    "battery": 3.85,
    "rssi": -76,
    "gravity-unit": "G",
}


def _make_device(app_client, overrides=None):
    data = {**DEVICE_BASE, **(overrides or {})}
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


def test_init():
    """Reset database state before suite."""
    truncate_database()


def test_temperature_fahrenheit_converted_to_celsius(app_client):
    """Fahrenheit temperature is stored as Celsius."""
    test_init()
    device = _make_device(app_client, {"chipId": "FAHR01", "name": "FahrDev"})
    payload = {**GRAVITY_BASE, "id": "FAHR01", "token": device["token"],
               "temperature": 68.0, "temp_units": "F"}
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    assert abs(readings[0]["temperature"] - 20.0) < 0.05


def test_temperature_below_absolute_zero_stored_as_received(app_client):
    """A temperature is stored exactly as received, whatever its size."""
    test_init()
    device = _make_device(app_client, {"chipId": "SENT01", "name": "SentDev"})
    payload = {**GRAVITY_BASE, "id": "SENT01", "token": device["token"],
               "temperature": -300.0, "temp_units": "C"}
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    assert readings[0]["temperature"] == -300.0


def test_gravity_plato_converted_to_sg(app_client):
    """Gravity in Plato is converted and stored as SG."""
    test_init()
    device = _make_device(app_client, {"chipId": "PLAT01", "name": "PlatoDev"})
    payload = {
        **GRAVITY_BASE, "id": "PLAT01", "token": device["token"],
        "gravity": 12.0, "gravity-unit": "P", "temp_units": "C", "temperature": 20.0,
    }
    r = app_client.post("/ingest/gravitymon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    sg = readings[0]["gravity"]
    assert 1.040 < sg < 1.060


def test_pressure_psi_converted_to_kpa(app_client):
    """PSI pressure is converted and stored in kPa."""
    test_init()
    device = _make_device(app_client, {
        "chipId": "PPSI01", "name": "PSIDev", "deviceType": "pressuremon",
    })
    payload = {
        "name": "PSIDev", "id": "PPSI01", "token": device["token"],
        "interval": 10, "temperature": 20.0, "temp_units": "C",
        "pressure": 14.504, "pressure_units": "psi",
        "battery": 3.5, "rssi": -80, "run-time": 0,
    }
    r = app_client.post("/ingest/pressuremon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/pressure", headers=headers).json()["items"]
    assert readings[0]["pressure"] > 90  # ~99.97 kPa


def test_pressure_bar_converted_to_kpa(app_client):
    """BAR pressure is converted and stored in kPa."""
    test_init()
    device = _make_device(app_client, {
        "chipId": "PBAR01", "name": "BARDev", "deviceType": "pressuremon",
    })
    payload = {
        "name": "BARDev", "id": "PBAR01", "token": device["token"],
        "interval": 10, "temperature": 20.0, "temp_units": "C",
        "pressure": 1.0, "pressure_units": "bar",
        "battery": 3.5, "rssi": -80, "run-time": 0,
    }
    r = app_client.post("/ingest/pressuremon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/pressure", headers=headers).json()["items"]
    assert readings[0]["pressure"] == 100.0


def test_pressure_temperature_fahrenheit_converted(app_client):
    """PressureMon Fahrenheit temperature is stored as Celsius."""
    test_init()
    device = _make_device(app_client, {
        "chipId": "PTMP01", "name": "PTmpDev", "deviceType": "pressuremon",
    })
    payload = {
        "name": "PTmpDev", "id": "PTMP01", "token": device["token"],
        "interval": 10, "temperature": 32.0, "temp_units": "F",
        "pressure": 0.0, "pressure_units": "kPa",
        "battery": 3.5, "rssi": -80,
    }
    r = app_client.post("/ingest/pressuremon", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/pressure", headers=headers).json()["items"]
    assert abs(readings[0]["temperature"] - 0.0) < 0.05


def test_ingest_reuses_existing_fermenting_batch(app_client):
    """Second ingestion reuses the existing fermenting batch, not creating a new one."""
    test_init()
    device = _make_device(app_client, {"chipId": "REUS01", "name": "ReusDev"})
    payload = {**GRAVITY_BASE, "id": "REUS01", "token": device["token"], "temp_units": "C"}
    app_client.post("/ingest/gravitymon", json=payload)
    app_client.post("/ingest/gravitymon", json=payload)

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    assert len(batches) == 1

    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    assert len(readings) == 2


def test_ispindel_rssi_uppercase_field(app_client):
    """iSpindel payloads use the native uppercase ``RSSI`` field."""
    test_init()
    device = _make_device(app_client, {
        "chipId": "ISPI02", "name": "iSpindel2", "deviceType": "ispindel",
    })
    payload = {
        "name": "[SG] iSpindel2", "ID": 13065052, "token": device["token"],
        "interval": 10, "temperature": 20.0, "temp_units": "C",
        "gravity": 1.055, "angle": 30.0, "battery": 4.0, "RSSI": -65,
    }
    r = app_client.post("/ingest/ispindel", json=payload)
    assert r.status_code == 200

    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    readings = app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]
    assert readings[0]["rssi"] == -65.0


def _ispindel_reading(app_client, chip_id, drop=(), **overrides):
    """POST an iSpindel payload for a fresh device; return (response, stored gravity readings)."""
    test_init()
    device = _make_device(app_client, {
        "chipId": chip_id, "name": f"iSp{chip_id}", "deviceType": "ispindel",
    })
    payload = {
        "name": "[SG] iSpindel", "ID": 13065052, "token": device["token"],
        "interval": 10, "temperature": 68.0,
        "gravity": 1.055, "angle": 30.0, "battery": 4.0, "RSSI": -65,
        **overrides,
    }
    for key in drop:
        payload.pop(key)
    r = app_client.post("/ingest/ispindel", json=payload)
    if r.status_code != 200:
        return r, []
    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    return r, app_client.get(f"/batches/{batch_id}/gravity", headers=headers).json()["items"]


def test_ispindel_hyphenated_temp_unit_alias_is_ignored(app_client):
    """``temp-unit`` is not a wire spelling: it is ignored and the reading stays Celsius."""
    r, readings = _ispindel_reading(app_client, "ISPI03", **{"temp-unit": "F"})
    assert r.status_code == 200
    assert readings[0]["temperature"] == 68.0


def test_ispindel_without_gravity_stores_other_fields(app_client):
    """A payload without gravity is accepted; the rest is stored and the gravity is null."""
    r, readings = _ispindel_reading(app_client, "ISNG01", drop=("gravity",))
    assert r.status_code == 200
    assert len(readings) == 1
    assert readings[0]["gravity"] is None
    assert readings[0]["angle"] == 30.0
    assert readings[0]["temperature"] == 68.0
    assert readings[0]["battery"] == 4.0
    assert readings[0]["rssi"] == -65.0


def test_ispindel_null_gravity_stores_null(app_client):
    """An explicit null gravity behaves like an absent one."""
    r, readings = _ispindel_reading(app_client, "ISNG02", gravity=None)
    assert r.status_code == 200
    assert readings[0]["gravity"] is None


def _typed_reading(app_client, device_type, chip_id, path, drop=(), **overrides):
    """POST a gravity-less payload for a fresh ``device_type`` device; return (r, readings)."""
    test_init()
    device = _make_device(app_client, {
        "chipId": chip_id, "name": f"dev{chip_id}", "deviceType": device_type,
    })
    payload = {
        "name": "GM", "ID": chip_id, "token": device["token"], "interval": 10,
        "temperature": 20.0, "temp_units": "C", "velocity": 0.5, "gravity": None,
        "gravity-unit": "G", "corr-gravity": 1.05, "angle": 30.0, "battery": 4.0, "RSSI": -65,
        **overrides,
    }
    for key in drop:
        payload.pop(key)
    r = app_client.post(path, json=payload)
    if r.status_code != 200:
        return r, []
    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    url = f"/batches/{batches[0]['id']}/gravity"
    return r, app_client.get(url, headers=headers).json()["items"]


@pytest.mark.parametrize("path", ["/ingest/ispindel", "/ingest/gravitymon", "/ingest/dispatch"])
@pytest.mark.parametrize("absent", [True, False])
def test_gravitymon_without_gravity_stores_other_fields(app_client, path, absent):
    """A GravityMon device may omit gravity (absent or null) on every gravity endpoint."""
    r, readings = _typed_reading(
        app_client, "gravitymon", f"GM{path[-4:]}{int(absent)}", path,
        drop=("gravity",) if absent else (),
    )
    assert r.status_code == 200, r.text
    assert readings[0]["gravity"] is None
    assert readings[0]["angle"] == 30.0
    assert readings[0]["temperature"] == 20.0
    assert readings[0]["battery"] == 4.0


def test_other_device_type_without_gravity_still_rejected(app_client):
    """Only iSpindel and GravityMon devices may omit gravity."""
    r, _ = _typed_reading(app_client, "pressuremon", "RPNG01", "/ingest/ispindel")
    assert r.status_code == 422


def test_gravitymon_empty_payload_rejected(app_client):
    """A GravityMon payload with no measurement at all is refused."""
    test_init()
    device = _make_device(app_client, {
        "chipId": "GMEMP1", "name": "gmEmpty", "deviceType": "gravitymon",
    })
    r = app_client.post("/ingest/gravitymon", json={
        "token": device["token"], "gravity-unit": "G", "gravity": None,
    })
    assert r.status_code == 422


def _null_gravity_reading(app_client, chip_id):
    """Ingest a gravity-less iSpindel reading; return (batch id, reading id)."""
    _, readings = _ispindel_reading(app_client, chip_id, drop=("gravity",))
    batch_id = app_client.get("/batches/", headers=headers).json()["items"][0]["id"]
    return batch_id, readings[0]["id"]


def test_null_gravity_reading_exclude_toggle(app_client):
    """Excluding and re-including a null-gravity reading works and keeps the gravity null."""
    batch_id, reading_id = _null_gravity_reading(app_client, "ISNG04")
    url = f"/batches/{batch_id}/gravity/{reading_id}"
    r = app_client.patch(url, json={"excluded": True}, headers=headers)
    assert r.status_code == 200
    assert r.json()["excluded"] is True
    assert r.json()["gravity"] is None
    r = app_client.patch(url, json={"excluded": False, "gravity": None}, headers=headers)
    assert r.status_code == 200
    assert r.json()["excluded"] is False
    assert r.json()["gravity"] is None


def test_patch_omitting_gravity_keeps_it_and_null_is_rejected(app_client):
    """A PATCH without gravity leaves it unchanged; clearing an existing gravity is a 422."""
    _, readings = _ispindel_reading(app_client, "ISNG05")
    batch_id = app_client.get("/batches/", headers=headers).json()["items"][0]["id"]
    url = f"/batches/{batch_id}/gravity/{readings[0]['id']}"
    r = app_client.patch(url, json={"excluded": True}, headers=headers)
    assert r.status_code == 200
    assert r.json()["gravity"] == readings[0]["gravity"]
    r = app_client.patch(url, json={"gravity": None}, headers=headers)
    assert r.status_code == 422


def test_ispindel_without_any_measurement_rejected(app_client):
    """A payload with no storable value at all is still a 422."""
    r, _ = _ispindel_reading(
        app_client, "ISNG03",
        drop=("gravity", "angle", "temperature", "battery", "RSSI"),
    )
    assert r.status_code == 422


def test_dispatch_does_not_route_gravityless_payload_to_ispindel(app_client):
    """Detection is unchanged: without a gravity key the dispatch endpoint finds no device."""
    r = app_client.post("/ingest/dispatch", json={"angle": 30.0, "battery": 4.0, "ID": 1})
    assert r.status_code == 422


def test_ispindel_unknown_temp_units_value_rejected(app_client):
    """``temp_units`` is exactly ``C`` or ``F``; any other value is a 422."""
    r, _ = _ispindel_reading(app_client, "ISPI04", temp_units="K")
    assert r.status_code == 422


def _pressure_reading(app_client, chip_id, unit_key, unit, pressure):
    """POST a PressureMon payload for a fresh device; return (response, stored readings)."""
    test_init()
    device = _make_device(app_client, {
        "chipId": chip_id, "name": f"P{chip_id}", "deviceType": "pressuremon",
    })
    payload = {
        "name": "PressureMon", "id": chip_id, "token": device["token"],
        "interval": 10, "temperature": 20.0, "temp_units": "C",
        "pressure": pressure, unit_key: unit,
        "battery": 3.5, "rssi": -80,
    }
    r = app_client.post("/ingest/pressuremon", json=payload)
    if r.status_code != 200:
        return r, []
    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    batch_id = batches[0]["id"]
    return r, app_client.get(f"/batches/{batch_id}/pressure", headers=headers).json()["items"]


@pytest.mark.parametrize("unit_key", ["pressure_units", "pressure-unit", "pressure_unit"])
@pytest.mark.parametrize("unit, pressure, expected_kpa", [
    ("kPa", 100.0, 100.0), ("KPA", 100.0, 100.0), ("kpa", 100.0, 100.0),
    ("Bar", 1.0, 100.0), ("BAR", 1.0, 100.0), ("bAr", 1.0, 100.0),
    ("PSI", 14.5, 99.97402), ("Psi", 10.0, 68.9476), ("psi", 10.0, 68.9476),
])
def test_pressuremon_unit_any_case_stored_in_kpa(
    app_client, unit_key, unit, pressure, expected_kpa
):
    """Firmware unit spellings in any letter case are accepted and stored in kPa."""
    r, readings = _pressure_reading(app_client, "PCASE1", unit_key, unit, pressure)
    assert r.status_code == 200
    assert abs(readings[0]["pressure"] - expected_kpa) < 0.01


@pytest.mark.parametrize("unit_key", ["pressure_units", "pressure-unit", "pressure_unit"])
@pytest.mark.parametrize("unit", ["atm", "", None, 5])
def test_pressuremon_invalid_unit_rejected(app_client, unit_key, unit):
    """Anything that is not kPa, bar or psi (any case) is a 422."""
    r, _ = _pressure_reading(app_client, "PBAD01", unit_key, unit, 1.0)
    assert r.status_code == 422


@pytest.mark.parametrize("unit, pressure, expected_kpa", [
    ("kPa", -5.0, -5.0), ("bar", -0.5, -50.0), ("psi", -2.0, -13.78952),
])
def test_pressuremon_negative_pressure_keeps_sign(app_client, unit, pressure, expected_kpa):
    """A negative reading (uncalibrated sensor or vacuum) is stored in kPa with its sign."""
    r, readings = _pressure_reading(app_client, "PNEG01", "pressure_units", unit, pressure)
    assert r.status_code == 200
    assert abs(readings[0]["pressure"] - expected_kpa) < 0.01


@pytest.mark.parametrize("unit, pressure, expected_kpa", [
    ("kPa", 3000.01, 3000.01), ("kPa", -5000.0, -5000.0), ("kPa", 250000.0, 250000.0),
    ("bar", 4000.0, 400000.0), ("psi", -4000.0, -27579.04),
])
def test_pressuremon_pressure_has_no_range(app_client, unit, pressure, expected_kpa):
    """A pressure is stored as received, converted to kPa, however large or small."""
    r, readings = _pressure_reading(app_client, "PBND01", "pressure_units", unit, pressure)
    assert r.status_code == 200
    assert abs(readings[0]["pressure"] - expected_kpa) < 0.01


# ---------------------------------------------------------------------------
# Store what is received: no ranges, no clamps, null for what was not sent
# ---------------------------------------------------------------------------

def _post_json(app_client, path, payload):
    """POST a payload as raw JSON text so NaN and Infinity reach the server as sent."""
    return app_client.post(path, content=json.dumps(payload),
                           headers={"Content-Type": "application/json"})


def _stored(app_client, device, kind):
    """The readings stored for the batch the device was attached to."""
    batches = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"]
    return app_client.get(f"/batches/{batches[0]['id']}/{kind}", headers=headers).json()["items"]


def _gravitymon_post(app_client, chip_id, drop=(), **overrides):
    """POST a GravityMon payload for a fresh device; return (response, stored readings)."""
    test_init()
    device = _make_device(app_client, {"chipId": chip_id, "name": f"GM{chip_id}"})
    payload = {**GRAVITY_BASE, "id": chip_id, "token": device["token"], "temp_units": "C",
               "temperature": 20.0, **overrides}
    for key in drop:
        payload.pop(key, None)
    r = _post_json(app_client, "/ingest/gravitymon", payload)
    return r, (_stored(app_client, device, "gravity") if r.status_code == 200 else [])


def _pressuremon_post(app_client, chip_id, drop=(), **overrides):
    """POST a PressureMon payload for a fresh device; return (response, stored readings)."""
    test_init()
    device = _make_device(app_client, {
        "chipId": chip_id, "name": f"PM{chip_id}", "deviceType": "pressuremon",
    })
    payload = {
        "name": "PressureMon", "id": chip_id, "token": device["token"],
        "temperature": 20.0, "temp_units": "C", "pressure": 100.0, "pressure_units": "kPa",
        "battery": 3.5, "rssi": -80, "run-time": 12.0, **overrides,
    }
    for key in drop:
        payload.pop(key)
    r = _post_json(app_client, "/ingest/pressuremon", payload)
    return r, (_stored(app_client, device, "pressure") if r.status_code == 200 else [])


@pytest.mark.parametrize("sent, field, value", [
    ({"gravity": 0.3}, "gravity", 0.3),
    ({"gravity": 5000.0}, "gravity", 5000.0),
    ({"gravity": 0.0}, "gravity", 0.0),
    ({"angle": -10.0}, "angle", -10.0),
    ({"angle": 400.0}, "angle", 400.0),
    ({"battery": 11.0}, "battery", 11.0),
    ({"battery": -1.0}, "battery", -1.0),
    ({"rssi": 5}, "rssi", 5.0),
    ({"rssi": -300}, "rssi", -300.0),
    ({"velocity": 500.0}, "velocity", 500.0),
    ({"run-time": 5000000.0}, "runTime", 5000000.0),
    ({"temperature": 250.0}, "temperature", 250.0),
    ({"temperature": -300.0}, "temperature", -300.0),
])
def test_gravitymon_values_stored_as_received(app_client, sent, field, value):
    """No range applies to a gravity reading: an odd value is stored, not clamped."""
    r, readings = _gravitymon_post(app_client, "GRCV01", **sent)
    assert r.status_code == 200
    assert readings[0][field] == value


def test_gravitymon_fahrenheit_is_converted_without_a_range(app_client):
    """A Fahrenheit value above the old 200 limit converts to 100 C."""
    r, readings = _gravitymon_post(app_client, "GRCV02", temperature=212.0, temp_units="F")
    assert r.status_code == 200
    assert readings[0]["temperature"] == 100.0


def test_gravitymon_plato_has_no_range(app_client):
    """A Plato value is converted to SG as received; zero Plato is 1.000."""
    r, readings = _gravitymon_post(app_client, "GRCV03", gravity=0.0, **{"gravity-unit": "P"})
    assert r.status_code == 200
    assert readings[0]["gravity"] == 1.0


@pytest.mark.parametrize(
    "field", ["angle", "battery", "rssi", "run-time", "velocity", "temperature"]
)
def test_gravitymon_absent_optional_fields_stored_null(app_client, field):
    """An optional measurement that was not sent is null, never zero."""
    r, readings = _gravitymon_post(app_client, "GRNL01", drop=(field,))
    assert r.status_code == 200
    assert readings[0]["runTime" if field == "run-time" else field] is None


def test_gravitymon_explicit_null_fields_stored_null(app_client):
    """A field sent as null is stored as null."""
    r, readings = _gravitymon_post(app_client, "GRNL02", angle=None, battery=None, rssi=None)
    assert r.status_code == 200
    assert readings[0]["angle"] is None
    assert readings[0]["battery"] is None
    assert readings[0]["rssi"] is None


@pytest.mark.parametrize(
    "field", ["gravity", "angle", "battery", "rssi", "velocity", "temperature"]
)
@pytest.mark.parametrize("bad", ["abc", "nan", "inf", float("nan"), float("inf"), float("-inf")])
def test_gravitymon_invalid_optional_number_dropped(app_client, field, bad):
    """Text, NaN and infinity are dropped from optional fields."""
    r, readings = _gravitymon_post(app_client, "GRBD01", **{field: bad})
    assert r.status_code == 200
    assert readings[0][field] is None


@pytest.mark.parametrize("unit", ["g", "G", "p", "P"])
def test_gravitymon_gravity_unit_ignores_case(app_client, unit):
    """The gravity unit is accepted in either letter case."""
    r, _ = _gravitymon_post(app_client, "GRUN01", **{"gravity-unit": unit})
    assert r.status_code == 200


@pytest.mark.parametrize("unit", ["SG", "x", "", None, 1])
def test_gravitymon_gravity_unit_must_be_allowed(app_client, unit):
    """Any other unit cannot be interpreted: 422."""
    r, _ = _gravitymon_post(app_client, "GRUN02", **{"gravity-unit": unit})
    assert r.status_code == 422


def test_gravitymon_missing_gravity_unit_rejected(app_client):
    """GravityMon always names its unit."""
    r, _ = _gravitymon_post(app_client, "GRUN03", drop=("gravity-unit",))
    assert r.status_code == 422


def test_gravitymon_lowercase_temp_unit_converted(app_client):
    """temp_units is case-insensitive."""
    r, readings = _gravitymon_post(app_client, "GRUN04", temperature=68.0, temp_units="f")
    assert r.status_code == 200
    assert abs(readings[0]["temperature"] - 20.0) < 0.05


def test_gravitymon_numeric_strings_are_dropped(app_client):
    """A numeric string is not a JSON number."""
    r, readings = _gravitymon_post(app_client, "GRST01", gravity="1.05", battery="3.9")
    assert r.status_code == 200
    assert readings[0]["gravity"] is None
    assert readings[0]["battery"] is None


def test_gravitymon_fractional_rssi_accepted(app_client):
    """RSSI is a number, not an integer."""
    r, readings = _gravitymon_post(app_client, "GRST02", rssi=-58.5)
    assert r.status_code == 200
    assert readings[0]["rssi"] in (-58.0, -59.0)


@pytest.mark.parametrize("ignored", [
    {"interval": "soon"}, {"interval": -5}, {"interval": 300.5}, {"corr-gravity": "x"},
    {"color": {"a": 1}}, {"name": 5}, {"name": None}, {"id": [1, 2]}, {"ID": 12},
])
def test_gravitymon_ignored_fields_never_rejected(app_client, ignored):
    """Fields that are accepted but not stored are ignored whatever they contain."""
    r, _ = _gravitymon_post(app_client, "GRIG01", **ignored)
    assert r.status_code == 200


@pytest.mark.parametrize("ignored", [
    {"color": "chartreuse"}, {"color": 7}, {"interval": "x"}, {"ID": "not-a-number"},
    {"name": None},
])
def test_ispindel_ignored_fields_never_rejected(app_client, ignored):
    """iSpindel ignored fields are never a 422."""
    r, _ = _ispindel_reading(app_client, "ISIG01", **ignored)
    assert r.status_code == 200


@pytest.mark.parametrize("sent, field, value", [
    ({"gravity": 0.3}, "gravity", 0.3), ({"gravity": 5000.0}, "gravity", 5000.0),
    ({"battery": 11.0}, "battery", 11.0), ({"RSSI": 5}, "rssi", 5.0),
    ({"angle": -45.0}, "angle", -45.0),
])
def test_ispindel_values_stored_as_received(app_client, sent, field, value):
    """No range applies to an iSpindel reading either."""
    r, readings = _ispindel_reading(app_client, "ISRV01", **{"name": "[SG] iSpindel", **sent})
    assert r.status_code == 200
    assert readings[0][field] == value


def test_ispindel_absent_optional_fields_stored_null(app_client):
    """iSpindel without angle, battery and RSSI stores null for each."""
    test_init()
    device = _make_device(app_client, {
        "chipId": "ISNL01", "name": "iSpNull", "deviceType": "ispindel",
    })
    payload = {"name": "[SG] iSpindel", "ID": 1, "token": device["token"], "gravity": 1.05}
    assert _post_json(app_client, "/ingest/ispindel", payload).status_code == 200
    reading = _stored(app_client, device, "gravity")[0]
    assert reading["angle"] is None
    assert reading["battery"] is None
    assert reading["rssi"] is None
    assert reading["temperature"] is None


@pytest.mark.parametrize("sent, field, value", [
    ({"battery": 11.0}, "battery", 11.0), ({"rssi": 5}, "rssi", 5.0),
    ({"temperature": 250.0}, "temperature", 250.0), ({"run-time": -3.0}, "runTime", -3.0),
    ({"pressure": 9999999.0}, "pressure", 9999999.0),
])
def test_pressuremon_values_stored_as_received(app_client, sent, field, value):
    """No range applies to a pressure reading."""
    r, readings = _pressuremon_post(app_client, "PRRV01", **sent)
    assert r.status_code == 200
    assert readings[0][field] == value


def test_pressuremon_absent_unit_means_kpa(app_client):
    """No pressure unit is kPa."""
    r, readings = _pressuremon_post(app_client, "PRUN01", drop=("pressure_units",), pressure=77.0)
    assert r.status_code == 200
    assert readings[0]["pressure"] == 77.0


def test_pressuremon_absent_temp_unit_means_celsius(app_client):
    """No temperature unit is Celsius."""
    r, readings = _pressuremon_post(app_client, "PRUN02", drop=("temp_units",), temperature=21.5)
    assert r.status_code == 200
    assert readings[0]["temperature"] == 21.5


def test_pressuremon_lowercase_temp_unit_converted(app_client):
    """temp_units is case-insensitive."""
    r, readings = _pressuremon_post(app_client, "PRUN03", temperature=68.0, temp_units="f")
    assert r.status_code == 200
    assert abs(readings[0]["temperature"] - 20.0) < 0.05


@pytest.mark.parametrize("field", ["battery", "rssi", "run-time", "temperature"])
def test_pressuremon_absent_optional_fields_stored_null(app_client, field):
    """An optional measurement that was not sent is null, never zero."""
    r, readings = _pressuremon_post(app_client, "PRNL01", drop=(field,))
    assert r.status_code == 200
    assert readings[0]["runTime" if field == "run-time" else field] is None


@pytest.mark.parametrize("field", ["pressure", "battery", "rssi", "temperature"])
@pytest.mark.parametrize("bad", ["abc", "nan", "inf", float("nan"), float("inf")])
def test_pressuremon_invalid_optional_number_dropped(app_client, field, bad):
    """Text, NaN and infinity are dropped from optional fields."""
    r, readings = _pressuremon_post(app_client, "PRBD01", **{field: bad})
    assert r.status_code == 200
    assert readings[0][field] is None


def _pressure_gap_post(app_client, device_type, chip_id, path, drop=(), **overrides):
    """POST a pressure-less payload for a fresh ``device_type`` device.

    Returns (response, device, readings); the readings are empty unless it was accepted.
    """
    test_init()
    device = _make_device(app_client, {
        "chipId": chip_id, "name": f"PG{chip_id}", "deviceType": device_type,
    })
    payload = {
        "name": "PressureMon", "id": chip_id, "token": device["token"], "pressure": None,
        "pressure2": 55.0, "temperature": 20.0, "temp_units": "C", "pressure-unit": "bar",
        "battery": 3.5, "rssi": -80, "run-time": 12.0, **overrides,
    }
    for key in drop:
        payload.pop(key)
    r = _post_json(app_client, path, payload)
    return r, device, (_stored(app_client, device, "pressure") if r.status_code == 200 else [])


@pytest.mark.parametrize("path", ["/ingest/pressuremon", "/ingest/dispatch"])
@pytest.mark.parametrize("absent", [True, False])
def test_pressuremon_without_pressure_stores_other_fields(app_client, path, absent):
    """A PressureMon payload may omit pressure (absent or null); the rest is stored."""
    r, device, readings = _pressure_gap_post(
        app_client, "pressuremon", f"PG{path[-4:]}{int(absent)}", path,
        drop=("pressure",) if absent else (),
    )
    assert r.status_code == 200, r.text
    assert readings[0]["pressure"] is None
    assert readings[0]["temperature"] == 20.0
    assert readings[0]["battery"] == 3.5
    assert readings[0]["rssi"] == -80
    assert readings[0]["runTime"] == 12.0
    batch = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"][0]
    reading = app_client.get(f"/batches/{batch['id']}/pressure", headers=headers).json()["items"][0]
    assert reading["pressure"] is None


def test_pressuremon_null_pressure_is_null_safe_in_series(app_client):
    """Chart, highest and lowest skip a reading without pressure instead of failing."""
    r, device, _ = _pressure_gap_post(app_client, "pressuremon", "PGSER1", "/ingest/pressuremon")
    assert r.status_code == 200
    batch = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"][0]
    chart = app_client.get(f"/batches/{batch['id']}/pressure/chart", headers=headers)
    assert chart.status_code == 200
    assert chart.json() == []
    assert app_client.get(f"/batches/{batch['id']}", headers=headers).status_code == 200
    assert app_client.get("/dashboard", headers=headers).status_code == 200


def test_pressuremon_null_pressure_reading_can_be_excluded(app_client):
    """A reading without pressure can be updated by omitting the pressure; it stays null."""
    r, device, readings = _pressure_gap_post(
        app_client, "pressuremon", "PGEXC1", "/ingest/pressuremon")
    assert r.status_code == 200
    batch = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"][0]
    patched = app_client.patch(
        f"/batches/{batch['id']}/pressure/{readings[0]['id']}",
        json={"excluded": True}, headers=headers)
    assert patched.status_code == 200, patched.text
    assert patched.json()["pressure"] is None
    assert patched.json()["excluded"] is True


def test_pressure_reading_with_value_cannot_be_cleared(app_client):
    """A stored pressure is never cleared by an update."""
    r, device, readings = _pressure_gap_post(
        app_client, "pressuremon", "PGCLR1", "/ingest/pressuremon", pressure=100.0)
    assert r.status_code == 200
    batch = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"][0]
    patched = app_client.patch(
        f"/batches/{batch['id']}/pressure/{readings[0]['id']}",
        json={"pressure": None}, headers=headers)
    assert patched.status_code == 422


def test_manual_pressure_reading_still_requires_pressure(app_client):
    """Manual entry has no gap: the create schema keeps pressure required."""
    r, device, _ = _pressure_gap_post(app_client, "pressuremon", "PGMAN1", "/ingest/pressuremon")
    assert r.status_code == 200
    batch = app_client.get(f"/batches/?deviceId={device['id']}", headers=headers).json()["items"][0]
    created = app_client.post(
        f"/batches/{batch['id']}/pressure", json={"temperature": 20.0}, headers=headers)
    assert created.status_code == 422


def test_other_device_type_without_pressure_still_rejected(app_client):
    """Only a PressureMon device may omit pressure."""
    r, _, _ = _pressure_gap_post(app_client, "ispindel", "PGOTH1", "/ingest/pressuremon")
    assert r.status_code == 422


def test_pressuremon_empty_payload_rejected(app_client):
    """A PressureMon payload with no measurement at all is refused."""
    test_init()
    device = _make_device(app_client, {
        "chipId": "PGEMP1", "name": "pgEmpty", "deviceType": "pressuremon",
    })
    r = app_client.post("/ingest/pressuremon", json={
        "token": device["token"], "pressure": None, "pressure-unit": "kPa",
    })
    assert r.status_code == 422


@pytest.mark.parametrize("unit", ["K", "", None, 1])
def test_pressuremon_invalid_temp_unit_rejected(app_client, unit):
    """A temperature unit other than C or F is a 422."""
    r, _ = _pressuremon_post(app_client, "PRBD03", temp_units=unit)
    assert r.status_code == 422


def test_pressuremon_converted_overflow_is_a_422_not_a_500(app_client):
    """A bar value so large that the kPa conversion overflows cannot be stored: 422."""
    r, _ = _pressuremon_post(app_client, "PRBD04", pressure=1e307, pressure_units="bar")
    assert r.status_code == 422


@pytest.mark.parametrize("ignored", [{"interval": "x"}, {"id": {"a": 1}}, {"name": 5}])
def test_pressuremon_ignored_fields_never_rejected(app_client, ignored):
    """Ignored PressureMon fields are never a 422."""
    r, _ = _pressuremon_post(app_client, "PRIG01", **ignored)
    assert r.status_code == 200


def test_unstorable_value_is_logged_as_parse_error_and_keeps_last_seen(app_client):
    """A value that cannot be stored is a logged parse_error; the device is still seen."""
    r, _ = _pressuremon_post(app_client, "PRLG01", pressure=1e307, pressure_units="bar")
    assert r.status_code == 422
    session = create_session()
    try:
        rows = session.query(IngestionLog).filter(IngestionLog.reason == "parse_error").all()
        assert len(rows) == 1
        assert rows[0].error_detail.startswith("pressure:")
        device = session.query(Device).filter(Device.chip_id == "PRLG01").one()
        assert device.last_seen is not None
    finally:
        session.close()
