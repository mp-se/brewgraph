# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Battery voltage → State of Charge conversion.

The `battery` column on gravity, pressure and temperature readings is stored in
**volts**, bounded 0-10 V at ingest by `_safe_float` in `oss/services/ingestion.py`.
Every battery-powered device type reports voltage; none reports a percentage.

This module is the single place that fact is expressed. A consumer that instead
compares the raw column against a percentage threshold reads a healthy 3.9 V
cell as "4%" — silently, since the number is plausible. Import the conversion
here rather than reimplementing it.
"""

from typing import Optional

# 18650 OCV→SoC lookup (voltage, soc_percent). Linear interpolation between points.
OCV_18650 = [
    (4.20, 100.0),
    (4.05, 90.0),
    (3.90, 80.0),
    (3.80, 70.0),
    (3.70, 60.0),
    (3.60, 50.0),
    (3.50, 30.0),
    (3.40, 15.0),
    (3.30, 5.0),
    (3.00, 0.0),
]

# pressuremon uses a LiPo pouch cell, not an 18650, and its OCV curve has not been
# measured — aliasing it to the 18650 table is a documented approximation, not a
# claim that the two chemistries discharge identically. Inventing numbers instead
# would be worse: a fabricated curve looks measured and nobody would know to
# doubt it. Replacing this alias with a real LiPo curve is a one-line change once
# one is measured.
OCV_LIPO_POUCH = OCV_18650

DEFAULT_TABLE = OCV_18650

# Cutoff at 3.5 V (~5% SoC) — below this the 3.3 V LDO regulator loses dropout
# margin and the ESP32 browns out before the nominal 3.3 V cell minimum is
# reached. This is a regulator/MCU property, not a cell chemistry property.
CUTOFF_SOC = 5.0

_TABLES_BY_DEVICE_TYPE = {
    "pressuremon": OCV_LIPO_POUCH,
}


def table_for(device_type: Optional[str]) -> list:
    """Return the OCV→SoC curve for a device type, defaulting to the 18650 table."""
    if device_type is None:
        return DEFAULT_TABLE
    return _TABLES_BY_DEVICE_TYPE.get(device_type, DEFAULT_TABLE)


def voltage_to_soc(voltage: Optional[float], device_type: Optional[str] = None) -> Optional[float]:
    """Map an open-circuit voltage to State of Charge % via linear interpolation.

    Returns None when `voltage` is None, so callers can distinguish "no battery
    data" (e.g. a mains-powered device) from an actual 0% reading.
    """
    if voltage is None:
        return None
    table = table_for(device_type)
    if voltage >= table[0][0]:
        return table[0][1]
    if voltage <= table[-1][0]:
        return table[-1][1]
    for i in range(len(table) - 1):
        v_hi, s_hi = table[i]
        v_lo, s_lo = table[i + 1]
        if v_lo <= voltage <= v_hi:
            frac = (voltage - v_lo) / (v_hi - v_lo)
            return s_lo + frac * (s_hi - s_lo)
    return 0.0
