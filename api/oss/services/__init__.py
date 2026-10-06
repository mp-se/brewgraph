# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Service layer dependency providers."""
from fastapi import Depends
from sqlalchemy.orm import Session

from core.db import get_session
from oss.services.batch import BatchService
from oss.services.batch_dry_hop import BatchDryHopService
from oss.services.batch_note import BatchNoteService
from oss.services.device import DeviceService
from oss.services.fermentation_step import FermentationStepService
from oss.services.gravity import GravityService
from oss.services.integration import IntegrationService
from oss.services.platform import (IngestionLogService, SystemLogService,
                                    TenantSettingsService)
from oss.services.pour_event import PourEventService
from oss.services.prediction import PredictionService
from oss.services.pressure import PressureService
from oss.services.storage_vessel import StorageVesselService
from oss.services.tap import TapService
from oss.services.temp_reading import TempService


def get_device_service(db_session: Session = Depends(get_session)) -> DeviceService:
    """Provide DeviceService dependency for endpoints."""
    return DeviceService(db_session)


def get_batch_service(db_session: Session = Depends(get_session)) -> BatchService:
    """Provide BatchService dependency for endpoints."""
    return BatchService(db_session)


def get_gravity_service(db_session: Session = Depends(get_session)) -> GravityService:
    """Provide GravityService dependency for endpoints."""
    return GravityService(db_session)


def get_pressure_service(db_session: Session = Depends(get_session)) -> PressureService:
    """Provide PressureService dependency for endpoints."""
    return PressureService(db_session)


def get_settings_service(db_session: Session = Depends(get_session)) -> TenantSettingsService:
    """Provide TenantSettingsService dependency for endpoints."""
    return TenantSettingsService(db_session)


def get_systemlog_service(db_session: Session = Depends(get_session)) -> SystemLogService:
    """Provide SystemLogService dependency for endpoints."""
    return SystemLogService(db_session)


def get_ingestionlog_service(
    db_session: Session = Depends(get_session),
) -> IngestionLogService:
    """Provide IngestionLogService dependency for endpoints."""
    return IngestionLogService(db_session)


def get_prediction_service(
    db_session: Session = Depends(get_session),
) -> PredictionService:
    """Provide PredictionService dependency for endpoints."""
    return PredictionService(db_session)


def get_tap_service(db_session: Session = Depends(get_session)) -> TapService:
    """Provide TapService dependency for endpoints."""
    return TapService(db_session)


def get_vessel_service(db_session: Session = Depends(get_session)) -> StorageVesselService:
    """Provide StorageVesselService dependency for endpoints."""
    return StorageVesselService(db_session)


def get_pour_service(db_session: Session = Depends(get_session)) -> PourEventService:
    """Provide PourEventService dependency for endpoints."""
    return PourEventService(db_session)


def get_fermentation_step_service(
    db_session: Session = Depends(get_session),
) -> FermentationStepService:
    """Provide FermentationStepService dependency for endpoints."""
    return FermentationStepService(db_session)


def get_batch_note_service(db_session: Session = Depends(get_session)) -> BatchNoteService:
    """Provide BatchNoteService dependency for endpoints."""
    return BatchNoteService(db_session)


def get_dry_hop_service(db_session: Session = Depends(get_session)) -> BatchDryHopService:
    """Provide BatchDryHopService dependency for endpoints."""
    return BatchDryHopService(db_session)


def get_temp_service(db_session: Session = Depends(get_session)) -> TempService:
    """Provide TempService dependency for endpoints."""
    return TempService(db_session)


def get_integration_service(db_session: Session = Depends(get_session)) -> IntegrationService:
    """Provide IntegrationService dependency for endpoints."""
    return IntegrationService(db_session)


__all__ = (
    "get_device_service",
    "get_batch_service",
    "get_gravity_service",
    "get_pressure_service",
    "get_settings_service",
    "get_systemlog_service",
    "get_ingestionlog_service",
    "get_prediction_service",
    "DeviceService",
    "BatchService",
    "GravityService",
    "PressureService",
    "TenantSettingsService",
    "SystemLogService",
    "IngestionLogService",
    "PredictionService",
    "TapService",
    "get_tap_service",
    "StorageVesselService",
    "get_vessel_service",
    "PourEventService",
    "get_pour_service",
    "FermentationStepService",
    "get_fermentation_step_service",
    "BatchDryHopService",
    "get_dry_hop_service",
    "BatchNoteService",
    "get_batch_note_service",
    "TempService",
    "get_temp_service",
    "IntegrationService",
    "get_integration_service",
)
