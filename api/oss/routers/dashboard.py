# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Unified dashboard endpoint — returns all home-screen data in one request."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import Depends
from fastapi.routing import APIRouter
from pydantic import BaseModel, ConfigDict

from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.extensions.retention import \
    oss_retention_provider as get_retention_cutoff
from oss.models.prediction import Prediction
from oss.schemas._camel import to_camel
from oss.schemas.dashboard import (DashboardBatchBase, DashboardDeviceBase,
                                   DashboardReadyItem, DashboardTapBase,
                                   DashboardVesselBase, LatestReadingBase)
from oss.schemas.prediction import PredictionResponse
from oss.services import (BatchService, DeviceService, GravityService,
                          PressureService, get_batch_service,
                          get_device_service, get_gravity_service,
                          get_prediction_service, get_pressure_service,
                          get_tap_service, get_temp_service,
                          get_vessel_service)
from oss.services.prediction import PredictionService
from oss.services.storage_vessel import StorageVesselService
from oss.services.tap import TapService
from oss.services.temp_reading import TempService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["dashboard"], dependencies=[Depends(api_key_auth)])


# ---------------------------------------------------------------------------
# Response schemas — see oss/schemas/dashboard.py for the shared base shapes.
# This repo has no extra fields on LatestReading/DashboardDevice/DashboardTap/
# DashboardVessel, so those are direct aliases; DashboardBatch is the one model
# where this repo adds fields (battery/rssi/last_reading_at) on top of the
# shared base.
# ---------------------------------------------------------------------------

class LatestReading(LatestReadingBase):
    """No additions here — empty subclass so the OpenAPI component name
    stays `LatestReading` rather than the shared `LatestReadingBase`."""


class DashboardDevice(DashboardDeviceBase):
    """No additions here — see `LatestReading` above."""


class DashboardTap(DashboardTapBase):
    """No additions here — see `LatestReading` above."""


class DashboardVessel(DashboardVesselBase):
    """No additions here — see `LatestReading` above."""


class DashboardBatch(DashboardBatchBase):
    """Active batch summary for the dashboard, with this repo's telemetry fields.

    `HomeView.vue` has a live dependency on the backend supplying these directly,
    so they stay here rather than in the shared base.
    """

    # These are across gravity, pressure, and temperature readings, not gravity-only:
    # a pressure-only or temp-only batch must retain a meaningful measurement timeline.
    first_reading_at: Optional[datetime] = None
    battery: Optional[float] = None
    rssi: Optional[float] = None
    last_reading_at: Optional[datetime] = None


