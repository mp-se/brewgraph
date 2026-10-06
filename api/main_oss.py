# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""BrewGraph app factory — single-user, API-key auth, SQLite or PostgreSQL."""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware

# Register models first — all core services resolve models at import time.
# oss/models/__init__.py is the single place the module list lives — migrations/env.py
# imports the same modules rather than keeping its own copy.
import oss.models as _oss_models  # noqa: F401,E402
import oss.models.platform as _platform  # noqa: F401,E402
from core.cache import write_key
from core.config import get_settings
from core.db import create_session, create_tables, engine
from core.enums import (GravityFormat, PressureFormat, TemperatureFormat,
                        VolumeFormat)
from core.errors import ERROR_CODES
from core.log import LogLevel, system_log
from core.models import Base
from core.openapi_tags import OPENAPI_TAGS
from core.schema_drift import warn_on_drift
from core.schemas.errors import ERROR_RESPONSES
from oss.routers import batches as batches_router
from oss.routers import batch_readings as batch_readings_router
from oss.routers import batch_steps as batch_steps_router
from oss.routers import brewfather as brewfather_router
from oss.routers import dashboard as dashboard_router
from oss.routers import devices as devices_router
from oss.routers import events as events_router
from oss.routers import ingest as ingest_router
from oss.routers import integrations as integrations_router
from oss.routers import predictions as predictions_router
from oss.routers import public_display as public_display_router
from oss.routers import system as system_router
from oss.routers import taps as taps_router
from oss.routers import tenant as tenant_router
from oss.routers import vessel_pours as vessel_pours_router
from oss.routers import vessel_readings as vessel_readings_router
from oss.routers import vessels as vessels_router
from oss.routers import yeast_strains as yeast_strains_router
from oss.jobs._forward_common import close_http_client
from oss.jobs.scheduler import scheduler_setup, scheduler_shutdown
from oss.schemas.platform import HealthResponse
from oss.schemas.platform import TenantSettingsCreate
from oss.services.platform import TenantSettingsService


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Manage startup and shutdown tasks for the FastAPI application."""
    # startup
    create_tables()
    _warn_on_schema_drift()
    _ensure_app_settings()
    scheduler_setup(fastapi_app)
    write_key("brewgraph", get_settings().version, ttl=None)
    system_log("startup_complete", "BrewGraph started", level=LogLevel.INFO)
    yield
    # shutdown
    scheduler_shutdown()
    await close_http_client()


def _warn_on_schema_drift():
    """Report a database that predates an in-place migration edit, and carry on."""
    drift = warn_on_drift(engine, Base.metadata)
    if drift:
        system_log(
            "schema_drift",
            f"Database schema does not match the models ({len(drift)}): "
            + "; ".join(sorted(drift)),
            level=LogLevel.ERROR,
        )


def _ensure_app_settings():
    """Create default TenantSettings row if none exists."""
    db = create_session()
    try:
        svc = TenantSettingsService(db)
        if len(svc.list()) == 0:
            svc.create(TenantSettingsCreate(
                temperature_format=TemperatureFormat.CELSIUS,
                pressure_format=PressureFormat.KPA,
                gravity_format=GravityFormat.SG,
                volume_format=VolumeFormat.METRIC,
            ))
    except Exception as e:  # pylint: disable=broad-except
        db.rollback()
        system_log("startup_warning", f"Failed to ensure app settings: {e}", level=LogLevel.WARNING)
    finally:
        db.remove()



settings = get_settings()
app = FastAPI(
    title="BrewGraph API",
    description="Device management, gravity collection and recipe integration.",
    version=settings.version,
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
)


app.add_middleware(GZipMiddleware, minimum_size=1024)
# allow_origins=["*"] is intentional: IoT devices (iSpindel, GravityMon, etc.)
# POST to the ingest endpoints directly from their own firmware without a
# browser origin. allow_credentials=False means cookies are never included,
# so a wildcard origin cannot be used for cross-site cookie attacks.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Attach a unique X-Request-ID to every request/response for log correlation.

    This is the sole source of `request.state.request_id`, which every error handler below
    reads to populate the envelope's `requestId`. `@app.middleware("http")` registers this
    exactly like `add_middleware`, appended after `GZipMiddleware` and `CORSMiddleware` above —
    so it is the outermost middleware (last registered wraps outermost) and sets
    `request.state.request_id` before any other middleware or route runs. An error raised
    earlier in the stack than this middleware would otherwise reach its handler with no
    request ID to report.
    """
    # Always server-generated. A caller-supplied X-Request-ID is deliberately
    # ignored: docs/architecture.md defines request_id as "UUID generated per
    # request by middleware — unique across every API call", and honouring the
    # header would let a client reuse one ID across calls (collapsing unrelated
    # requests in the logs) or forge another request's ID.
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(ingest_router.router, responses=ERROR_RESPONSES)
app.include_router(public_display_router.router, responses=ERROR_RESPONSES)
app.include_router(tenant_router.router, responses=ERROR_RESPONSES)
app.include_router(devices_router.router, responses=ERROR_RESPONSES)
app.include_router(batches_router.router, responses=ERROR_RESPONSES)
app.include_router(batch_readings_router.router, responses=ERROR_RESPONSES)
app.include_router(batch_steps_router.router, responses=ERROR_RESPONSES)
app.include_router(predictions_router.router, responses=ERROR_RESPONSES)
app.include_router(dashboard_router.router, responses=ERROR_RESPONSES)
app.include_router(brewfather_router.router, responses=ERROR_RESPONSES)
app.include_router(system_router.public_router, responses=ERROR_RESPONSES)
app.include_router(system_router.router, responses=ERROR_RESPONSES)
app.include_router(events_router.router, responses=ERROR_RESPONSES)
app.include_router(taps_router.router, responses=ERROR_RESPONSES)
app.include_router(vessels_router.router, responses=ERROR_RESPONSES)
app.include_router(vessel_pours_router.router, responses=ERROR_RESPONSES)
app.include_router(vessel_readings_router.router, responses=ERROR_RESPONSES)
app.include_router(yeast_strains_router.router, responses=ERROR_RESPONSES)
app.include_router(integrations_router.router, responses=ERROR_RESPONSES)

