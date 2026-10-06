# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Integration (account-level forwarding target) API endpoints."""
import logging
import uuid
from typing import Any, List

from fastapi import Depends
from fastapi.routing import APIRouter
from starlette.exceptions import HTTPException

import oss.schemas.integration  # noqa: F401,W0611 — side-effect: triggers self-registration  # pylint: disable=unused-import
from core.openapi_tags import INTEGRATIONS
from core.schemas.errors import NOT_FOUND_RESPONSES, ErrorResponse
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.schemas.registry import get as _s
from oss.services import get_integration_service
from oss.services.integration import IntegrationService

IntegrationCreate = _s("IntegrationCreate")
IntegrationUpdate = _s("IntegrationUpdate")
IntegrationResponse = _s("IntegrationResponse")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/integrations", dependencies=[Depends(api_key_auth)])


@router.get(
    "",
    tags=[INTEGRATIONS],
    response_model=List[IntegrationResponse],
    dependencies=[Depends(api_key_auth)],
)
async def list_integrations(
    integration_service: IntegrationService = Depends(get_integration_service),
) -> Any:
    """List every forwarding target configured for the account, including disabled ones."""
    logger.info("Endpoint GET /integrations/")
    return integration_service.list()


@router.post(
    "",
    tags=[INTEGRATIONS],
    response_model=IntegrationResponse,
    status_code=201,
    dependencies=[Depends(api_key_auth)],
)
async def create_integration(
    body: IntegrationCreate,
    integration_service: IntegrationService = Depends(get_integration_service),
) -> Any:
    """Create a new forwarding target."""
    logger.info("Endpoint POST /integrations/")
    return integration_service.create(body)


@router.patch(
    "/{integration_id}",
    tags=[INTEGRATIONS],
    response_model=IntegrationResponse,
    responses=NOT_FOUND_RESPONSES,
    dependencies=[Depends(api_key_auth)],
)
async def update_integration(
    integration_id: uuid.UUID,
    body: IntegrationUpdate,
    integration_service: IntegrationService = Depends(get_integration_service),
) -> Any:
    """Partial update — name, enabled, and/or config. `measurement` and `type` are immutable."""
    logger.info("Endpoint PATCH /integrations/%s", integration_id)
    updated = integration_service.update(integration_id, body)
    if updated is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    return updated


@router.post(
    "/{integration_id}/test",
    tags=[INTEGRATIONS],
    responses={404: {"model": ErrorResponse, "description": "Integration not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def test_integration(
    integration_id: uuid.UUID,
    integration_service: IntegrationService = Depends(get_integration_service),
) -> Any:
    """Send a fixed test reading without changing the target's auto-disable state."""
    result = await integration_service.test(integration_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    return result


@router.delete(
    "/{integration_id}",
    tags=[INTEGRATIONS],
    status_code=204,
    responses={404: {"model": ErrorResponse, "description": "Integration not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def delete_integration(
    integration_id: uuid.UUID,
    integration_service: IntegrationService = Depends(get_integration_service),
) -> None:
    """Remove one forwarding target. Siblings of the same type are unaffected."""
    logger.info("Endpoint DELETE /integrations/%s", integration_id)
    if not integration_service.delete(integration_id):
        raise HTTPException(status_code=404, detail="Integration not found")
