# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Shape of the `GET /api/dashboard` response.

Every response model here builds on a shared base rather than being declared
independently, avoiding the full-retype pattern of duplicating the same fields
across seven near-identical models.

Every class here is a `*Base` usable directly (most fields need no per-repo addition) or
subclassed to add fields — an "additive override, not a retype" shape. Notably,
`DashboardBatchBase` is the one case where this repo's model is the fuller one:
`DashboardBatch` subclasses to add fields (`battery`/`rssi`/`last_reading_at`) that
`HomeView.vue` has a live dependency on the backend supplying directly, so the shared base
itself stays lean rather than carrying them.

`DashboardResponse` is deliberately NOT here: the router builds its own concrete response
directly from these subclasses, so a shared top-level model would only add indirection.

A future field belongs on the relevant `*Base` class here if broadly useful, or on a
subclass if it's specific to one feature area — exactly like `battery_soc` and
`last_pour_at`/`last_pour_amount` already are.
"""
import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict

from oss.schemas._camel import to_camel
from oss.schemas.prediction import PredictionResponse


def _camel_config() -> ConfigDict:
    return ConfigDict(alias_generator=to_camel, populate_by_name=True)


class LatestReadingBase(BaseModel):
    """Most recent sensor reading for a device."""

    model_config = _camel_config()

    gravity: Optional[float] = None
    pressure: Optional[float] = None
    temperature: Optional[float] = None
    # Volts, as stored — see `oss/services/ingestion.py`. A percentage (`_soc`
    # suffix) is a per-device-type addition, since the OCV curve lives with the
    # device type definition, not here.
    battery: Optional[float] = None
    rssi: Optional[float] = None
    recorded_at: Optional[datetime] = None


class DashboardDeviceBase(BaseModel):
    """Device summary for the dashboard."""

    model_config = _camel_config()

    id: uuid.UUID
    name: str
    chip_family: Optional[str] = None
    device_type: Optional[str] = None
    batch_id: Optional[uuid.UUID] = None
    batch_role: Optional[str] = None
    vessel_id: Optional[uuid.UUID] = None
    status: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    latest_reading: Optional[LatestReadingBase] = None
    predictions: List[PredictionResponse] = []


class DashboardBatchBase(BaseModel):
    """Active batch summary for the dashboard.

    `current_gravity` / `current_pressure` / `current_temp` are unambiguous
    because `Batch.gravity_device_id` / `pressure_device_id` / `temp_device_id`
    each designate exactly one device — the brewer's nomination, not a guess
    from whichever reading happens to exist.
    """

    model_config = _camel_config()

    id: uuid.UUID
    name: str
    status: Optional[str] = None
    brew_date: Optional[Any] = None
    day_count: Optional[int] = None
    og: Optional[float] = None
    fg: Optional[float] = None
    first_gravity: Optional[float] = None
    current_gravity: Optional[float] = None
    current_pressure: Optional[float] = None
    current_temp: Optional[float] = None
    temp_device_id: Optional[uuid.UUID] = None
    gravity_count: int = 0
    pressure_count: int = 0
    predictions: List[PredictionResponse] = []


class DashboardTapBase(BaseModel):
    """Tap summary including the currently assigned vessel for the dashboard."""

    model_config = _camel_config()

    id: uuid.UUID
    name: str
    tap_number: Optional[int] = None
    location: Optional[str] = None
    vessel_id: Optional[uuid.UUID] = None
    vessel_name: Optional[str] = None
    batch_name: Optional[str] = None
    batch_id: Optional[uuid.UUID] = None
    volume_remaining: Optional[float] = None
    predictions: List[PredictionResponse] = []


class DashboardVesselBase(BaseModel):
    """Storage vessel summary for the dashboard.

    Current readings are included so a client does not need a per-vessel
    "latest" endpoint to render the vessel card. `null` when the vessel has
    never reported one.
    """

    model_config = _camel_config()

    id: uuid.UUID
    name: str
    vessel_type: Optional[str] = None
    status: Optional[str] = None
    tap_id: Optional[uuid.UUID] = None
    batch_id: Optional[uuid.UUID] = None
    batch_name: Optional[str] = None
    total_volume: Optional[float] = None
    volume_remaining: Optional[float] = None
    fill_date: Optional[Any] = None
    current_temp: Optional[float] = None
    current_pressure: Optional[float] = None
    predictions: List[PredictionResponse] = []


class DashboardReadyItem(BaseModel):
    """A batch or vessel that has finished conditioning and is ready to serve.

    No per-repo variation — no `*Base` split needed.
    """

    model_config = _camel_config()

    id: uuid.UUID
    name: str
    kind: str
    ready_date: Optional[Any] = None
