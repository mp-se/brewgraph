"""Shared known-answer vectors for the bounded gravity formula language."""

import json
from pathlib import Path

import pytest

from oss.gravity_formula import (
    FormulaError, GRAVITY_FORMULA_MAX_LENGTH, GRAVITY_FORMULA_MAX_TOKENS,
    evaluate_formula, temperature_correct_gravity, validate_formula,
)


VECTORS = json.loads(
    (Path(__file__).parents[2] / "web/src/core/gravityFormula/vectors.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("vector", VECTORS["valid"])
def test_valid_vectors(vector):
    """Python SG results agree with the cross-language fixture."""
    assert evaluate_formula(
        vector["formula"], vector["tilt"], vector["temp"], vector["unit"]
    ) == pytest.approx(vector["gravitySg"], abs=1e-10)


@pytest.mark.parametrize("formula", VECTORS["invalidFormula"])
def test_invalid_formula_vectors(formula):
    """Unsafe or unsupported source is rejected before evaluation."""
    with pytest.raises(FormulaError):
        validate_formula(formula)


@pytest.mark.parametrize("vector", VECTORS["invalidReading"])
def test_invalid_reading_vectors(vector):
    """Unusable readings never produce a gravity value."""
    with pytest.raises(FormulaError):
        evaluate_formula(
            vector["formula"], vector["tilt"], vector["temp"], vector["unit"]
        )


@pytest.mark.parametrize("vector", VECTORS["temperatureCorrection"])
def test_temperature_correction_vectors(vector):
    """The firmware correction stays aligned with the shared fixture."""
    assert temperature_correct_gravity(
        vector["gravitySg"], vector["tempC"], vector["calibrationTempC"]
    ) == pytest.approx(vector["correctedSg"], abs=1e-10)


def test_formula_limits_and_missing_temperature():
    """Bound parse work and require temperature only when referenced."""
    with pytest.raises(FormulaError, match="token limit"):
        validate_formula("+".join(["1"] * 65))
    with pytest.raises(FormulaError, match="temperature"):
        evaluate_formula("1 + temp / 1000", 30)
    assert GRAVITY_FORMULA_MAX_LENGTH == VECTORS["limits"]["maxLength"]
    assert GRAVITY_FORMULA_MAX_TOKENS == VECTORS["limits"]["maxTokens"]
