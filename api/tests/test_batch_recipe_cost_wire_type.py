"""`recipe_cost` must reach the wire as a JSON number, not a string.

`recipe_cost` is `Numeric(10, 2)` in the column and `Decimal` in Python, which is
right for currency. Pydantic v2 then serialises `Decimal` as a JSON **string** by
default, and declares `type: string` in the OpenAPI schema — while `cost_per_liter`,
the value derived from it, is a plain number. A client could not divide one by the
other.

This shipped unnoticed because **nothing asserted the JSON type**. It is also not a
dialect quirk: the annotation coerces a float to `Decimal` on the way in, so SQLite
produces `"12.34"` exactly like Postgres does. Tests that compared parsed values
rather than types passed either way.

It reached further than the API. `web/src/modules/backup/exportDocument.ts` types
`recipeCost` as `number | null` and copies the API's value straight into a
`brewgraph-batch-export-v1` document, whose schema requires a number — so a batch
with a recipe cost produced an export that fails its own schema.
"""
from __future__ import annotations

import json
from decimal import Decimal

from oss.schemas.batch import BatchBase


def test_recipe_cost_serialises_as_a_json_number():
    """A Decimal must emit as a number, which is what every consumer expects."""
    emitted = json.loads(BatchBase(recipe_cost=Decimal("12.34")).model_dump_json(by_alias=True))
    assert emitted["recipeCost"] == 12.34
    assert isinstance(emitted["recipeCost"], float), "emitted as a string, not a number"


def test_recipe_cost_survives_a_float_input_too():
    """SQLite hands back a float; the annotation coerces it, so this path matters."""
    emitted = json.loads(BatchBase(recipe_cost=12.34).model_dump_json(by_alias=True))
    assert emitted["recipeCost"] == 12.34
    assert isinstance(emitted["recipeCost"], float)


def test_recipe_cost_stays_null_when_unset():
    """`None` must not become `0.0` — an unpriced recipe is not a free one."""
    emitted = json.loads(BatchBase().model_dump_json(by_alias=True))
    assert emitted["recipeCost"] is None


def test_openapi_declares_recipe_cost_a_number():
    """The published contract has to agree with what is emitted.

    Asserted separately from the value: a serializer fixes the payload while
    leaving the OpenAPI schema advertising `type: string`, which is what clients
    generate their models from.
    """
    schema = BatchBase.model_json_schema(mode="serialization")
    declared = json.dumps(schema["properties"]["recipeCost"])
    assert '"string"' not in declared, f"recipeCost still declared as a string: {declared}"
    assert '"number"' in declared, f"recipeCost is not declared a number: {declared}"


def test_cost_per_liter_is_computed_from_recipe_cost_and_volume():
    """No column backs this field; it must still reach the wire, correctly.

    60.00 / 21.0 does not divide evenly (2.857142857142857...) -- this is the
    case that would fail if quantisation were ever removed from the field.
    """
    emitted = json.loads(
        BatchBase(recipe_cost=Decimal("60.00"), volume=21.0).model_dump_json(by_alias=True)
    )
    assert emitted["costPerLiter"] == 2.86


def test_cost_per_liter_is_null_when_volume_is_zero():
    """A computed field can newly crash here; it must return None, not divide by zero."""
    emitted = json.loads(
        BatchBase(recipe_cost=Decimal("12.34"), volume=0.0).model_dump_json(by_alias=True)
    )
    assert emitted["costPerLiter"] is None


def test_cost_per_liter_is_null_when_an_input_is_missing():
    """Absent recipe_cost or volume must not be treated as zero."""
    assert json.loads(BatchBase(volume=2.0).model_dump_json(by_alias=True))["costPerLiter"] is None
    assert (
        json.loads(BatchBase(recipe_cost=Decimal("12.34")).model_dump_json(by_alias=True))[
            "costPerLiter"
        ]
        is None
    )
