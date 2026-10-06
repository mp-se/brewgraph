# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Ingest dispatch — auto-detect device type from payload fields."""
from typing import Optional

from core.enums import DeviceType


def _detect_device_type(payload: dict) -> Optional[DeviceType]:
    """Detect device type from payload fields per spec dispatch rules.

    Returns None when the payload doesn't match any known device shape.
    """
    field_map = [
        ("maxVolume", DeviceType.KEGMON),
        ("pressure", DeviceType.PRESSUREMON),
        ("pressure_units", DeviceType.PRESSUREMON),
        ("beer_temperature", DeviceType.CHAMBER_CONTROLLER),
        ("fridge_temperature", DeviceType.CHAMBER_CONTROLLER),
        # GravityMon's HTTP-push template names the scale key "gravity-unit". It is checked
        # after the chamber fields (a bridge may relay it beside beer_temperature) and
        # before the bare "gravity" key, which means iSpindel.
        ("gravity-unit", DeviceType.GRAVITYMON),
        ("gravity", DeviceType.ISPINDEL),
    ]
    for field, device_type in field_map:
        if field in payload:
            return device_type
    if "temperature" in payload and "angle" not in payload:
        return DeviceType.CHAMBER_CONTROLLER
    return None
