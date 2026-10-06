# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tap-line cleaning reminder.

Kegerator tap lines need periodic cleaning regardless of pour volume. This app
has no dedicated notification/inbox model — system_log (surfaced in the System
Logs view) is the existing mechanism used for every other scheduler-driven alert
in this codebase (see task_check_database, task_chamber_step_reminder).
"""
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from core.db import create_session
from core.log import LogLevel, system_log_scheduler
from core.models.registry import resolve_model

logger = logging.getLogger(__name__)

Tap = resolve_model("Tap")

_TAP_LINE_INTERVAL_DAYS = 14


def _days_overdue(tap, now: datetime) -> int | None:
    """Days since last_cleaned_at (or created_at, when never cleaned), or None
    if the tap isn't yet overdue (or has neither timestamp set)."""
    last_cleaned = tap.last_cleaned_at or tap.created_at
    if last_cleaned is None:
        return None
    age_days = (now - last_cleaned).days
    return age_days if age_days >= _TAP_LINE_INTERVAL_DAYS else None


async def task_tap_line_reminder() -> None:
    """For every tap, if last_cleaned_at (or created_at, when never cleaned) is
    older than 14 days, log a reminder. Once per overdue tap per run, not once
    ever — dedup via a marker appended to the log message, checked against
    recent system_log entries would require a query surface system_log doesn't
    expose cleanly; instead this job runs at a day-granularity cadence (see
    scheduler_setup, hours=24) and relies on the operator noticing the
    (infrequent, at most one per tap per day) repeat entries rather than a hard
    dedup — acceptable for a single-user, log-based notification surface.
    Revisit if this proves noisy.
    """
    db = create_session()
    reminders = 0
    try:
        now = datetime.now(UTC)
        taps = db.scalars(select(Tap)).all()
        for tap in taps:
            days_overdue = _days_overdue(tap, now)
            if days_overdue is None:
                continue
            system_log_scheduler(
                f"Tap '{tap.name}': line hasn't been cleaned in {days_overdue} days"
                f" — consider cleaning it (~{_TAP_LINE_INTERVAL_DAYS}-day interval)",
                level=LogLevel.INFO,
            )
            reminders += 1
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("task_tap_line_reminder failed: %s", exc)
    finally:
        if reminders:
            logger.info("task_tap_line_reminder: %d reminder(s) logged", reminders)
        db.remove()
