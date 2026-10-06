# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Background job scheduler for BrewGraph."""
import logging
from datetime import datetime
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from core.cache import acquire_lock
from core.config import get_settings
from core.log import (LogLevel, ingestion_log_purge,
                      system_log_purge, system_log_scheduler)
from oss.jobs.chamber_reminder import task_chamber_step_reminder
from oss.jobs.gravity_forward import (task_drain_gravity_forward_queue,
                                      task_reclaim_stale_gravity_forwards)
from oss.jobs.pour_forward import (task_drain_pour_forward_queue,
                                   task_reclaim_stale_pour_forwards)
from oss.jobs.predictions import task_update_predictions
from oss.jobs.pressure_forward import (task_drain_pressure_forward_queue,
                                       task_reclaim_stale_pressure_forwards)
from oss.jobs.retention_purge import soft_delete_purge
from oss.jobs.tap_reminder import task_tap_line_reminder
from oss.jobs.temp_forward import (task_drain_temp_forward_queue,
                                   task_reclaim_stale_temp_forwards)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_singleton_job(
    job: Callable[[], Awaitable[None]], lock_ttl: int,
) -> None:
    """Run one scheduled task once across replicas when Redis is available."""
    name = job.__name__
    if not acquire_lock(f"scheduler:{name}", lock_ttl):
        logger.info("%s skipped; another scheduler replica owns this interval", name)
        return
    await job()


def _add_interval_job(job: Callable[[], Awaitable[None]], **interval) -> None:
    """Register one named, replica-safe interval job in the local scheduler."""
    cadence_seconds = sum(
        amount * {"seconds": 1, "minutes": 60, "hours": 3600}[unit]
        for unit, amount in interval.items()
    )
    scheduler.add_job(
        _run_singleton_job,
        "interval",
        # Locks intentionally expire just before the next scheduled turn.  A
        # crash therefore costs at most one interval, while replicas that fire
        # at roughly the same time still have one unambiguous owner.
        args=(job, max(1, cadence_seconds - 1)),
        id=job.__name__,
        name=job.__name__,
        replace_existing=True,
        max_instances=1,
        **interval,
    )


def scheduler_shutdown() -> None:
    """Gracefully shutdown the background job scheduler."""
    logger.info("Shutting down scheduler")
    scheduler.shutdown()


async def task_check_database() -> None:
    """Check database health and purge old log records."""
    logger.info("task_check_database running at %s", datetime.now())
    system_log_purge(days=90)
    ingestion_log_purge(days=120)
    system_log_scheduler(
        "Database maintenance completed: old logs purged",
        level=LogLevel.INFO,
    )


async def task_soft_delete_purge() -> None:
    """Daily hard-delete of soft-deleted rows past their grace period. Runs on its own
    24h interval, separate from task_check_database's 6h log maintenance,
    because this one is destructive and unrecoverable (no export) and its
    cadence is a deliberate product decision, not incidental to log cleanup.
    Grace period: Settings.soft_delete_purge_days (see core.log.soft_delete_purge).
    """
    logger.info("task_soft_delete_purge running at %s", datetime.now())
    soft_delete_purge()
    system_log_scheduler("Soft-delete purge completed", level=LogLevel.INFO)


def scheduler_setup(application: FastAPI) -> None:  # pylint: disable=unused-argument
    """Initialize and configure the background job scheduler."""
    logger.info("Setting up scheduler")

    if get_settings().scheduler_enabled:
        _add_interval_job(task_check_database, hours=6)
        _add_interval_job(task_soft_delete_purge, hours=24)
        _add_interval_job(task_update_predictions, minutes=10)
        _add_interval_job(task_drain_gravity_forward_queue, seconds=30)
        _add_interval_job(task_reclaim_stale_gravity_forwards, seconds=60)
        _add_interval_job(task_drain_pressure_forward_queue, seconds=30)
        _add_interval_job(task_reclaim_stale_pressure_forwards, seconds=60)
        _add_interval_job(task_drain_pour_forward_queue, seconds=30)
        _add_interval_job(task_reclaim_stale_pour_forwards, seconds=60)
        _add_interval_job(task_drain_temp_forward_queue, seconds=30)
        _add_interval_job(task_reclaim_stale_temp_forwards, seconds=60)
        _add_interval_job(task_chamber_step_reminder, hours=2)
        _add_interval_job(task_tap_line_reminder, hours=24)
    else:
        logger.warning("Scheduler disabled in configuration")

    scheduler.start()
