# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Fermentation step service."""
import logging
from datetime import UTC, date, datetime, timedelta
from typing import List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select, update as sa_update
from sqlalchemy.orm import Session

from core.models.registry import resolve_model
from oss.schemas.fermentation_step import FermentationStepCreate
from oss.services.base import BaseService

logger = logging.getLogger(__name__)

FermentationStep = resolve_model("FermentationStep")
Batch = resolve_model("Batch")


class FermentationStepService(BaseService):
    """Service for managing fermentation steps belonging to a batch."""

    def __init__(self, db_session: Session):
        super().__init__(FermentationStep, db_session)

    def create_list(self, lst: List[FermentationStepCreate]) -> List[FermentationStep]:
        if not lst:
            raise HTTPException(status_code=400, detail="No fermentation steps in request.")
        self._validate_batch_exists(lst[0].batch_id)
        return super().create_list(lst)

    def replace_for_batch(
        self, batch_id: UUID, lst: List[FermentationStepCreate]
    ) -> List[FermentationStep]:
        """Replace all fermentation steps for a batch in a single transaction."""
        if not lst:
            raise HTTPException(status_code=400, detail="No fermentation steps in request.")
        self._validate_batch_exists(batch_id)
        self.db_session.execute(
            delete(self.model).where(self.model.batch_id == batch_id)
        )
        self._clear_chamber_control(batch_id)
        return super().create_list(lst)

    def search_by_batch_id(self, batch_id: UUID) -> List[FermentationStep]:
        """Return all non-deleted fermentation steps for a batch ordered by step order."""
        rows = self.db_session.scalars(
            select(self.model)
            .where(self.model.batch_id == batch_id, self.model.deleted_at.is_(None))
            .order_by(self.model.order.asc())
        ).all()
        logger.info("Fetched %d fermentation steps for batch %s", len(rows), batch_id)
        return list(rows)

    def delete_by_batch_id(self, batch_id: UUID) -> int:
        """Soft-delete all fermentation steps for a batch. Returns affected row count."""
        result = self.db_session.execute(
            sa_update(self.model)
            .where(self.model.batch_id == batch_id, self.model.deleted_at.is_(None))
            .values(deleted_at=datetime.now(UTC))
        )
        self._clear_chamber_control(batch_id)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        logger.info("Deleted %d fermentation steps for batch %s", result.rowcount, batch_id)
        return result.rowcount

    def delete_by_id(self, batch_id: UUID, step_id: UUID) -> None:
        """Soft-delete a single fermentation step. Raises 404 if not found, not owned
        by batch, or already deleted."""
        step = self.db_session.scalars(
            select(self.model).where(
                self.model.id == step_id,
                self.model.batch_id == batch_id,
                self.model.deleted_at.is_(None),
            )
        ).first()
        if not step:
            raise HTTPException(status_code=404, detail="Fermentation step not found")
        step.deleted_at = datetime.now(UTC)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        logger.info("Deleted fermentation step %s for batch %s", step_id, batch_id)

    def _clear_chamber_control(self, batch_id: UUID) -> None:
        """A changed/removed schedule requires explicit re-activation — otherwise
        the active flag lingers on steps without activation dates
        (perpetual R + the reminder job keeps scanning the batch)."""
        batch = self.db_session.get(Batch, batch_id)
        if batch is not None and batch.chamber_control_active:
            batch.chamber_control_active = False

    def _today(self, batch) -> date:  # pylint: disable=unused-argument
        """The date a schedule is measured against.

        A hook, not a constant, so a deployment can resolve it in a timezone other
        than the server's own — overriding this one method is what lets the
        scheduling logic below stay shared rather than forked per timezone policy.
        """
        return date.today()

    def activate(self, batch_id: UUID) -> List[FermentationStep]:
        """Activate temperature control for a batch's step list.

        Computes each step's `date` as an absolute start date (ISO "YYYY-MM-DD",
        matching the column's String(20) type), cascading from today by each step's
        `days` in `order` — step 0 covers [today, today+step0.days), step 1 starts
        where step 0 ends, etc. Marks the batch as under active control. Re-running
        this discards any previous schedule and recomputes from today — no
        pause/resume support for a schedule mid-step.
        """
        self._validate_batch_exists(batch_id)
        steps = self.search_by_batch_id(batch_id)
        if not steps:
            raise HTTPException(
                status_code=400, detail="Batch has no fermentation steps to activate."
            )

        # days < 1 makes a step unmatchable (half-open range [date, date+days))
        # and a trailing 0-day step auto-deactivates on the first poll — reject
        # at activation with an actionable message rather than failing silently.
        bad = [s for s in steps if s.days < 1]
        if bad:
            raise HTTPException(
                status_code=400,
                detail="Every fermentation step needs days >= 1 to be activated.",
            )

        batch = self.db_session.get(Batch, batch_id)
        cursor = self._today(batch)
        for step in steps:
            step.date = cursor
            cursor = cursor + timedelta(days=step.days)

        batch.chamber_control_active = True
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        logger.info("Activated chamber control for batch %s (%d steps)", batch_id, len(steps))
        return steps

    def deactivate(self, batch_id: UUID) -> None:
        """End temperature control for a batch before its schedule would otherwise
        expire on its own. Subsequent chamber polls for this batch's steps return
        mode R. Does not mutate step dates."""
        batch = self._validate_batch_exists(batch_id)
        batch.chamber_control_active = False
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        logger.info("Deactivated chamber control for batch %s", batch_id)

    def advance_step(self, batch_id: UUID) -> FermentationStep:
        """End the batch's currently-active fermentation step early and move on to
        whichever step's date range takes over next. Mirrors the step-matching
        algorithm in confirm_diacetyl_pass/resolve_chamber_mode, but fires
        triggered_at regardless of trigger_type (day_offset, terminal_gravity, or
        manual are all eligible, unlike the diacetyl gate which only fires manual
        steps). Raises 400 if the batch isn't under active chamber control, or
        there is no current step to advance past."""
        batch = self._validate_batch_exists(batch_id)
        if not batch.chamber_control_active:
            raise HTTPException(
                status_code=400, detail="Batch is not under active chamber control."
            )

        steps = self.search_by_batch_id(batch_id)
        today = self._today(batch)
        matched = None
        for step in steps:
            if step.date is None:
                continue
            start = step.date
            end = start + timedelta(days=step.days)
            if step.trigger_type == "manual":
                ended = step.triggered_at is not None
            else:
                ended = step.triggered_at is not None or today >= end
            if start <= today and not ended:
                matched = step
                break

        if matched is None:
            raise HTTPException(
                status_code=400, detail="No currently active fermentation step to advance."
            )

        matched.triggered_at = datetime.now(UTC)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        logger.info("Advanced fermentation step %s for batch %s", matched.id, batch_id)
        return matched

    def confirm_diacetyl_pass(self, batch_id: UUID) -> bool:
        """Fire triggered_at on the batch's currently-active manual step after a
        passed forced-diacetyl test. Mirrors the step-matching algorithm in
        oss/services/ingestion.py's resolve_chamber_mode, but batch notes are not
        device-scoped so this considers all of the batch's steps ordered by order.
        Returns False (no-op) if the batch isn't under active chamber control, or
        there is no current step that is both manual and not already triggered.
        """
        batch = self.db_session.get(Batch, batch_id)
        if batch is None or not batch.chamber_control_active:
            return False

        steps = self.search_by_batch_id(batch_id)
        today = self._today(batch)
        matched = None
        advanced_early = False
        for step in steps:
            if step.date is None:
                continue
            start = step.date
            end = start + timedelta(days=step.days)
            if step.triggered_at is not None:
                advanced_early = True
                continue
            is_manual = step.trigger_type == "manual"
            if not is_manual and today >= end:
                continue
            effective_start = today if advanced_early else start
            if effective_start <= today:
                matched = step
                break

        if matched is None or matched.trigger_type != "manual" or matched.triggered_at is not None:
            return False

        matched.triggered_at = datetime.now(UTC)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        logger.info(
            "Confirmed diacetyl pass for batch %s, fired step %s", batch_id, matched.id
        )
        return True
