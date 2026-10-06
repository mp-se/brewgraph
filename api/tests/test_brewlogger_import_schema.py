"""The BrewLogger import schema must accept real exports and reject broken ones.

`api/oss/brewlogger-import.schema.json` describes a format **we do not control**,
which sets the balance differently from the export schema: a false rejection
refuses a user's real data, so unknown keys are permitted and almost nothing is
required. What it must still catch is a wrong type, since that is what actually
breaks a converter — a gravity of `"1.010"` reads fine and computes wrong.

Two BrewLogger behaviours drive the shape and are asserted directly below:
`BackupView.cleanupJson()` deletes every null before writing, while exports taken
by other paths keep theirs — so each optional field has to permit absent *and*
null.
"""
from __future__ import annotations

import copy
import json
import pathlib

import pytest
from jsonschema import Draft202012Validator

SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[1] / "oss/brewlogger-import.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(name="validator", scope="module")
def fixture_validator() -> Draft202012Validator:
    """The schema, checked as a schema before it is used to check anything."""
    Draft202012Validator.check_schema(SCHEMA)
    return Draft202012Validator(SCHEMA)


@pytest.fixture(name="export")
def fixture_export() -> dict:
    """A single-batch export, shaped like the real ones.

    Field values follow a survey of 7 real BrewLogger exports (5344 readings):
    `fermentationSteps` is a JSON-encoded string rather than an array, and
    `chamberTemperature`/`beerTemperature` arrive as explicit nulls.
    """
    return {
        "name": "83. Helles ESP32 ICM",
        "description": "Automatically created",
        "chipIdGravity": "19a54c",
        "chipIdPressure": "",
        "active": False,
        "tapList": True,
        "brewDate": "2026-07-03",
        "style": "German Helles Exportbier",
        "brewer": "Magnus Persson",
        "abv": 5.12,
        "ebc": 4.8,
        "ibu": 10.6,
        "fg": 1.009,
        "og": 1.048029411,
        "predictionHoursLeft": 4.79,
        "predictionAtTimestamp": None,
        "brewfatherId": "YOJ4aJiwKLzaoLLcjAVTGUubVJHzFN",
        "fermentationChamber": 0,
        "fermentationSteps": '[{"order": 0, "temp": 10, "days": 10, "type": "Primary"}]',
        "id": 46,
        "gravity": [{
            "temperature": 10.5, "gravity": 1.0221, "velocity": None, "angle": 45.3,
            "battery": 4.05, "rssi": -62, "corrGravity": 1.0223, "runTime": 3,
            "created": "2026-07-04T10:00:00", "active": True,
            "chamberTemperature": None, "beerTemperature": None,
            "batchId": 46, "id": 9001,
        }],
        "pressure": [],
        "pour": [],
    }


def test_accepts_a_real_shaped_export(validator, export):
    """Without this, every rejection case below could pass for the wrong reason."""
    assert validator.is_valid(export), list(validator.iter_errors(export))


def test_accepts_a_backup_container(validator, export):
    """`BackupView.createBackup()` writes many batches under `meta`/`batches`."""
    backup = {
        "meta": {"version": "0.8", "software": "BrewLogger", "created": "2026-08-19"},
        "batches": [export],
        "devices": [],
        "pressure": [],
        "pour": [],
    }
    assert validator.is_valid(backup), list(validator.iter_errors(backup))


def test_accepts_an_export_with_every_null_stripped(validator, export):
    """`cleanupJson()` deletes null-valued keys, so absent must be as valid as null.

    This is the case a schema written from the class definitions alone would get
    wrong — the classes list the fields, and the writer removes most of them.
    """
    stripped = {k: v for k, v in export.items() if v is not None}
    stripped["gravity"] = [
        {k: v for k, v in r.items() if v is not None} for r in stripped["gravity"]
    ]
    assert validator.is_valid(stripped), list(validator.iter_errors(stripped))


def test_accepts_unknown_keys(validator, export):
    """A future BrewLogger field, and BrewGraph's own training annotations.

    The preserved originals carry `board`, `gyro`, `device_filtered`, `yeast`,
    `yeastProductId` and `truth` — added by BrewGraph, not BrewLogger. Refusing
    unknown keys would reject every file in `ai/data/brewlogger/`.
    """
    export["board"] = "esp32"
    export["truth"] = {"completion_time": "2026-07-09T06:00:00"}
    export["somethingBrewLoggerAddsIn2027"] = 42
    assert validator.is_valid(export), list(validator.iter_errors(export))


REJECTS = {
    "batch loses its name": lambda d: d.pop("name"),
    "batch loses its readings": lambda d: d.pop("gravity"),
    "a reading loses created": lambda d: d["gravity"][0].pop("created"),
    "created is empty": lambda d: d["gravity"][0].update(created=""),
    "gravity arrives as a string": lambda d: d["gravity"][0].update(gravity="1.010"),
    "og arrives as a string": lambda d: d.update(og="1.048"),
    "readings are not a list": lambda d: d.update(gravity={}),
    "active is a string": lambda d: d["gravity"][0].update(active="yes"),
}


@pytest.mark.parametrize("name", list(REJECTS))
def test_schema_rejects(validator, export, name):
    """Type errors are the failure mode worth catching in an untrusted format.

    A gravity of `"1.010"` looks right in a diff and computes wrong.
    """
    broken = copy.deepcopy(export)
    REJECTS[name](broken)
    assert not validator.is_valid(broken), f"schema accepted: {name}"
