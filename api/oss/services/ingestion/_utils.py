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


def _safe_float(value, default: float = 0.0, lo: float = -1e9, hi: float = 1e9) -> float:
    """Convert value to float, clamping to [lo, hi] and replacing NaN/Inf with default."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(f):
        return default
    return max(lo, min(hi, f))


def _payload_temperature(payload: dict) -> Optional[float]:
    """Parse an optional device temperature payload into Celsius.

    The unit is the wire contract's ``temp_units`` (``C`` or ``F``); the ingest
    schemas guarantee that key, so no alternate spellings are read here.
    """
    raw = payload.get("temperature")
    if raw is None:
        return None
    temperature = _safe_float(raw, default=None, lo=-270.0, hi=200.0)  # type: ignore[arg-type]
    if temperature is None or temperature <= -270:
        return None
    if payload.get("temp_units", "C").upper() == "F":
        temperature = quantise((temperature - 32) * 5 / 9, "temperature")
    return temperature
