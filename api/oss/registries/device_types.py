# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Device-type registry — the set of ``Device.device_type`` values this
build accepts.

``device_type`` is a validated string, not a shared enum: each product
registers the device types it supports at import time, and the schema layer
validates incoming values against whatever is registered. An unregistered
value is rejected with a 422 rather than silently stored.

The device types supported are registered below, pulled from
``core.enums.DeviceType`` so every value that validated before this registry
existed still validates after.
"""
from core.enums import DeviceType


class DeviceTypeRegistry:
    """A mutable set of accepted ``device_type`` string values."""

    def __init__(self) -> None:
        self._types: set[str] = set()

    def register(self, device_type: str) -> None:
        """Add a device type to the accepted set."""
        self._types.add(device_type)

    def is_registered(self, device_type: str) -> bool:
        """Return whether ``device_type`` is currently accepted."""
        return device_type in self._types

    def all(self) -> frozenset[str]:
        """Return the currently accepted device types."""
        return frozenset(self._types)


device_type_registry = DeviceTypeRegistry()

for _member in DeviceType:
    device_type_registry.register(_member.value)