_validation_logger = logging.getLogger(__name__)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors — log details server-side, return the normative envelope.

    Emits `{error, message, requestId}` — a machine-readable code, a human-readable summary, and
    the ID that ties this response to the full server-side log entry. The full per-field
    validation detail is logged server-side rather than returned, matching the same rule 500s
    follow: developer-authored text is fine to pass through verbatim, but a raw Pydantic error
    list is internal shape, not a message.
    """
    request_id = getattr(request.state, "request_id", None)
    _validation_logger.error(
        "Request validation error (requestId=%s): %s", request_id, exc
    )
    return JSONResponse(
        {
            "error": "validation_error",
            "message": "Invalid request",
            "requestId": request_id,
        },
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Wrap every `HTTPException` (and `ApiError`) raised anywhere in the app in the envelope.

    Deliberately handles `starlette.exceptions.HTTPException`, not `fastapi.HTTPException` —
    the former is the base FastAPI's own exception subclasses, so this single handler also
    catches raises from FastAPI internals and from middleware that only knows about Starlette
    (e.g. `oss/routers/batches.py` imports the Starlette exception directly). `error` comes from
    the exception's own code when it is an `ApiError`; otherwise from `ERROR_CODES` by status;
    otherwise a safe fallback so an unmapped status still emits a coded envelope. `headers` is
    passed through unchanged so `Retry-After` on 429s survives (see `retry_after_headers` in
    `core/middleware/auth.py`).
    """
    error = getattr(exc, "error", None) or ERROR_CODES.get(exc.status_code, "error")
    message = exc.detail if isinstance(exc.detail, str) else "An error occurred"
    request_id = getattr(request.state, "request_id", None)
    # "All errors must be logged" (docs/architecture.md §Error responses) — that
    # includes 4xx. 5xx keeps ERROR; expected client-side failures log at WARNING
    # so they do not drown real faults.
    _validation_logger.log(
        logging.ERROR if exc.status_code >= 500 else logging.WARNING,
        "HTTP %s on %s %s (requestId=%s): %s",
        exc.status_code, request.method, request.url.path, request_id, message,
    )
    return JSONResponse(
        {
            "error": error,
            "message": message,
            "requestId": request_id,
        },
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch anything not already an `HTTPException`/`ApiError` and return a fixed 500 body.

    The one case where `message` is NOT the raise site's text verbatim — an unhandled
    exception's `str(exc)` can contain a stack-trace fragment, a query, or a file path, so the
    client only ever sees the fixed `"Internal server error"`. The real exception is logged
    here, server-side, against the same `requestId` the client was given, which is the only
    bridge from a user-visible error back to the full detail in the logs.
    """
    request_id = getattr(request.state, "request_id", None)
    _validation_logger.error(
        "Unhandled exception (requestId=%s): %s", request_id, exc, exc_info=exc
    )
    return JSONResponse(
        {
            "error": "internal_error",
            "message": "Internal server error",
            "requestId": request_id,
        },
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )



@app.get("/health", tags=["system"], response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
