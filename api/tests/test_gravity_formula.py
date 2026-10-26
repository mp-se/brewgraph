# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Shared known-answer vectors for the bounded gravity formula language."""

import json
import random
import time
from decimal import Decimal
from pathlib import Path

import pytest

from oss.gravity_formula import (
    FormulaError, GRAVITY_FORMULA_MAX_LENGTH, GRAVITY_FORMULA_MAX_TOKENS,
    evaluate_formula, normalize_formula, temperature_correct_gravity, validate_formula,
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


def test_sign_before_power_error_names_the_fix():
    """The rejection tells the user which parenthesised forms are valid."""
    message = r"ambiguous; add parentheses: \(-tilt\)\^2 or -\(tilt\^2\)"
    with pytest.raises(FormulaError, match=message):
        validate_formula("-tilt^2")


def test_parenthesised_and_polynomial_signs_stay_valid():
    """A sign in front of a group or a product, or a binary minus, is unambiguous."""
    assert evaluate_formula("1.1-(tilt^2)/10000", 30, 20, "sg") == pytest.approx(1.01)
    assert evaluate_formula("-8.1e-7*tilt^3+1.1", 30, 20, "sg") == pytest.approx(1.07813)


NORMALIZATION = VECTORS["normalization"]


@pytest.mark.parametrize("vector", NORMALIZATION["valid"], ids=lambda v: v["input"][:30])
def test_normalization_vectors(vector):
    """Exponent notation is rewritten to the exactly equal plain decimal, byte for byte."""
    assert normalize_formula(vector["input"]) == vector["output"]
    assert normalize_formula(vector["output"]) == vector["output"]


@pytest.mark.parametrize("formula", NORMALIZATION["notAnExponent"])
def test_marker_without_digits_is_not_an_exponent(formula):
    """An `e` that is not followed by ASCII digits is left for the parser to reject."""
    assert normalize_formula(formula) == formula


@pytest.mark.parametrize("formula", NORMALIZATION["invalidExponent"])
def test_out_of_range_exponent_is_rejected_by_normalization(formula):
    """An exponent outside -30..30, or a rewrite past the length limit, is a syntax error."""
    with pytest.raises(FormulaError):
        normalize_formula(formula)


@pytest.mark.parametrize("formula", NORMALIZATION["invalidFormula"])
def test_normalization_invalid_formulas(formula):
    """Everything the normalization rules reject also fails validation."""
    with pytest.raises(FormulaError):
        validate_formula(formula)


def _random_literal(rng):
    whole = str(rng.randint(0, 99999))
    fraction = "." + "".join(rng.choice("0123456789") for _ in range(rng.randint(0, 6)))
    mantissa = whole + (fraction if rng.random() < 0.5 else "")
    if rng.random() < 0.1:
        mantissa = fraction if len(fraction) > 1 else "1"
    return f"{mantissa}{rng.choice('eE')}{rng.choice(['', '+', '-'])}{rng.randint(0, 30)}"


def test_normalization_is_idempotent_and_exact():
    """Normalizing twice changes nothing; a random valid literal equals its plain decimal."""
    rng = random.Random(20261011)
    samples = [v["input"] for v in NORMALIZATION["valid"]] + list(NORMALIZATION["notAnExponent"])
    samples += [_random_literal(rng) for _ in range(500)]
    junk = "0123456789.eE+-*tilt_"
    samples += ["".join(rng.choice(junk) for _ in range(rng.randint(1, 14))) for _ in range(2000)]
    for sample in samples:
        try:
            once = normalize_formula(sample)
        except FormulaError:
            continue
        assert normalize_formula(once) == once, sample
    for _ in range(500):
        literal = _random_literal(rng)
        assert Decimal(normalize_formula(literal)) == Decimal(literal), literal


JUNK_TOKENS = [
    "0", "1", "2", "3", "5", "9", ".", "e", "E", "+", "-", "*", "^", "(", ")", "tilt", "temp", " ",
]
JUNK_COUNT = 30000


def _junk_corpus():
    """Token strings from a fixed generator that the web test reproduces exactly."""
    seed = 20261011

    def draw():
        nonlocal seed
        seed = (seed * 1664525 + 1013904223) % 4294967296
        return seed / 4294967296

    return [
        "".join(JUNK_TOKENS[int(draw() * len(JUNK_TOKENS))] for _ in range(1 + int(draw() * 16)))
        for _ in range(JUNK_COUNT)
    ]


def _outcome(sample):
    try:
        return normalize_formula(sample)
    except FormulaError:
        return None


def _fnv1a(text):
    value = 2166136261
    for char in text:
        value = ((value ^ ord(char)) * 16777619) % 4294967296
    return f"{value:08x}"


@pytest.mark.parametrize("formula", NORMALIZATION["strayMarker"])
def test_stray_exponent_marker_leaves_the_input_unchanged(formula):
    """An `e` right after a number makes the whole input unchanged, and validation rejects it."""
    assert normalize_formula(formula) == formula
    with pytest.raises(FormulaError):
        validate_formula(formula)


def test_normalization_is_idempotent_for_junk_input():
    """Every input, valid or not, is a fixed point after one pass and never raises on the second."""
    samples = [v["input"] for v in NORMALIZATION["valid"]] + NORMALIZATION["notAnExponent"]
    samples += NORMALIZATION["strayMarker"] + NORMALIZATION["invalidExponent"]
    samples += _junk_corpus()
    outcomes = []
    for sample in samples:
        once = _outcome(sample)
        if once is not None:
            assert normalize_formula(once) == once, sample
        outcomes.append("!" if once is None else once)
    assert _fnv1a("\n".join(outcomes[-JUNK_COUNT:])) == NORMALIZATION["junkDigest"]


def test_normalization_time_is_linear_on_pathological_input():
    """200-character inputs built to provoke backtracking finish instantly."""
    started = time.perf_counter()
    for unit in ("1e", "1.e", ".1e+", "1e+1e", "0" * 9 + "e", "1.", "e1", "1.1.1e1", ".e"):
        _outcome((unit * 200)[:GRAVITY_FORMULA_MAX_LENGTH])
    assert time.perf_counter() - started < 1.0


def test_exponent_formula_evaluates_like_its_plain_decimal():
    """A formula with exponent literals evaluates exactly as its rewritten text does."""
    source = "-8.1595791e-7*tilt^3+0.00010120890*tilt^2-0.0022066128*tilt+0.99997836"
    plain = normalize_formula(source)
    assert "e" not in plain
    assert evaluate_formula(source, 45) == evaluate_formula(plain, 45)


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
