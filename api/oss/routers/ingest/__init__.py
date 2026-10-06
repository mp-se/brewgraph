# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Public ingestion endpoints — no auth required.

Router assembly for the ingest package: cross-cutting throttle infra
(`_check_throttle`/`_throttle_budget`, kept here rather than in `_shared.py` — see
that module's docstring for why) plus every `@router.post(...)` endpoint, each a
thin request/response wrapper around its use case's `_process_*` function
(oss/routers/ingest/gravity.py, pressure.py, chamber.py, pour.py, dispatch.py).
"""
import logging
from contextlib import contextmanager
from json import JSONDecodeError
from typing import Any

from fastapi import BackgroundTasks, Depends, Request
from fastapi.responses import Response
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from core.cache import delete_key, set_key_if_absent
from core.enums import DeviceType
from core.middleware.auth import AuthContext, ingest_auth, retry_after_headers
from core.models.registry import resolve_model
from core.utils import get_client_ip
from oss.schemas.ingest import (
    ChamberIngestRequest,
    ChamberIngestResponse,
    GravityIngestRequest,
    IspindelIngestRequest,
    KegmonBeerRequest,
    KegmonBeerResponse,
    KegmonIngestRequest,
    PressureIngestRequest,
)
from oss.services.ingestion import IngestionService

from ._shared import IngestContext, _check_device_request_quota, _get_ingestion_service, router
from .chamber import _process_chamber
from .dispatch import _detect_device_type
from .gravity import _process_gravity
from .pour import _process_pour
from .pressure import _process_pressure

__all__ = ["router", "_check_device_request_quota"]

logger = logging.getLogger(__name__)


def _check_throttle(device_id, min_interval: int) -> None:
    """Raise HTTP 429 if the device has sent a request within min_interval seconds."""
    if min_interval <= 0:
        return
    key = f"ingest_throttle_{device_id}"
    if not set_key_if_absent(key, "1", ttl=min_interval):
        raise HTTPException(
            status_code=429,
            detail="Too many requests — throttle interval active",
            # Live TTL, not the nominal interval: a device throttled two seconds into
            # a five-minute window should be told 298, not 300.
            headers=retry_after_headers(key, fallback=min_interval),
        )


@contextmanager
def _throttle_budget(entity_id, min_interval: int):
    """Claim the per-device throttle budget, releasing it if the reading is rejected.

    The interval pays for an *accepted* reading, not for an attempt. Claiming it
    before the write is what stops two simultaneous requests both passing, so the
    claim stays where it is — but if the handler then rejects the reading (a
    conflicting pour, an unusable payload, a database error) nothing was stored,
    and serving out a full interval for it would lock a misconfigured device out
    of a window it never used. From the outside that is indistinguishable from a
    real rate limit.

    429 is excluded: the only 429 reachable here is the one ``_check_throttle``
    raises above, which happens before the ``try`` and so never releases a key it
    did not claim. The check is kept anyway so a future inner throttle cannot
    silently make a throttle undo itself.
    """
    _check_throttle(entity_id, min_interval)
    try:
        yield
    except HTTPException as exc:
        if exc.status_code != 429:
            delete_key(f"ingest_throttle_{entity_id}")
        raise
    except Exception:
        delete_key(f"ingest_throttle_{entity_id}")
        raise


@router.post("/ingest/kegmon", status_code=200, response_class=Response,
    responses={200: {"content": {"text/plain": {}}, "description": "Accepted; body is empty."}})
async def ingest_kegmon(
    request: Request,
    body: KegmonIngestRequest,
    background_tasks: BackgroundTasks,
    ingestion_svc: IngestionService = Depends(_get_ingestion_service),
    auth: AuthContext = Depends(ingest_auth),
) -> Response:
    """Ingest a KegMon pour event payload."""
    logger.info("Endpoint POST /ingest/kegmon")
    client_ip = get_client_ip(request)
    ctx = IngestContext(client_ip, background_tasks, ingestion_svc, auth, _throttle_budget)
    payload = body.model_dump(by_alias=True)
    payload["eventId"] = payload.get("eventId") or request.headers.get("Idempotency-Key")
    return await _process_pour(payload, ctx)


@router.post("/ingest/gravitymon", status_code=200, response_class=Response,
    responses={200: {"content": {"text/plain": {}}, "description": "Accepted; body is empty."}})
async def ingest_gravitymon(
    request: Request,
    body: GravityIngestRequest,
    background_tasks: BackgroundTasks,
    ingestion_svc: IngestionService = Depends(_get_ingestion_service),
    auth: AuthContext = Depends(ingest_auth),
) -> Response:
    """Ingest a GravityMon payload."""
    logger.info("Endpoint POST /ingest/gravitymon")
    client_ip = get_client_ip(request)
    ctx = IngestContext(client_ip, background_tasks, ingestion_svc, auth, _throttle_budget)
    return await _process_gravity(body.model_dump(by_alias=True), ctx, "gravitymon")


@router.post("/ingest/ispindel", status_code=200, response_class=Response,
    responses={200: {"content": {"text/plain": {}}, "description": "Accepted; body is empty."}})
async def ingest_ispindel(
    request: Request,
    body: IspindelIngestRequest,
    background_tasks: BackgroundTasks,
    ingestion_svc: IngestionService = Depends(_get_ingestion_service),
    auth: AuthContext = Depends(ingest_auth),
) -> Response:
    """Ingest an iSpindel payload."""
    logger.info("Endpoint POST /ingest/ispindel")
    client_ip = get_client_ip(request)
    ctx = IngestContext(client_ip, background_tasks, ingestion_svc, auth, _throttle_budget)
    return await _process_gravity(body.model_dump(by_alias=True), ctx, "ispindel")


@router.post("/ingest/pressuremon", status_code=200, response_class=Response,
    responses={200: {"content": {"text/plain": {}}, "description": "Accepted; body is empty."}})
async def ingest_pressuremon(
    request: Request,
    body: PressureIngestRequest,
    background_tasks: BackgroundTasks,
    ingestion_svc: IngestionService = Depends(_get_ingestion_service),
    auth: AuthContext = Depends(ingest_auth),
) -> Response:
    """Ingest a PressureMon payload."""
    logger.info("Endpoint POST /ingest/pressuremon")
    client_ip = get_client_ip(request)
    ctx = IngestContext(client_ip, background_tasks, ingestion_svc, auth, _throttle_budget)
    return await _process_pressure(body.model_dump(by_alias=True), ctx)


@router.post("/ingest/chamber", status_code=200, response_model=ChamberIngestResponse)
async def ingest_temp(
    request: Request,
    body: ChamberIngestRequest,
    background_tasks: BackgroundTasks,
    ingestion_svc: IngestionService = Depends(_get_ingestion_service),
    auth: AuthContext = Depends(ingest_auth),
) -> Response:
    """Ingest a generic temperature reading from a chamber controller.

    Body: { "token": "<device_token>", "beer_temperature": 18.5,
            "fridge_temperature": 4.2, "current_mode": "B" }

    `current_mode` is optional and informational — the returned setpoint is derived
    from batch state, never from what the controller reports about itself.

    Identity: a device token, or — failing that — `id` matched against a unique
    `chamber_controller`'s configured chip ID. That fallback is a trusted-LAN
    convenience for BLE bridging, not authentication. Either way it resolves
    vessel_id/batch_id from the device's association, so it works whether the device
    is paired to an active batch or to a vessel in storage with no batch.

    At least one of `token`/`id` and one of the two temperatures is required; the
    schema rejects a poll carrying neither.

    Delegates to `_process_chamber` — the same core logic `/ingest/dispatch` already
    uses for chamber payloads — rather than keeping a second, near-duplicate body.
    This also closes the throttle gap the two bodies used to disagree on: only
    `_process_chamber` called `_check_device_request_quota` before writing, so this
    dedicated route was reachable without it. See `chamber.py`'s module docstring.
    """
    logger.info("Endpoint POST /ingest/chamber")
    client_ip = get_client_ip(request)
    ctx = IngestContext(client_ip, background_tasks, ingestion_svc, auth, _throttle_budget)
    return await _process_chamber(body.model_dump(by_alias=True), ctx)


# ---------------------------------------------------------------------------
# dispatch, kegmon/beer
# ---------------------------------------------------------------------------

@router.post(
    "/ingest/dispatch",
    status_code=200,
    response_class=Response,
    responses={200: {"content": {"text/plain": {}}, "description": "Accepted; body is empty."}},
    openapi_extra={
        "requestBody": {
            "description": (
                "Device type is auto-detected from the payload fields — "
                "this is not a discriminated union, the server inspects "
                "which fields are present to pick one of the five shapes below."
            ),
            "content": {
                "application/json": {
                    "schema": {
                        "oneOf": [
                            {"$ref": "#/components/schemas/GravityIngestRequest"},
                            {"$ref": "#/components/schemas/IspindelIngestRequest"},
                            {"$ref": "#/components/schemas/PressureIngestRequest"},
                            {"$ref": "#/components/schemas/KegmonIngestRequest"},
                            {"$ref": "#/components/schemas/ChamberIngestRequest"},
                        ]
                    }
                }
            },
        }
    },
)
async def ingest_dispatch(
    request: Request,
    background_tasks: BackgroundTasks,
    ingestion_svc: IngestionService = Depends(_get_ingestion_service),
    auth: AuthContext = Depends(ingest_auth),
) -> Response:
    """Generic dispatch endpoint — auto-detects device type from payload fields."""
    logger.info("Endpoint POST /ingest/dispatch")
    client_ip = get_client_ip(request)
    try:
        raw = await request.json()
    except (JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Unable to parse request") from exc

    device_type = _detect_device_type(raw)
    _schema_map = {
        DeviceType.GRAVITYMON: GravityIngestRequest,
        DeviceType.ISPINDEL: IspindelIngestRequest,
        DeviceType.PRESSUREMON: PressureIngestRequest,
        DeviceType.KEGMON: KegmonIngestRequest,
        DeviceType.CHAMBER_CONTROLLER: ChamberIngestRequest,
    }
    schema_cls = _schema_map.get(device_type)
    if schema_cls is None:
        raise HTTPException(status_code=422, detail="Cannot detect device type from payload fields")
    try:
        payload = schema_cls.model_validate(raw).model_dump(by_alias=True)
    except ValidationError as exc:
        logger.debug("Payload validation failed for device_type=%s: %s", device_type, exc)
        raise HTTPException(status_code=422, detail="Invalid payload structure") from exc

    ctx = IngestContext(client_ip, background_tasks, ingestion_svc, auth, _throttle_budget)
    if device_type in (DeviceType.GRAVITYMON, DeviceType.ISPINDEL):
        return await _process_gravity(payload, ctx, device_type.value)
    if device_type == DeviceType.PRESSUREMON:
        return await _process_pressure(payload, ctx)
    if device_type == DeviceType.KEGMON:
        payload["eventId"] = payload.get("eventId") or request.headers.get("Idempotency-Key")
        return await _process_pour(payload, ctx)
    return await _process_chamber(payload, ctx)


@router.post("/ingest/kegmon/beer", status_code=200, response_model=KegmonBeerResponse,
             dependencies=[Depends(ingest_auth)])
async def ingest_kegmon_beer(
    body: KegmonBeerRequest,
    ingestion_svc: IngestionService = Depends(_get_ingestion_service),
) -> Any:
    """Return beer info for the tap identified by the request token.

    Kegmon fetches this for local display and caches it for offline use.

    Gated the same way every other public ingestion route already is: the
    per-IP `ingest_auth` ceiling at the route level, plus the per-token
    `_check_device_request_quota` hard ceiling used by `/ingest/kegmon`'s own
    `resolve_tap` call (`_process_pour`) — this is a read of the same tap
    lookup, not a write, so it reuses that gate rather than inventing a new
    shape. Both run before `resolve_tap`'s DB lookup, so a flood of invalid
    tokens is rejected without ever reaching the database.
    """
    logger.info("Endpoint POST /ingest/kegmon/beer")
    _check_device_request_quota(body.token)
    tap = ingestion_svc.resolve_tap(body.token)
    if tap is None:
        raise HTTPException(status_code=401, detail="Tap not registered")

    vessel = ingestion_svc.find_active_vessel_for_tap(tap)
    if vessel is None or vessel.batch_id is None:
        raise HTTPException(status_code=401, detail="No active vessel on tap")

    batch_model = resolve_model("Batch")
    batch = ingestion_svc._db.get(batch_model, vessel.batch_id)  # pylint: disable=protected-access
    if batch is None:
        raise HTTPException(status_code=401, detail="Batch not found")

    return {
        "name": vessel.name or batch.name,
        "abv": batch.abv,
        "ebc": batch.ebc,
        "ibu": batch.ibu,
    }
