# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Anonymous, deployment-exposed display documents for an OSS installation."""
import hashlib
import json
import logging
from collections.abc import Callable
from typing import Any

from fastapi import Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from core.cache import read_key, write_key
from core.db import get_session
from core.middleware.auth import enforce_request_rate_ceiling
from core.utils import get_client_ip
from oss.schemas.public_display import (PublicBottleItem, PublicDisplayContextResponse,
                                        PublicTapItem)
from oss.services.public_display import PublicDisplayService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["public display"])

# Displays re-read their context every 5 minutes; a longer TTL here (and in the
# browser's Cache-Control) would delay a settings change well beyond that.
_CACHE_TTLS = {"context": 300, "tap": 15, "bottle": 15}
_RATE_LIMIT = 60
_RATE_WINDOW_SECONDS = 60


def _rate_limit(request: Request, resource: str) -> None:
    """Apply an IP rate ceiling without storing a reversible client address."""
    client_digest = hashlib.sha256(get_client_ip(request).encode("utf-8")).hexdigest()
    enforce_request_rate_ceiling(
        f"public_display:rate:{resource}:{client_digest}",
        limit=_RATE_LIMIT,
        window_secs=_RATE_WINDOW_SECONDS,
        detail="Too many public display requests",
    )


def _cached_document(resource: str, build: Callable[[], Any]) -> JSONResponse:
    """Return a short-lived, sanitized document cache for one public resource."""
    cache_key = f"public_display:oss:{resource}"
    raw = read_key(cache_key)
    if raw is not None:
        try:
            payload = json.loads(raw)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("Ignoring malformed public-display cache entry for %s", resource)
        else:
            return _document_response(payload, _CACHE_TTLS[resource])

    payload = jsonable_encoder(build())
    # A Redis outage makes this a no-op; the public API remains available and
    # the request rate ceiling still has its bounded local fallback.
    write_key(cache_key, json.dumps(payload, separators=(",", ":")), ttl=_CACHE_TTLS[resource])
    return _document_response(payload, _CACHE_TTLS[resource])


def _document_response(payload: Any, max_age: int) -> JSONResponse:
    """Set only cache headers safe for anonymous, shared displays."""
    return JSONResponse(
        content=payload,
        headers={"Cache-Control": f"public, max-age={max_age}"},
    )


@router.get("/d", response_model=PublicDisplayContextResponse)
def get_public_display_context(
    request: Request,
    db_session: Session = Depends(get_session),
) -> Response:
    """Return the low-churn display presentation settings without authentication."""
    _rate_limit(request, "context")
    service = PublicDisplayService(db_session)
    return _cached_document(
        "context",
        lambda: service.display_context(service.oss_context()),
    )


@router.get("/t", response_model=list[PublicTapItem])
def get_public_taps(
    request: Request,
    db_session: Session = Depends(get_session),
) -> Response:
    """Return the complete OSS tap display as a top-level anonymous array."""
    _rate_limit(request, "tap")
    service = PublicDisplayService(db_session)
    return _cached_document("tap", lambda: service.build_public_tap_list(service.oss_context()))


@router.get("/b", response_model=list[PublicBottleItem])
def get_public_bottles(
    request: Request,
    db_session: Session = Depends(get_session),
) -> Response:
    """Return public packaged-bottle availability as a top-level anonymous array."""
    _rate_limit(request, "bottle")
    service = PublicDisplayService(db_session)
    return _cached_document(
        "bottle",
        lambda: service.build_public_bottle_list(service.oss_context()),
    )
