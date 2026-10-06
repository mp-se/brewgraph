# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tag metadata for the OpenAPI document.

Without this, FastAPI orders tags by whichever router mounted first and gives
none of them a description, so `/docs` renders one undifferentiated wall —
`batches` alone carries roughly a third of the operations. Ordering here is the
order a reader wants: the brewing entities first, then the readings hanging off
them, then ingest and operations.

Sub-resources take a ``parent - child`` tag so a batch's gravity endpoints group
separately from the batch itself. Operation-level tags override a router's, so
this needs no router splitting.
"""

#: Tag names, so a typo in a router is a NameError rather than a silent new group.
BATCHES = "batches"
BATCHES_GRAVITY = "batches - gravity"
BATCHES_PRESSURE = "batches - pressure"
BATCHES_TEMPERATURE = "batches - temperature"
BATCHES_STEPS = "batches - fermentation steps"
BATCHES_DRY_HOPS = "batches - dry hops"
BATCHES_NOTES = "batches - notes"
DEVICES = "devices"
DEVICES_LOCAL = "devices - local"
VESSELS = "vessels"
VESSELS_TEMPERATURE = "vessels - temperature"
VESSELS_PRESSURE = "vessels - pressure"
VESSELS_POURS = "vessels - pours"
TAPS = "taps"
PREDICTIONS = "predictions"
DASHBOARD = "dashboard"
EVENTS = "events"
INGEST = "ingest"
SYSTEM = "system"
TENANT = "tenant"
YEAST = "yeast"
BREWFATHER = "brewfather"
INTEGRATIONS = "integrations"

OPENAPI_TAGS = [
    {"name": BATCHES, "description": "Batch records and their lifecycle."},
    {"name": BATCHES_GRAVITY, "description": "Gravity readings for a batch."},
    {"name": BATCHES_PRESSURE, "description": "Pressure readings for a batch."},
    {"name": BATCHES_TEMPERATURE, "description": "Temperature readings for a batch."},
    {"name": BATCHES_STEPS, "description": "Fermentation step schedules and control."},
    {"name": BATCHES_DRY_HOPS, "description": "Dry hop additions and their triggers."},
    {"name": BATCHES_NOTES, "description": "Free-text notes on a batch."},
    {"name": DEVICES, "description": "Device records, assignment and tokens."},
    {
        "name": DEVICES_LOCAL,
        "description": (
            "Operations against hardware on the local network — proxying a request to a "
            "device, mDNS discovery, and device logs. These reach the device itself "
            "rather than its record."
        ),
    },
    {"name": VESSELS, "description": "Storage vessels: kegs and bottle sets."},
    {"name": VESSELS_TEMPERATURE, "description": "Temperature readings for a vessel."},
    {"name": VESSELS_PRESSURE, "description": "Pressure readings for a vessel."},
    {"name": VESSELS_POURS, "description": "Pour events recorded against a vessel."},
    {"name": TAPS, "description": "Taps and what is currently pouring from them."},
    {"name": PREDICTIONS, "description": "Model-generated predictions and their history."},
    {"name": DASHBOARD, "description": "Aggregate payload behind the home screen."},
    {"name": EVENTS, "description": "Server-sent event stream."},
    {"name": INGEST, "description": "Endpoints devices post their readings to."},
    {"name": SYSTEM, "description": "Health, logs, scheduler and self-test."},
    {"name": TENANT, "description": "Application-wide settings."},
    {"name": YEAST, "description": "The yeast strain library."},
    {"name": BREWFATHER, "description": "Brewfather import."},
    {
        "name": INTEGRATIONS,
        "description": "Account-level configuration for forwarding measurements to an "
                       "external service in the background.",
    },
]
