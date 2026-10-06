# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Shared ingest-router infrastructure: DI, discovery, and the per-request context
passed into every use-case module's `_process_*` function.

Not itself a use-case: `_get_ingestion_service`/`IngestContext`/discovery are used by
every oss/routers/ingest/<usecase>.py module (gravity.py, pressure.py, chamber.py,
pour.py). None of those modules import back from the package's `__init__.py` — that
direction would be circular, since `__init__.py` imports each of them to register its
route(s) onto `router`. `_check_throttle`/`_throttle_budget` are the one exception:
they stay defined directly in `__init__.py` itself (not here) because
`tests/conftest.py`'s autouse fixture patches `oss.routers.ingest._check_throttle` by
that exact dotted path, which only works if the code that calls it lives in that same
module's namespace — see `IngestContext.throttle_budget` below for how a use-case
module still gets to use it without importing it.
"""
import hashlib
import os
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from fastapi import BackgroundTasks, Depends, Request
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from core.db import get_session
from core.middleware.auth import AuthContext, enforce_request_rate_ceiling
from core.models.registry import resolve_model
from oss.schemas.platform import IngestEndpointResponse
from oss.services import TenantSettingsService, get_settings_service
from oss.services.ingestion import IngestionService

TenantSettings = resolve_model("TenantSettings")  # type: ignore[assignment]

router = APIRouter(prefix="/api", tags=["ingest"])  # auth handled per-endpoint via ingest_auth

# Public URLs devices should be configured with. These are the short form the web
# proxy exposes; it rewrites /ingest/<device> to the canonical /api/ingest/<device>
# route this router actually serves.
_INGEST_ENDPOINTS = [
    {"device": "gravitymon", "path": "/ingest/gravitymon", "note": "token in body"},
    {"device": "ispindel", "path": "/ingest/ispindel", "note": "token in body"},
    {"device": "pressuremon", "path": "/ingest/pressuremon", "note": "token in body"},
    {"device": "kegmon", "path": "/ingest/kegmon", "note": "token in body"},
    {"device": "chamber", "path": "/ingest/chamber", "note": "token in body"},
    {
        "device": "dispatch",
        "path": "/ingest/dispatch",
        "note": "auto-detect from payload",
    },
]


@router.get("/ingest/endpoints", response_model=List[IngestEndpointResponse])
async def list_ingest_endpoints(request: Request) -> List[dict]:
    """Return all ingest endpoint URLs with their full public base URL.

    Base URL resolution order:
    1. PUBLIC_URL env var (set this in production behind a reverse proxy)
    2. Derived from the incoming request Host + scheme
       (requires X-Forwarded-Proto / X-Forwarded-Host from nginx)
    """
    base = (os.getenv("PUBLIC_URL") or f"{request.url.scheme}://{request.url.netloc}").rstrip("/")
    return [{"device": e["device"], "url": base + e["path"], "note": e["note"]}
            for e in _INGEST_ENDPOINTS]


def _get_ingestion_service(
    db: Session = Depends(get_session),
    settings_svc: TenantSettingsService = Depends(get_settings_service),
) -> IngestionService:
    settings_list = settings_svc.list()
    settings = settings_list[0] if settings_list else TenantSettings()
    return IngestionService(db, settings)


def _check_device_request_quota(token: str | None) -> None:
    """Hard per-device request-rate ceiling, independent of the per-device
    interval throttle in the package's `__init__.py`. Keyed by a SHA-256 hash of the
    full token — never the plaintext token or a short prefix, which would let two
    devices collide onto the same rate budget. This matches the existing
    token-hashing convention already used for stored token_hash comparisons (see
    oss/services/tap.py).
    """
    if not token:
        return
    key = f"ingest_rl_device:{hashlib.sha256(token.encode()).hexdigest()}"
    enforce_request_rate_ceiling(key)


@dataclass
class IngestContext:
    """Per-request dependencies shared by every ingest use-case's `_process_*` function.

    Bundles what each oss/routers/ingest/<usecase>.py module needs from the request
    (and the package's own `_throttle_budget`, built by `__init__.py` and passed in
    here) into one parameter, instead of each `_process_*` function repeating the
    same four-or-five-argument list.
    """
    client_ip: str
    background_tasks: BackgroundTasks
    ingestion_svc: IngestionService
    auth: Optional[AuthContext]
    throttle_budget: Callable[..., Any]
