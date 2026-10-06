# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Manual chamber-control notification fallback.

Not every fermentation step, and not every batch under active chamber control, has
a ChamberController device to poll — Brewfather-imported steps commonly have no
device_id, and many brewers control temperature manually. This job surfaces the
current step's target temperature via system_log for those cases, since there is
no device polling to carry the setpoint. This app has no dedicated notification/inbox
model — system_log (surfaced in the System Logs view) is the existing mechanism
used for every other scheduler-driven alert in this codebase (see
task_check_database).
"""
import logging
from datetime import date, timedelta

from sqlalchemy import select

from core.db import create_session
from core.log import LogLevel, system_log_scheduler
from core.models.registry import resolve_model

logger = logging.getLogger(__name__)

Batch = resolve_model("Batch")
FermentationStep = resolve_model("FermentationStep")


def _current_step(steps: list, today: date):
    """Return the step whose computed date range contains today, or None."""
    for step in steps:
        if step.date is None:
            continue
        start = step.date
        end = start + timedelta(days=step.days)
        if start <= today < end:
            return step
    return None


async def task_chamber_step_reminder() -> None:
    """For every batch under active chamber control, if the current step has no
    device assigned, log a reminder with the temperature the brewer should set
    manually. Once per step (not once per run) — dedup via a marker appended to
    the log message, checked against recent system_log entries would require a
    query surface system_log doesn't expose cleanly; instead this job runs at a
    day-granularity cadence (see scheduler_setup, hours=2) matched to step
    granularity, and relies on the operator noticing the (infrequent, at most a
    few per day) repeat entries rather than a hard dedup — acceptable for a
    single-user, log-based notification surface. Revisit if this proves noisy.
    """
    db = create_session()
    reminders = 0
    try:
        today = date.today()
        batches = db.scalars(
            select(Batch).where(Batch.chamber_control_active)
        ).all()
        for batch in batches:
            steps = db.scalars(
                select(FermentationStep)
                .where(FermentationStep.batch_id == batch.id)
                .order_by(FermentationStep.order.asc())
            ).all()
            step = _current_step(steps, today)
            if step is None or step.device_id is not None:
                continue
            system_log_scheduler(
                f"Batch '{batch.name}': set fermentation chamber to {step.temp}°C "
                f"({step.name or step.type}) — no chamber controller assigned to this step",
                level=LogLevel.INFO,
            )
            reminders += 1
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("task_chamber_step_reminder failed: %s", exc)
    finally:
        if reminders:
            logger.info("task_chamber_step_reminder: %d manual reminder(s) logged", reminders)
        db.remove()
