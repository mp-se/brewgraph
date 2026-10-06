# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Ingest-handler registry — the set of ingest sources this build supports.

Each supported ingest source registers a handler declaring its payload shape,
its field mapping, and (where one exists) the device type it produces.
Adding an ingest source is a registration, never a new forked router.

Two structurally distinct handler shapes exist among the sources registered
below, split on whether the source has a device type to declare:

- ``TypedIngestHandler`` — resolves a ``Device`` row (via
  ``IngestionService.resolve_device``) and mints its own ``device_type``:
  the kind of reading this source itself produces.
- ``UntypedIngestHandler`` — has no ``device_type`` of its own to declare.
  Tap-token sources (``kegmon``, ``kegmon-beer``) resolve a ``Tap`` row (via
  ``IngestionService.resolve_tap``), never a ``Device`` at all — there is no
  device type for them to produce.

Neither case models "device type: absent-but-checkable" with a nullable
field — the attribute is structurally absent from ``UntypedIngestHandler``
entirely, so a handler cannot be registered in an invalid state (a typed
handler with no device_type, or an untyped handler carrying a stray one).
The ``auth`` field stays on both shapes as informational metadata about how
the source's token is resolved; it does not drive which type is used.
"""
from dataclasses import dataclass, field
from typing import Mapping, Optional, Type, Union

from pydantic import BaseModel

from core.enums import DeviceType
from oss.schemas.ingest import (
    ChamberIngestRequest,
    GravityIngestRequest,
    IspindelIngestRequest,
    KegmonBeerRequest,
    KegmonIngestRequest,
    PressureIngestRequest,
)


@dataclass(frozen=True)
class TypedIngestHandler:
    """A registered ingest source that mints its own ``device_type``.

    ``source`` is the key used in the ingest path (``/api/ingest/{source}``).
    ``payload_schema`` is the Pydantic model the wire payload is validated
    against. ``field_mapping`` documents wire-field -> internal-meaning for
    fields the router remaps before writing (informational; the router
    remains the executable source of truth). ``device_type`` is the
    ``DeviceType`` this source's readings are classified as — always
    present; a source with no device type to declare belongs to
    ``UntypedIngestHandler`` instead. ``auth`` is informational only:
    "device_token" for every source registered with this shape today.
    """

    source: str
    payload_schema: Type[BaseModel]
    device_type: DeviceType
    field_mapping: Mapping[str, str] = field(default_factory=dict)
    auth: str = "device_token"


@dataclass(frozen=True)
class UntypedIngestHandler:
    """A registered ingest source with no ``device_type`` of its own.

    Same fields as ``TypedIngestHandler`` except ``device_type`` is
    structurally absent, not present-and-``None`` — used by tap-token
    sources, which resolve a ``Tap`` row rather than a ``Device``.
    """

    source: str
    payload_schema: Type[BaseModel]
    auth: str  # "device_token" | "tap_token"
    field_mapping: Mapping[str, str] = field(default_factory=dict)


IngestHandler = Union[TypedIngestHandler, UntypedIngestHandler]


class IngestHandlerRegistry:
    """A mutable set of registered ingest handlers, keyed by source."""

    def __init__(self) -> None:
        self._handlers: dict[str, IngestHandler] = {}

    def register(self, handler: IngestHandler) -> None:
        """Add a handler to the registered set."""
        self._handlers[handler.source] = handler

    def get(self, source: str) -> Optional[IngestHandler]:
        """Return the handler registered for ``source``, or ``None``."""
        return self._handlers.get(source)

    def all(self) -> Mapping[str, IngestHandler]:
        """Return all registered handlers, keyed by source."""
        return dict(self._handlers)


ingest_handler_registry = IngestHandlerRegistry()

ingest_handler_registry.register(TypedIngestHandler(
    source="gravitymon",
    payload_schema=GravityIngestRequest,
    device_type=DeviceType.GRAVITYMON,
    field_mapping={"id": "chip_id", "gravity-unit": "gravity_unit"},
))

ingest_handler_registry.register(TypedIngestHandler(
    source="ispindel",
    payload_schema=IspindelIngestRequest,
    device_type=DeviceType.ISPINDEL,
    field_mapping={"ID": "chip_id", "temp_units": "temp_units"},
))

ingest_handler_registry.register(TypedIngestHandler(
    source="pressuremon",
    payload_schema=PressureIngestRequest,
    device_type=DeviceType.PRESSUREMON,
    field_mapping={"id": "chip_id", "pressure_units": "pressure_units"},
))

ingest_handler_registry.register(TypedIngestHandler(
    source="chamber",
    payload_schema=ChamberIngestRequest,
    device_type=DeviceType.CHAMBER_CONTROLLER,
    field_mapping={"beer_temperature": "beer_temperature",
                   "fridge_temperature": "fridge_temperature"},
))

ingest_handler_registry.register(UntypedIngestHandler(
    source="kegmon",
    payload_schema=KegmonIngestRequest,
    auth="tap_token",
    field_mapping={},
))

ingest_handler_registry.register(UntypedIngestHandler(
    source="kegmon-beer",
    payload_schema=KegmonBeerRequest,
    auth="tap_token",
    field_mapping={},
))
