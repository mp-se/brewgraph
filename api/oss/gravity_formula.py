# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Gravity formula limits and the per-device formula unit.

The formula unit is the unit a device's gravity formula returns. It is stored
nullable on the device (``null`` selects the family default) and the effective
unit is derived here, in one place, so the API response and any formula
evaluator agree.
"""
import math
import re
from typing import Literal, Optional

GRAVITY_FORMULA_MAX_LENGTH = 200
GRAVITY_FORMULA_MAX_TOKENS = 128
GRAVITY_CALIBRATION_MAX_POINTS = 20
MIN_VALID_ANGLE_DEG = 15
MAX_VALID_ANGLE_DEG = 90
MIN_VALID_GRAVITY_SG = 0.98
MAX_VALID_GRAVITY_SG = 1.25
_MAX_LITERAL = 1_000_000
_MAX_INTERMEDIATE = 1_000_000_000_000
_TOKEN = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)|[A-Za-z_]\w*|[()+*/^\-]")

# Includes the SaaS-only RAPT Pill; OSS's registry still rejects that type at its API boundary.
GRAVITY_DEVICE_TYPES = frozenset({"gravitymon", "ispindel", "rapt_pill"})

FormulaUnit = Literal["sg", "plato"]
_SG_NAME_PREFIX = "[SG]"


def can_carry_formula(device_type: Optional[str]) -> bool:
    """A device of a gravity type, or of a not-yet-known type, may carry a formula."""
    return device_type is None or device_type in GRAVITY_DEVICE_TYPES


def family_default_unit(device_type: Optional[str], name: Optional[str]) -> FormulaUnit:
    """The formula unit a device uses when none is stored."""
    if device_type == "ispindel":
        return "sg" if (name or "").startswith(_SG_NAME_PREFIX) else "plato"
    return "sg"


def effective_formula_unit(
    device_type: Optional[str], name: Optional[str], stored: Optional[str]
) -> Optional[FormulaUnit]:
    """The unit reported for a device, or ``None`` when the device cannot carry a formula."""
    if not can_carry_formula(device_type):
        return None
    return stored or family_default_unit(device_type, name)  # type: ignore[return-value]


class FormulaError(ValueError):
    """Invalid formula or a formula that cannot produce usable gravity."""


def _tokens(formula: str) -> list[str]:
    if not formula or len(formula) > GRAVITY_FORMULA_MAX_LENGTH:
        raise FormulaError("formula is empty or exceeds the length limit")
    tokens = []
    pos = 0
    while pos < len(formula):
        if formula[pos] in " \t\r\n\f\v":
            pos += 1
            continue
        match = _TOKEN.match(formula, pos)
        if match is None:
            raise FormulaError(f"invalid formula character at position {pos + 1}")
        tokens.append(match.group())
        if len(tokens) > GRAVITY_FORMULA_MAX_TOKENS:
            raise FormulaError("formula exceeds the token limit")
        pos = match.end()
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.index = 0

    def peek(self) -> Optional[str]:
        """Return the next token without consuming it."""
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self) -> str:
        """Consume one token or reject an unexpected end."""
        token = self.peek()
        if token is None:
            raise FormulaError("unexpected end of formula")
        self.index += 1
        return token

    def expression(self):
        """Parse addition and subtraction."""
        node = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            node = (op, node, self.term())
        return node

    def term(self):
        """Parse multiplication and division."""
        node = self.unary()
        while self.peek() in ("*", "/"):
            op = self.take()
            node = (op, node, self.unary())
        return node

    def unary(self):
        """Parse a unary sign before a power expression."""
        if self.peek() in ("+", "-"):
            return ("u" + self.take(), self.unary())
        return self.power()

    def power(self):
        """Parse a bounded integer power."""
        node = self.primary()
        if self.peek() == "^":
            self.take()
            exponent = self.take()
            if exponent not in ("1", "2", "3", "4", "5", "6"):
                raise FormulaError("power must be an integer literal from 1 to 6")
            node = ("^", node, int(exponent))
        return node

    def primary(self):
        """Parse a number, variable, or parenthesized expression."""
        token = self.take()
        if token == "(":
            node = self.expression()
            if self.take() != ")":
                raise FormulaError("missing closing parenthesis")
            return node
        if token in ("tilt", "temp"):
            return ("var", token)
        if token[0].isdigit() or token[0] == ".":
            value = float(token)
            if not math.isfinite(value) or value > _MAX_LITERAL:
                raise FormulaError("numeric literal is too large")
            return ("num", value)
        raise FormulaError(f"unknown identifier or unexpected token: {token}")


def validate_formula(formula: str):
    """Parse the bounded, shared firmware-compatible subset without executing code."""
    parser = _Parser(_tokens(formula))
    node = parser.expression()
    if parser.peek() is not None:
        raise FormulaError(f"unexpected token: {parser.peek()}")
    return node


def _value(node, tilt: float, temp: Optional[float]) -> float:  # pylint: disable=too-many-branches
    op = node[0]
    if op == "num":
        return node[1]
    if op == "var":
        if node[1] == "tilt":
            return tilt
        if temp is None or not math.isfinite(temp):
            raise FormulaError("temperature is required by this formula")
        return temp
    if op in ("u+", "u-"):
        result = _value(node[1], tilt, temp)
        return result if op == "u+" else -result
    left = _value(node[1], tilt, temp)
    if op == "^":
        result = left ** node[2]
    else:
        right = _value(node[2], tilt, temp)
        if op == "+":
            result = left + right
        elif op == "-":
            result = left - right
        elif op == "*":
            result = left * right
        elif right == 0:
            raise FormulaError("division by zero")
        else:
            result = left / right
    if not math.isfinite(result) or abs(result) > _MAX_INTERMEDIATE:
        raise FormulaError("formula result exceeds the intermediate limit")
    return result


def plato_to_gravity(plato: float) -> float:
    """The same Plato-to-SG conversion used by the OSS web core."""
    denominator = 258.6 - 227.1 * (plato / 258.2)
    if denominator == 0:
        raise FormulaError("Plato value cannot be converted to SG")
    return 1 + plato / denominator


def temperature_correct_gravity(
    gravity_sg: float, temp_c: float, calibration_temp_c: float = 20
) -> float:
    """Apply the firmware's hydrometer-temperature correction after formula evaluation."""
    def factor(celsius: float) -> float:
        fahrenheit = celsius * 1.8 + 32
        return (1.00130346 - 0.000134722124 * fahrenheit
                + 0.00000204052596 * fahrenheit ** 2
                - 0.00000000232820948 * fahrenheit ** 3)
    return gravity_sg * factor(temp_c) / factor(calibration_temp_c)


def evaluate_formula(  # pylint: disable=too-many-arguments
    formula: str, tilt: float, temp: Optional[float] = None,
    unit: FormulaUnit = "sg", *, correct_temperature: bool = False,
    calibration_temp_c: float = 20,
) -> float:
    """Evaluate to canonical SG, rejecting unusable readings and unsafe results."""
    if not math.isfinite(tilt) or not MIN_VALID_ANGLE_DEG <= tilt <= MAX_VALID_ANGLE_DEG:
        raise FormulaError("angle is outside the valid range")
    if unit not in ("sg", "plato"):
        raise FormulaError("unknown formula unit")
    result = _value(validate_formula(formula), tilt, temp)
    gravity = result if unit == "sg" else plato_to_gravity(result)
    if correct_temperature:
        if temp is None or not math.isfinite(temp):
            raise FormulaError("temperature is required for correction")
        gravity = temperature_correct_gravity(gravity, temp, calibration_temp_c)
    if not math.isfinite(gravity) or not MIN_VALID_GRAVITY_SG <= gravity <= MAX_VALID_GRAVITY_SG:
        raise FormulaError("gravity is outside the valid range")
    return gravity
