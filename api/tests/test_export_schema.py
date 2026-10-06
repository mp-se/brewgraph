"""The export schema must reject, not merely exist.

`api/oss/export-v1.schema.json` is the single definition of
`brewgraph-batch-export-v1`, shared by every producer of the format. A schema
that accepts everything is decoration, so the cases below mutate a valid document
one field at a time and require each mutation to fail.

`unevaluatedProperties` is used throughout the schema rather than
`additionalProperties`, because the latter does not see through `$ref` -- a
composed subschema would silently accept any extra key. The "gains an unknown
key" cases are what hold that distinction in place.
"""
from __future__ import annotations

import copy
import json
import pathlib

import pytest
from jsonschema import Draft202012Validator

SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[1] / "oss/export-v1.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(name="validator", scope="module")
def fixture_validator() -> Draft202012Validator:
    """The schema, checked as a schema before it is used to check anything."""
    Draft202012Validator.check_schema(SCHEMA)
    return Draft202012Validator(SCHEMA)


@pytest.fixture(name="document")
def fixture_document() -> dict:
    """A minimal but complete `ml` document — the baseline every case mutates."""
    return {
        "schemaVersion": "1",
        "exportedAt": "2026-08-19T12:00:00Z",
        "source": "oss",
        "mode": "ml",
        "settings": {},
        "devices": [{
            "chipId": "abc123", "name": "Gravity", "role": "gravity",
            "board": "esp32", "gyroModel": "ICM42670P", "deviceFiltered": True,
        }],
        "taps": [],
        "vessels": [],
        "batches": [{
            "name": "Test Batch", "brewDate": "2026-08-01", "style": "Helles",
            "og": 1.048, "fg": 1.009, "abv": 5.1, "volume": 20.0,
            "yeast": "Diamond Lager", "yeastProductId": "lallemand-diamond-lager-yeast",
            "notes": None, "recipeCost": None, "costCurrency": None,
            "fermentation": None,
            "gravityReadings": [{
                "deviceChipId": "abc123", "gravity": 1.020, "temperature": 12.0,
                "angle": 45.0, "velocity": None, "battery": 4.1, "rssi": -60,
                "runTime": 3.2, "excluded": False, "isAggregate": False,
                "createdAt": "2026-08-02T00:00:00Z",
            }],
            "pressureReadings": [],
            "temperatureReadings": [],
            "fermentationSteps": [],
            "dryHops": [],
        }],
    }


def test_baseline_document_is_valid(validator, document):
    """Without this the rejection cases below could pass for the wrong reason."""
    assert validator.is_valid(document), list(validator.iter_errors(document))


def test_a_human_authored_label_is_allowed(validator, document):
    """`truth` may sit on a stored training file.

    No *producer* may write one — that is a rule about the writer, which a schema
    cannot express, so each producer's suite asserts it separately.
    """
    document["batches"][0]["truth"] = {
        "completion_time": "2026-08-05T06:00:00",
        "criteria": "Gravity settled within 0.002 SG and held",
    }
    assert validator.is_valid(document), list(validator.iter_errors(document))


def _without(doc, *path):
    """Delete a nested key and return the document."""
    target = doc
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]
    return doc


REJECTS = {
    "envelope loses mode":
        lambda d: _without(d, "mode"),
    "envelope gains an unknown key":
        lambda d: d.update(exportedBy="someone"),
    "mode is not one of the three":
        lambda d: d.update(mode="training"),
    "schemaVersion drifts":
        lambda d: d.update(schemaVersion="2"),
    "a gravity reading loses runTime":
        lambda d: _without(d, "batches", 0, "gravityReadings", 0, "runTime"),
    "a gravity reading gains an unknown column":
        lambda d: d["batches"][0]["gravityReadings"][0].update(corrGravity=1.01),
    "a batch entry gains an unknown field":
        lambda d: d["batches"][0].update(madeUp=True),
    "ml carries a backup-only identity field":
        lambda d: d["batches"][0].update(id="b1"),
    "ml carries batchNotes":
        lambda d: d["batches"][0].update(batchNotes=[]),
    "a device leaks an ingest token at ml depth":
        lambda d: d["devices"][0].update(token="secret"),
    "truth stores a duration instead of an instant":
        lambda d: d["batches"][0].update(truth={"hours_from_start": 552}),
    "gravity is a string":
        lambda d: d["batches"][0]["gravityReadings"][0].update(gravity="1.010"),
}


@pytest.mark.parametrize("name", list(REJECTS))
def test_schema_rejects(validator, document, name):
    """Each mutation must fail. A schema that never rejects guards nothing."""
    broken = copy.deepcopy(document)
    REJECTS[name](broken)
    assert not validator.is_valid(broken), f"schema accepted: {name}"


def test_lossless_rule_covers_every_reading_column(validator, document):
    """Dropping any reading column must fail: the archive is lossless.

    Enumerated from the document rather than a second literal list, so a column
    added to the schema is covered here without being added twice.
    """
    reading = document["batches"][0]["gravityReadings"][0]
    for column in list(reading):
        broken = copy.deepcopy(document)
        del broken["batches"][0]["gravityReadings"][0][column]
        assert not validator.is_valid(broken), f"dropping {column} was accepted"
