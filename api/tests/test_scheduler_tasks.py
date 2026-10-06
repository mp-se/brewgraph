# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/jobs/scheduler.py — task functions and scheduler_setup."""
from unittest.mock import MagicMock, patch

import pytest

from oss.jobs.scheduler import (_run_singleton_job, scheduler_setup,
                                 task_check_database, task_soft_delete_purge)

# ---------------------------------------------------------------------------
# task_check_database
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_task_check_database_runs():
    """task_check_database calls the two log-purge functions (soft-delete
    purge moved to its own daily job, task_soft_delete_purge, below)."""
    with patch("oss.jobs.scheduler.system_log_purge") as p1, \
         patch("oss.jobs.scheduler.ingestion_log_purge") as p2, \
         patch("oss.jobs.scheduler.system_log_scheduler"):
        await task_check_database()
    p1.assert_called_once_with(days=90)
    p2.assert_called_once_with(days=120)


@pytest.mark.asyncio
async def test_task_soft_delete_purge_runs():
    """task_soft_delete_purge calls soft_delete_purge with no explicit days
    (it uses the configured Settings.soft_delete_purge_days default)."""
    with patch("oss.jobs.scheduler.soft_delete_purge") as p1, \
         patch("oss.jobs.scheduler.system_log_scheduler"):
        await task_soft_delete_purge()
    p1.assert_called_once_with()


@pytest.mark.asyncio
async def test_singleton_job_skips_when_another_replica_holds_lock():
    """A second scheduler process must not execute the same interval job."""
    ran = []

    async def job():
        ran.append(True)

    with patch("oss.jobs.scheduler.acquire_lock", return_value=False) as lock:
        await _run_singleton_job(job, 59)

    assert not ran
    lock.assert_called_once_with("scheduler:job", 59)


@pytest.mark.asyncio
async def test_singleton_job_runs_when_it_claims_lock():
    """The replica that wins the Redis lock executes the task normally."""
    ran = []

    async def job():
        ran.append(True)

    with patch("oss.jobs.scheduler.acquire_lock", return_value=True) as lock:
        await _run_singleton_job(job, 59)

    assert ran == [True]
    lock.assert_called_once_with("scheduler:job", 59)


# ---------------------------------------------------------------------------
# scheduler_setup
# ---------------------------------------------------------------------------

def test_scheduler_setup_disabled_does_not_add_jobs():
    """No jobs are added when scheduler_enabled is False, but scheduler still starts."""
    with patch("oss.jobs.scheduler.get_settings") as mock_cfg, \
         patch("oss.jobs.scheduler.scheduler") as mock_sched:
        mock_cfg.return_value = MagicMock(scheduler_enabled=False)
        scheduler_setup(MagicMock())
    mock_sched.add_job.assert_not_called()
    mock_sched.start.assert_called_once()


def test_scheduler_setup_enabled_adds_all_jobs():
    """All 13 scheduled jobs are registered when scheduler_enabled is True.

    task_forward_gravity's old single 15-minute poll was replaced by a
    two-job pair (drain + reclaim-sweep) built on a reliable hashed Redis
    queue design — see oss/jobs/gravity_forward.py. Generalized to three more
    measurement-forwarding job pairs (pressure/pour/temp), each mirroring
    gravity's own drain+reclaim shape.
    """
    with patch("oss.jobs.scheduler.get_settings") as mock_cfg, \
         patch("oss.jobs.scheduler.scheduler") as mock_sched:
        mock_cfg.return_value = MagicMock(scheduler_enabled=True)
        scheduler_setup(MagicMock())
    assert mock_sched.add_job.call_count == 13
    mock_sched.start.assert_called_once()
    assert {
        call.kwargs["id"] for call in mock_sched.add_job.call_args_list
    } == {
        "task_check_database",
        "task_soft_delete_purge",
        "task_update_predictions",
        "task_drain_gravity_forward_queue",
        "task_reclaim_stale_gravity_forwards",
        "task_drain_pressure_forward_queue",
        "task_reclaim_stale_pressure_forwards",
        "task_drain_pour_forward_queue",
        "task_reclaim_stale_pour_forwards",
        "task_drain_temp_forward_queue",
        "task_reclaim_stale_temp_forwards",
        "task_chamber_step_reminder",
        "task_tap_line_reminder",
    }
