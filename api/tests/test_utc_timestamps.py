# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Every instant the API emits carries an explicit UTC marker.

SQLite and the Oracle driver return naive datetimes for timezone-aware columns; the
`UtcDateTime` column type re-attaches UTC so the JSON says `...Z`/`+00:00` and browsers
do not read the value as local time.
"""
import re
from datetime import UTC, datetime, timedelta, timezone

from core.config import get_settings
from core.models.types import UtcDateTime
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

# A timestamp (date, 'T', time) -- the pattern a datetime serialises to.
_ISO_DATETIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d(\.\d+)?)?")
_ZONED = re.compile(r"(Z|[+-]\d\d:\d\d)$")


def _walk(value, path=""):
    """Yield (path, string) for every string leaf in a JSON document."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def _datetimes(body):
    return [(p, s) for p, s in _walk(body) if _ISO_DATETIME.match(s)]


def _seed(app_client) -> dict:
    """Create one of everything that carries a timestamp and return the ids."""
    truncate_database()

    def post(path, payload, status=201):
        r = app_client.post(path, json=payload, headers=headers)
        assert r.status_code == status, (path, r.text)
        for where, text in _datetimes(r.json()):
            assert _ZONED.search(text), f"POST {path}{where} = {text!r} has no UTC marker"
        return r.json()

    batch = post(
        "/batches", {"name": "UTC Batch", "status": "fermenting", "brewDate": "2026-01-01"}
    )
    batch_id = batch["id"]
    device = post("/devices", {
        "name": "UTC Device", "chipId": "BBBBBB", "deviceType": "gravitymon",
        "mdns": "gravitymon-bbbbbb", "chipFamily": "ESP32",
    })
    gravity = [{"batchId": batch_id, "temperature": 20.0, "gravity": 1.05, "velocity": 0.1,
                "angle": 45.0, "battery": 3.8, "rssi": -75.0, "runTime": 0.8}]
    post(f"/batches/{batch_id}/gravity/bulk", gravity)
    post(f"/batches/{batch_id}/temp/bulk", [{"batchId": batch_id, "temperature": 18.0}])
    post(f"/batches/{batch_id}/pressure/bulk", [{"batchId": batch_id, "pressure": 1.2}])
    post(f"/batches/{batch_id}/fermentation-steps", [
        {"batchId": batch_id, "order": 1, "type": "primary", "temp": 20.0, "days": 7},
    ])
    post(f"/batches/{batch_id}/notes", {"content": "A note"})
    post(f"/batches/{batch_id}/dry-hops", [{"name": "Citra", "amount": 10.0}])
    tap = post("/taps", {"name": "UTC Tap", "tapNumber": 1})
    vessel = post("/vessels", {
        "batchId": batch_id, "vesselNumber": 1, "vesselType": "keg", "name": "Keg",
        "fillDate": "2026-05-01", "totalVolume": 19.0, "volumeRemaining": 19.0,
        "status": "serving", "tapId": tap["id"],
    })
    vessel_id = vessel["id"]
    post(f"/vessels/{vessel_id}/pours", {"pourAmount": 0.5})
    post(f"/vessels/{vessel_id}/temp/bulk", [{"vesselId": vessel_id, "temperature": 4.0}])
    post(f"/vessels/{vessel_id}/pressure/bulk", [{"vesselId": vessel_id, "pressure": 1.5}])
    return {"batch": batch_id, "device": device["id"], "tap": tap["id"], "vessel": vessel_id}


def test_every_get_response_datetime_has_a_utc_marker(app_client):
    """No ISO datetime in any GET (or create) response is missing its zone."""
    ids = _seed(app_client)
    paths = [
        "/batches", f"/batches/{ids['batch']}",
        f"/batches/{ids['batch']}/gravity", f"/batches/{ids['batch']}/gravity/chart",
        f"/batches/{ids['batch']}/temp", f"/batches/{ids['batch']}/temp/chart",
        f"/batches/{ids['batch']}/pressure", f"/batches/{ids['batch']}/pressure/chart",
        f"/batches/{ids['batch']}/fermentation-steps", f"/batches/{ids['batch']}/notes",
        f"/batches/{ids['batch']}/vessels",
        "/devices", f"/devices/{ids['device']}", "/taps", f"/taps/{ids['tap']}",
        "/vessels", f"/vessels/{ids['vessel']}", f"/vessels/{ids['vessel']}/pours",
        f"/vessels/{ids['vessel']}/temp", f"/vessels/{ids['vessel']}/pressure",
        "/dashboard", "/predictions", "/integrations", "/system/info",
    ]
    checked = 0
    for path in paths:
        r = app_client.get(path, headers=headers)
        assert r.status_code == 200, (path, r.status_code, r.text)
        for where, text in _datetimes(r.json()):
            checked += 1
            assert _ZONED.search(text), f"{path}{where} = {text!r} has no UTC marker"
    # Guard against the walk silently matching nothing (e.g. a renamed route family).
    assert checked >= 20, f"only {checked} datetimes inspected"


def test_naive_client_input_is_echoed_as_utc(app_client):
    """A note created with a naive timestamp reads back with an explicit marker."""
    ids = _seed(app_client)
    created = (datetime.now(UTC) - timedelta(hours=1)).replace(tzinfo=None).isoformat()
    r = app_client.post(f"/batches/{ids['batch']}/notes",
                        json={"content": "naive", "createdAt": created}, headers=headers)
    assert r.status_code == 201, r.text
    listed = app_client.get(f"/batches/{ids['batch']}/notes", headers=headers).json()["items"]
    assert all(_ZONED.search(n["createdAt"]) for n in listed)


def test_utc_datetime_type_normalises_values():
    """Naive -> UTC, aware -> UTC, None passes through (both directions)."""
    column = UtcDateTime()
    plus_two = timezone(timedelta(hours=2))

    naive = datetime(2026, 10, 3, 10, 0, 0)
    assert column.process_result_value(naive, None) == naive.replace(tzinfo=UTC)
    assert column.process_result_value(naive, None).utcoffset() == timedelta(0)

    aware = datetime(2026, 10, 3, 12, 0, 0, tzinfo=plus_two)
    out = column.process_result_value(aware, None)
    assert out == aware and out.utcoffset() == timedelta(0) and out.hour == 10

    assert column.process_result_value(None, None) is None

    bound = column.process_bind_param(aware, None)
    assert bound.utcoffset() == timedelta(0) and bound.hour == 10
    assert column.process_bind_param(naive, None) is naive
    assert column.process_bind_param(None, None) is None