class DashboardResponse(BaseModel):
    """Top-level response returned by GET /api/dashboard."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    devices: List[DashboardDevice]
    batches: List[DashboardBatch]
    taps: List[DashboardTap]
    vessels: List[DashboardVessel]
    ready_batches: List[DashboardReadyItem] = []
    ready_vessels: List[DashboardReadyItem] = []



# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    response_model_by_alias=True,
    dependencies=[Depends(api_key_auth)],
)
async def get_dashboard(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements
    device_service: DeviceService = Depends(get_device_service),
    batch_service: BatchService = Depends(get_batch_service),
    gravity_service: GravityService = Depends(get_gravity_service),
    pressure_service: PressureService = Depends(get_pressure_service),
    temp_service: TempService = Depends(get_temp_service),
    prediction_service: PredictionService = Depends(get_prediction_service),
    tap_service: TapService = Depends(get_tap_service),
    vessel_service: StorageVesselService = Depends(get_vessel_service),
    retention_cutoff: Optional[datetime] = Depends(get_retention_cutoff),
) -> DashboardResponse:
    """Return all home-screen data in a single request."""
    logger.info("Endpoint GET /dashboard")

    # --- devices ---
    device_status_map = {s.device_id: s for s in device_service.status_for_all()}
    devices = device_service.list()
    device_ids = [d.id for d in devices]
    # One query per relation, not one per device: see oss/services/_batched.py.
    device_gravity = gravity_service.latest_for_devices(
        [d.id for d in devices if d.batch_role == "gravity"]
    )
    device_pressure = pressure_service.latest_for_devices(
        [d.id for d in devices if d.batch_role in ("pressure", "chamber")]
    )
    device_predictions = prediction_service.latest_for_owners(
        Prediction.device_id, device_ids
    )
    dashboard_devices: List[DashboardDevice] = []
    for d in devices:
        latest: Optional[LatestReading] = None
        if d.batch_role == "gravity":
            r = device_gravity.get(d.id)
            if r:
                latest = LatestReading(
                    gravity=r.gravity,
                    angle=r.angle,
                    temperature=r.temperature,
                    battery=r.battery,
                    rssi=r.rssi,
                    recorded_at=r.created_at,
                )
        elif d.batch_role in ("pressure", "chamber"):
            r = device_pressure.get(d.id)
            if r:
                latest = LatestReading(
                    pressure=r.pressure,
                    temperature=r.temperature,
                    battery=r.battery,
                    rssi=r.rssi,
                    recorded_at=r.created_at,
                )
        ds = device_status_map.get(d.id)
        device_prediction = device_predictions.get(d.id)
        device_preds = (
            [PredictionResponse.model_validate(device_prediction)]
            if device_prediction is not None else []
        )
        dashboard_devices.append(DashboardDevice(
            id=d.id,
            name=d.name,
            chip_family=d.chip_family,
            device_type=d.device_type,
            batch_id=d.batch_id,
            batch_role=d.batch_role,
            vessel_id=d.vessel_id,
            status=ds.status.value if ds else None,
            last_seen_at=ds.last_seen_at if ds else None,
            latest_reading=latest,
            predictions=device_preds,
        ))

    # --- batches (active only) ---
    dashboard_batches: List[DashboardBatch] = []
    ingesting_batches = batch_service.search_accepting_ingest()
    ingesting_ids = [b.id for b in ingesting_batches]
    batch_latest_g = gravity_service.latest_for_batches(
        ingesting_ids, retention_cutoff=retention_cutoff
    )
    batch_latest_p = pressure_service.latest_for_batches(ingesting_ids)
    batch_g_counts = gravity_service.count_for_batches(
        ingesting_ids, retention_cutoff=retention_cutoff
    )
    batch_p_counts = pressure_service.count_for_batches(
        ingesting_ids, retention_cutoff=retention_cutoff
    )
    batch_first_g = gravity_service.earliest_for_batches(ingesting_ids)
    batch_first_p = pressure_service.earliest_for_batches(ingesting_ids)
    batch_first_temp = temp_service.earliest_for_batches(ingesting_ids)
    batch_predictions = prediction_service.latest_for_owners(
        Prediction.batch_id, ingesting_ids
    )
    # `current_temp` is sourced from the batch's own nominated `temp_device_id`, never
    # guessed from whichever of the gravity/pressure devices happens to have a reading —
    # a chamber controller can carry a genuine beer-temperature sensor alongside its
    # fridge-air one, and only the brewer's nomination says which is which.
    temp_device_ids = [b.temp_device_id for b in ingesting_batches if b.temp_device_id]
    device_latest_temp = temp_service.latest_for_devices(temp_device_ids)
    for b in ingesting_batches:
        latest_g = batch_latest_g.get(b.id)
        latest_p = batch_latest_p.get(b.id)
        g_count = batch_g_counts.get(b.id, 0)
        p_count = batch_p_counts.get(b.id, 0)
        first_g = batch_first_g.get(b.id)
        first_p = batch_first_p.get(b.id)
        first_temp = batch_first_temp.get(b.id)

        day_count: Optional[int] = None
        if b.brew_date:
            day_count = (datetime.now(timezone.utc).date() - b.brew_date).days

        latest_temp = device_latest_temp.get(b.temp_device_id) if b.temp_device_id else None
        batch_prediction = batch_predictions.get(b.id)
        batch_preds = (
            [PredictionResponse.model_validate(batch_prediction)]
            if batch_prediction is not None else []
        )
        # battery/rssi/last_reading_at describe whichever device on this batch actually
        # reported most recently, not the gravity device specifically — a pressure-only
        # or temp-only batch reports normally instead of looking like it never checked in.
        candidates = [r for r in (latest_g, latest_p, latest_temp) if r is not None]
        freshest = max(candidates, key=lambda r: r.created_at) if candidates else None
        first_candidates = [r for r in (first_g, first_p, first_temp) if r is not None]
        first_measurement = (
            min(first_candidates, key=lambda r: r.created_at) if first_candidates else None
        )
        dashboard_batches.append(DashboardBatch(
            id=b.id,
            name=b.name,
            status=getattr(b, "status", None),
            brew_date=b.brew_date,
            day_count=day_count,
            og=b.og,
            fg=b.fg,
            first_gravity=first_g.gravity if first_g else None,
            current_gravity=latest_g.gravity if latest_g else None,
            current_pressure=latest_p.pressure if latest_p else None,
            current_temp=latest_temp.temperature if latest_temp else None,
            temp_device_id=b.temp_device_id,
            first_reading_at=first_measurement.created_at if first_measurement else None,
            battery=freshest.battery if freshest else None,
            rssi=freshest.rssi if freshest else None,
            last_reading_at=freshest.created_at if freshest else None,
            gravity_count=g_count,
            pressure_count=p_count,
            predictions=batch_preds,
        ))

    # --- taps ---
    dashboard_taps: List[DashboardTap] = []
    taps = tap_service.dashboard()
    tap_predictions = prediction_service.latest_for_owners(
        Prediction.tap_id, [t.id for t in taps]
    )
    for t in taps:
        tap_prediction = tap_predictions.get(t.id)
        tap_preds = (
            [PredictionResponse.model_validate(tap_prediction)]
            if tap_prediction is not None else []
        )
        dashboard_taps.append(DashboardTap(
            id=t.id,
            name=t.name,
            tap_number=t.tap_number,
            location=t.location,
            vessel_id=t.vessel_id,
            vessel_name=t.vessel_name,
            batch_name=t.batch_name,
            batch_id=t.batch_id,
            volume_remaining=t.volume_remaining,
            predictions=tap_preds,
        ))

    # --- vessels ---
    dashboard_vessels: List[DashboardVessel] = []
    vessels, _ = vessel_service.list_page(page=1, page_size=200)
    vessel_ids = [v.id for v in vessels]
    vessel_batch_names = batch_service.get_names_by_ids(
        [v.batch_id for v in vessels if v.batch_id]
    )
    vessel_predictions = prediction_service.latest_for_owners(
        Prediction.vessel_id, vessel_ids
    )
    vessel_temps = temp_service.latest_for_vessels(vessel_ids)
    vessel_pressures = pressure_service.latest_for_vessels(vessel_ids)
    for v in vessels:
        batch_name: Optional[str] = vessel_batch_names.get(v.batch_id) if v.batch_id else None
        vessel_prediction = vessel_predictions.get(v.id)
        vessel_preds = (
            [PredictionResponse.model_validate(vessel_prediction)]
            if vessel_prediction is not None else []
        )
        latest_temp = vessel_temps.get(v.id)
        latest_pressure = vessel_pressures.get(v.id)
        dashboard_vessels.append(DashboardVessel(
            id=v.id,
            name=v.name,
            vessel_type=v.vessel_type,
            status=v.status,
            tap_id=v.tap_id,
            batch_id=v.batch_id,
            batch_name=batch_name,
            total_volume=v.total_volume,
            volume_remaining=v.volume_remaining,
            fill_date=getattr(v, "fill_date", None),
            current_temp=latest_temp.temperature if latest_temp else None,
            current_pressure=latest_pressure.pressure if latest_pressure else None,
            predictions=vessel_preds,
        ))


    # Collect batch IDs that are assigned to taps
    taps_batch_ids = {t.batch_id for t in dashboard_taps if t.batch_id}

    # --- ready batches (packaged with conditioning complete, or assigned to taps) ---
    today = datetime.now(timezone.utc).date()
    ready_batches: List[DashboardReadyItem] = []
    for b in batch_service.list():
        ready_date: Optional[Any] = None
        # Check if batch is packaged with conditioning complete
        if getattr(b, "status", None) == "packaged":
            package_date = getattr(b, "package_date", None)
            conditioning_days = getattr(b, "conditioning_days", None)
            if package_date and conditioning_days:
                ready_date = package_date + timedelta(days=conditioning_days)
        # Also include batches assigned to taps (ready to pour)
        if not ready_date and b.id in taps_batch_ids:
            ready_date = today
        if ready_date and ready_date <= today:
            ready_batches.append(DashboardReadyItem(
                id=b.id,
                name=b.name,
                kind="batch",
                ready_date=ready_date,
            ))

    # --- ready vessels (filled, conditioning complete, or assigned to taps) ---
    taps_vessel_ids = {t.vessel_id for t in dashboard_taps if t.vessel_id}
    ready_vessels: List[DashboardReadyItem] = []
    for v in vessel_service.list_active():
        ready_date: Optional[Any] = None
        # Check if vessel is filled with conditioning complete
        if v.status == "filled":
            fill_date = getattr(v, "fill_date", None)
            conditioning_days = getattr(v, "conditioning_days", None)
            if fill_date and conditioning_days:
                ready_date = fill_date + timedelta(days=conditioning_days)
        # Also include vessels assigned to taps (ready to pour)
        if not ready_date and v.id in taps_vessel_ids:
            ready_date = today
        if ready_date and ready_date <= today:
            ready_vessels.append(DashboardReadyItem(
                id=v.id,
                name=v.name,
                kind="vessel",
                ready_date=ready_date,
            ))

    return DashboardResponse(
        devices=dashboard_devices,
        batches=dashboard_batches,
        taps=dashboard_taps,
        vessels=dashboard_vessels,
        ready_batches=ready_batches,
        ready_vessels=ready_vessels,
    )
