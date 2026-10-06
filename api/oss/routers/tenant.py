# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tenant settings API endpoints (GET + PATCH /api/tenant/settings)."""
import logging
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.routing import APIRouter

from core.cache import delete_key
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.precision import DECIMALS
from oss.schemas.platform import TenantSettingsResponse, TenantSettingsUpdate
from oss.services import TenantSettingsService, get_settings_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tenant", tags=["tenant"], dependencies=[Depends(api_key_auth)])


def _get_settings(svc: TenantSettingsService) -> Any:
    """Return the single TenantSettings row, 404 if not yet initialised."""
    rows = svc.list()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="settings_not_found")
    return rows[0]


@router.get("/settings", response_model=TenantSettingsResponse)
def get_tenant_settings(svc: TenantSettingsService = Depends(get_settings_service)):
    """Return application-wide settings."""
    response = TenantSettingsResponse.model_validate(_get_settings(svc))
    return response.model_copy(update={"precision": dict(DECIMALS)})


@router.patch("/settings", response_model=TenantSettingsResponse)
def update_tenant_settings(
    body: TenantSettingsUpdate,
    svc: TenantSettingsService = Depends(get_settings_service),
):
    """Update application-wide settings. Only supplied fields are changed."""
    row = _get_settings(svc)
    updated = svc.update(row.id, body)
    # /d is deliberately long-lived because presentation changes rarely. Make
    # an authenticated settings update visible on the next display reload.
    delete_key("public_display:oss:context")
    logger.info("Tenant settings updated")
    response = TenantSettingsResponse.model_validate(updated)
    return response.model_copy(update={"precision": dict(DECIMALS)})
