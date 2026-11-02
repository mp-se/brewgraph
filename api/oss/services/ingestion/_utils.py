# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Shared numeric parsing and model resolution for the ingestion service.

Not itself a use-case module — every oss/services/ingestion/_*.py mixin below
needs a subset of these, so they are resolved once here rather than each mixin
re-resolving its own copy of the same model class.
"""
import math
from typing import Optional

from core.models.registry import resolve_model
from oss.precision import quantise

Batch = resolve_model("Batch")
Device = resolve_model("Device")
GravityReading = resolve_model("GravityReading")
PourEvent = resolve_model("PourEvent")
PressureReading = resolve_model("PressureReading")
StorageVessel = resolve_model("StorageVessel")
TempReading = resolve_model("TempReading")
Tap = resolve_model("Tap")


class UnstorableValueError(ValueError):
    """A received value that cannot be stored; the router answers it with a 422.

    ``field`` names the offending payload field and ``cause`` says why in a few words,
    never the value itself.
    """

    def __init__(self, field: str, cause: str):
        super().__init__(f"{field}: {cause}")
        self.field = field
        self.cause = cause


class NoActiveVesselError(ValueError):
    """A KegMon report for a tap that has no vessel on it; the router ignores it."""


def _safe_float(value, default: Optional[float] = 0.0) -> Optional[float]:
    """Convert value to a float as received; text, absent and NaN/Inf values give default.

    There is no range: a measurement is stored exactly as the device sent it.
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(f):
        return default
    return f


def _optional_float(payload: dict, *keys: str) -> Optional[float]:
    """The first of ``keys`` present in payload as a float; None when absent or unusable.

    An optional measurement that was not sent is stored as null, never as zero.
    """
    for key in keys:
        if payload.get(key) is not None:
            return _safe_float(payload[key], default=None)
    return None


def _required_float(payload: dict, key: str) -> float:
    """The primary value of a reading; a missing or non-finite one cannot be stored."""
    value = _safe_float(payload.get(key), default=None)
    if value is None:
        raise UnstorableValueError(key, "missing or not a finite number")
    return value


def _finite(value: float, field: str) -> float:
    """Guard a converted value: an unit conversion of a huge number may overflow."""
    if not math.isfinite(value):
        raise UnstorableValueError(field, "not a finite number after unit conversion")
    return value


def _payload_temperature(payload: dict) -> Optional[float]:
    """Parse an optional device temperature payload into Celsius.

    The unit is the wire contract's ``temp_units`` (``C`` or ``F``); the ingest
    schemas guarantee that key, so no alternate spellings are read here.
    """
    temperature = _optional_float(payload, "temperature")
    if temperature is None:
        return None
    if payload.get("temp_units", "C").upper() == "F":
        temperature = quantise((temperature - 32) * 5 / 9, "temperature")
    return temperature
