# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""A client model must not read a field the API never sends.

`test_frontend_endpoints.py` checks that every URL the frontend calls exists.
Nothing checked the *fields*, and the gap was not theoretical: for months
`BatchFermentationControlView` read `batch.fermentationSteps` and
`batch.fermentationChamber`, both always `undefined`, so half that screen could
never render and the header permanently claimed no chamber was selected. Every
suite stayed green, because the mock fixtures were written from the same
misunderstanding as the component.

This parses the keys each `fromJson` reads out of its argument and checks them
against the union of the OpenAPI schemas that can produce that entity. It is the
field-level analogue of the URL test, and like that one it runs against the live
app rather than a generated artefact.

**What it cannot catch:** a field that exists but is never populated, and a type
mismatch. It answers "could the API ever send this key".
"""

from __future__ import annotations

import re
from pathlib import Path

from main_oss import app

REPO_ROOT = Path(__file__).resolve().parents[2]
CLASSES = REPO_ROOT / "web" / "src" / "modules" / "classes"

#: Client class -> the OpenAPI schema names that produce it. A class is fed by more
#: than one schema (a list response and a dashboard projection carry different
#: subsets), so the check is against their union.
SCHEMA_SOURCES = {
    "Batch": ("BatchResponse", "BatchListResponse", "DashboardBatch", "BatchCreate"),
    "Device": ("DeviceResponse", "DeviceBase", "DashboardDevice"),
    "Tap": ("TapResponse", "DashboardTap", "TapCreate"),
    "StorageVessel": ("StorageVesselResponse", "StorageVesselListResponse",
                      "DashboardVessel", "StorageVesselCreate"),
    "BatchNote": ("BatchNoteResponse", "BatchNoteCreate"),
    "Prediction": ("PredictionResponse",),
    "Gravity": ("GravityReadingResponse", "GravityChartPoint"),
    "Pressure": ("PressureReadingResponse", "PressureChartPoint"),
    "PourEvent": ("PourEventResponse",),
    "FermentationStep": ("FermentationStepResponse", "FermentationStepCreate"),
}

#: Keys a class legitimately reads that no API schema provides, each with its reason.
#: Every entry here is a field the client owns; adding one is a decision, and an
#: entry that stops being read is caught by the staleness test below.
LOCAL_ONLY = {
    ("Batch", "fermentationSteps"): "carried by the backup/restore file format, not the API",
    ("Batch", "fermentationChamber"): "carried by the backup/restore file format, not the API",
    ("Device", "fermentationStep"): "read by brewloggerRestore from the BrewLogger import file",
}

_FROM_JSON = re.compile(r"static fromJson\s*\([^)]*\)\s*:[^{]*\{(.*?)\n  \}", re.S)


def _schema_properties(names: tuple[str, ...]) -> set[str]:
    """Union of property names across the given OpenAPI component schemas."""
    schemas = app.openapi()["components"]["schemas"]
    props: set[str] = set()
    for name in names:
        props |= set(schemas.get(name, {}).get("properties", {}))
    return props


def _keys_read(class_name: str) -> tuple[set[str], str]:
    """Return the keys `fromJson` reads from its argument, and the argument name."""
    source = (CLASSES / f"{class_name}.ts").read_text(encoding="utf-8")
    body_match = _FROM_JSON.search(source)
    assert body_match, f"could not find fromJson in {class_name}.ts"
    body = body_match.group(1)

    arg = re.search(r"static fromJson\s*\(\s*(\w+)", source).group(1)
    return set(re.findall(rf"\b{arg}\.(\w+)", body)), arg


def test_every_client_field_exists_in_some_response_schema():
    """A key no schema provides is always `undefined` — a dead binding waiting to happen."""
    ghosts: list[str] = []
    for class_name, schema_names in SCHEMA_SOURCES.items():
        if not (CLASSES / f"{class_name}.ts").exists():
            continue
        available = _schema_properties(schema_names)
        assert available, f"no OpenAPI schema found for {class_name}: {schema_names}"

        keys, _ = _keys_read(class_name)
        for key in sorted(keys - available):
            if (class_name, key) in LOCAL_ONLY:
                continue
            ghosts.append(f"{class_name}.fromJson reads `{key}`, absent from {schema_names}")

    assert not ghosts, (
        "these client fields are populated from keys the API never sends, so they are "
        "always undefined. Either the API should send them, or the client should stop "
        "reading them — or add them to LOCAL_ONLY with a reason:\n  " + "\n  ".join(ghosts)
    )


def test_no_local_only_entry_is_stale():
    """A LOCAL_ONLY entry the client stopped reading, or the API started sending."""
    stale: list[str] = []
    for (class_name, key), reason in LOCAL_ONLY.items():
        keys, _ = _keys_read(class_name)
        if key not in keys:
            stale.append(f"{class_name}.{key} is no longer read ({reason})")
        elif key in _schema_properties(SCHEMA_SOURCES[class_name]):
            stale.append(f"{class_name}.{key} is now a real API field ({reason})")
    assert not stale, "LOCAL_ONLY is out of date:\n  " + "\n  ".join(stale)


def test_the_parser_can_actually_see_fields():
    """Guards the guard: a regex that matches nothing would enforce nothing."""
    keys, arg = _keys_read("Batch")
    assert arg, "failed to find the fromJson argument name"
    assert {"id", "name", "brewDate"} <= keys, (
        f"the fromJson parser found only {sorted(keys)[:10]} — it has stopped working"
    )
