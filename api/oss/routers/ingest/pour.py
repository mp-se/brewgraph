# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Pour ingestion — KegMon pour events."""
import logging

from fastapi.responses import Response
from starlette.exceptions import HTTPException

from core.cache import set_key_if_absent
from core.enums import IngestionErrorReason
from core.events import notify_clients
from oss.extensions.tenant import DEFAULT_TENANT_ID
from oss.jobs.pour_forward import enqueue_forward
from oss.services.ingestion import NoActiveVesselError, UnstorableValueError, kegmon_temperature

from ._shared import IngestContext, _check_device_request_quota, log_dropped_fields

logger = logging.getLogger(__name__)

_DROPPED_LOG_SECONDS = 15 * 60

# Kegmon's own poll interval is undocumented; ~5 minutes is used as the basis here,
# the only documented comparable polling cadence for a device in this project.
# Deliberately NOT derived from pour frequency — pours are sporadic (Kegmon posts on pour
# detection, not a timer), so sizing an offline threshold against them would
# mark every quiet-but-healthy tap offline. Not yet wired into a health computation —
# there is no Kegmon-aware status_for_all yet.
KEGMON_POLL_INTERVAL_SECONDS = 300
KEGMON_OFFLINE_THRESHOLD_SECONDS = 2 * KEGMON_POLL_INTERVAL_SECONDS


def _log_dropped_temperature(payload: dict, tap, ctx: IngestContext) -> None:
    """Log an unusable temperature (field and cause, never the value), once per 15 minutes."""
    _, cause = kegmon_temperature(payload)
    if cause is None:
        return
    if set_key_if_absent(f"ingest:dropped_temperature:{tap.id}", "1", ttl=_DROPPED_LOG_SECONDS):
        ctx.ingestion_svc.log_ingestion_error(
            ctx.client_ip, "kegmon", IngestionErrorReason.PARSE_ERROR,
            f"temperature: {cause}; field dropped",
        )


def _write_pour(payload: dict, tap, ctx: IngestContext):
    """Store the event, answering a value that cannot be stored; no vessel propagates."""
    try:
        return ctx.ingestion_svc.write_pour(tap, payload)
    except UnstorableValueError as exc:
        ctx.reject_unstorable("kegmon", exc, tap)
        return None  # not reached: reject_unstorable always raises
    except NoActiveVesselError:
        raise
    except ValueError as exc:
        ctx.ingestion_svc.log_ingestion_error(
            ctx.client_ip, "kegmon", IngestionErrorReason.PARSE_ERROR,
            str(exc),
        )
        logger.error("write_pour failed: %s", exc)
        raise HTTPException(status_code=409, detail="Conflict processing pour event") from exc


async def _process_pour(payload: dict, ctx: IngestContext) -> Response:
    """Core KegMon pour processing logic."""
    token = payload.get("token") or None
    _check_device_request_quota(token)

    tap = ctx.ingestion_svc.resolve_tap(token)
    if tap is None:
        ctx.ingestion_svc.log_ingestion_error(
            ctx.client_ip, "kegmon", IngestionErrorReason.UNKNOWN_TOKEN,
            "Token not found — tap not registered",
        )
        raise HTTPException(status_code=401, detail="Tap not registered")

    ctx.ingestion_svc.stamp_tap_last_seen(tap)
    log_dropped_fields(ctx, "kegmon", tap, payload.pop("dropped_fields", []))
    try:
        with ctx.throttle_budget(tap.id, ctx.auth.ingest_interval_seconds):
            pour = _write_pour(payload, tap, ctx)
    except NoActiveVesselError:
        # A tap with nothing on it has nothing to update: not an error, not logged.
        return Response(content="", status_code=200)

    _log_dropped_temperature(payload, tap, ctx)

    # We need to notify that vessel has been updated since that contains a new volume
    ctx.background_tasks.add_task(notify_clients, "vessel", "update",
                                   pour.vessel_id if pour is not None else None,
                                   DEFAULT_TENANT_ID, source="pour")
    ctx.background_tasks.add_task(enqueue_forward, tap.id, DEFAULT_TENANT_ID)
    return Response(content="", status_code=200)
