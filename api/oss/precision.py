# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Decimal precision for each canonical quantity, enforced once, at the API.

The unit for each quantity is already canonical and unconverted (°C, litres,
grams, kPa, SG — see ingestion.py and the model column comments). The number
of *decimals* kept for a value was not: absent a shared source of truth, each
quantity's rounding is decided independently, wherever it happens to be
applied. This module is that source.

Quantisation happens here — at ingest, where device payloads arrive, and at
the write schemas, where API clients send values — never in service
arithmetic and never as input validation. A device or client sending more
digits than we keep (`18.4712`, `0.3300000001`) is not wrong; the reading is
good and rejecting it would be hostile to a client doing its own maths. The
API silently keeps only the digits that are meaningful for the quantity, so
every reader gets a value that is already rounded and never has to decide
how many decimals a quantity deserves.

`carbonation_volumes` / `carbonation_volumes_target` are deliberately absent
from this table — "volumes of CO2" is a dimensionless ratio, not a volume,
and carries no unit to quantise.
"""

from typing import Optional

from pydantic import field_validator

DECIMALS = {
    "temperature": 2,  # °C -- a DS18B20's 12-bit step is 0.0625 °C; a third decimal is noise
    "volume": 3,        # litres -- one millilitre
    "mass": 1,           # grams -- finer than any brewing scale resolves
    "pressure": 2,       # kPa -- below the sensors' noise floor
    "gravity": 4,        # SG -- one point of gravity is 0.001
    "battery": 2,        # volts -- the ADC does not justify more
    "signal": 0,         # dBm -- an integer quantity, float only for column uniformity
    "percent": 1,        # ABV / SoC
    # money -- NOT for an amount payable: currency minor units genuinely differ
    # (JPY/KRW use 0, most use 2), so a single global precision would be wrong for
    # a value someone is charged. This entry is only for a *derived analytic ratio*
    # (cost per litre), where minor-unit rules don't apply and 2 decimals is enough
    # for any currency's per-litre figure -- it matches what the cost summary UI
    # already renders with toFixed(2). Do not apply this to recipe_cost: that one
    # is user-entered, exact in Decimal, and its correct precision is currency-
    # dependent -- quantising it here would silently truncate a JPY amount.
    "money": 2,
}


def quantise(value: Optional[float], quantity: str) -> Optional[float]:
    """Round `value` to the canonical decimal count for `quantity`.

    None stays None -- an absent measurement is not a zero, and quantising
    one would turn "not measured" into a fabricated reading of 0.0.
    """
    if value is None:
        return None
    return round(value, DECIMALS[quantity])


def quantised(*field_names: str, quantity: str):
    """A reusable pydantic field_validator that quantises the named fields.

    One line per quantity per schema instead of a hand-written validator per
    field -- the figures still live in exactly one place (DECIMALS above),
    this just wires them up. Use as a class attribute:

        _quantise_temp = quantised("temperature", quantity="temperature")
    """

    def _validate(_cls, v):
        return quantise(v, quantity)

    return field_validator(*field_names)(classmethod(_validate))
