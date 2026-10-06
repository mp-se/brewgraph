# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""System management API endpoints."""
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import Depends, HTTPException, Query
from fastapi.routing import APIRouter
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.cache import find_key, read_key, write_key
from core.config import get_settings
from core.db import get_session
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.jobs.retention_purge import soft_delete_purge
from oss.jobs.scheduler import scheduler
from oss.schemas._page import CursorPage, encode_cursor, parse_cursor
from oss.schemas.platform import (IngestionLogResponse, SchedulerJobStatus,
                                  SystemLogResponse)
from oss.services import (IngestionLogService, SystemLogService,
                          TenantSettingsService, get_ingestionlog_service,
                          get_settings_service, get_systemlog_service)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system", tags=["system"], dependencies=[Depends(api_key_auth)])
public_router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/self-test", dependencies=[Depends(api_key_auth)])
async def self_test(db: Session = Depends(get_session)) -> dict:
    """Perform system self-test checking database, redis, and scheduler connectivity.

    The BLE scanner posts every format to ingest, so device liveness and values live
    on the device itself — `Device.last_seen` for liveness, reading rows for values,
    both with history a cache mirror would not have — and this endpoint carries no
    `ble` array of cache keys.
    """
    logger.info("Endpoint GET /api/system/self_test/")

    db_ok = False
    try:
        svc = TenantSettingsService(db)
        svc.list()
        db_ok = True
    except SQLAlchemyError:
        pass

    redis_ok = False
    try:
        write_key("self_test", "testing", 60)
        val = read_key("self_test")
        if val and val.decode() == "testing":
            redis_ok = True
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    jobs = [job.name for job in scheduler.get_jobs()]

    log = []
    for key in find_key("log_*"):
        value = read_key(key)
        log.append({"name": key.decode() if isinstance(key, bytes) else key,
                     "value": value.decode() if value else None})

    return {
        "databaseConnection": db_ok,
        "redisConnection": redis_ok,
        "backgroundJobs": jobs,
        "log": log,
    }


@router.get(
    "/scheduler",
    response_model=List[SchedulerJobStatus],
    dependencies=[Depends(api_key_auth)],
)
async def get_scheduler_status() -> list:
    """Return name and seconds-until-next-run for each scheduled job."""
    logger.info("Endpoint GET /system/scheduler/")
    now = datetime.now(tz=timezone.utc)
    result = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        next_run_in = max(0, int((next_run - now).total_seconds())) if next_run else None
        result.append({"name": job.name, "nextRunIn": next_run_in})
    return result


@router.post("/purge-deleted", dependencies=[Depends(api_key_auth)])
async def purge_deleted() -> dict:
    """Hard-delete every currently soft-deleted row, right now, across all models.

    Same code path as the nightly `task_soft_delete_purge` job
    (`oss.jobs.retention_purge.soft_delete_purge`), just with the grace period
    collapsed to zero instead of `Settings.soft_delete_purge_days`. Exists for
    restore: `processBrewGraphRestore` soft-deletes every device, batch, tap and
    vessel before recreating them from the backup file, but a soft-deleted row
    still occupies its unique constraints (device chip_id/token, ...), so the
    recreate step conflicts unless those rows are actually gone, not just
    marked. This purges them immediately so restore can proceed.

    This is intentionally not scoped to what a given restore just deleted — it
    is a blanket "collapse the grace window to now" for every soft-deleted row
    in the database, restore-triggered or not. A batch deleted five minutes ago
    and still inside its normal recovery window is gone for good once this
    runs, same as everything else with `deleted_at` set.
    """
    logger.info("Endpoint POST /system/purge-deleted")
    soft_delete_purge(days=0)
    return {"status": "ok"}


@public_router.get("/health")
async def health() -> dict:
    """Quick liveness check."""
    logger.info("Endpoint GET /system/health")
    return {"status": "ok"}


@router.get("/info", dependencies=[Depends(api_key_auth)])
async def system_info(
    settings_svc: TenantSettingsService = Depends(get_settings_service),
) -> dict:
    """Return version and database status."""
    logger.info("Endpoint GET /system/info")
    cfg = get_settings()

    db_ok = False
    try:
        settings_svc.list()
        db_ok = True
    except SQLAlchemyError:
        db_ok = False

    return {
        "version": cfg.version,
        "appName": cfg.app_name,
        "databaseOk": db_ok,
    }


@router.get(
    "/logs",
    response_model=CursorPage[SystemLogResponse],
    dependencies=[Depends(api_key_auth)],
)
async def get_system_logs(
    limit: int = Query(50, ge=1, le=500),
    cursor: Optional[str] = Query(None),
    log_svc: SystemLogService = Depends(get_systemlog_service),
) -> Any:
    """Retrieve system logs, newest first (cursor-paginated)."""
    logger.info("Endpoint GET /system/logs limit=%d cursor=%s", limit, cursor)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    try:
        records, has_more = log_svc.list_cursor(limit=limit, cursor=cursor_dt)
    except SQLAlchemyError as e:
        logger.error("Database error retrieving system logs: %s", e)
        records, has_more = [], False
    items = [SystemLogResponse.model_validate(r) for r in records]
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.get(
    "/ingestion",
    response_model=CursorPage[IngestionLogResponse],
    dependencies=[Depends(api_key_auth)],
)
async def get_ingestion_log(
    limit: int = Query(50, ge=1, le=500),
    cursor: Optional[str] = Query(None),
    log_svc: IngestionLogService = Depends(get_ingestionlog_service),
) -> Any:
    """Retrieve ingestion error logs, newest first (cursor-paginated)."""
    logger.info("Endpoint GET /system/ingestion limit=%d cursor=%s", limit, cursor)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    try:
        records, has_more = log_svc.list_cursor(limit=limit, cursor=cursor_dt)
    except SQLAlchemyError as e:
        logger.error("Database error retrieving ingestion logs: %s", e)
        records, has_more = [], False
    items = [IngestionLogResponse.model_validate(r) for r in records]
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)
