# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Prediction service."""
from datetime import UTC, datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models.registry import resolve_model
from oss.schemas.prediction import PredictionCreate
from oss.services._batched import group_by_owner, latest_by_owner
from oss.services._cursor import Cursor, apply_cursor_filter, cursor_order_by
from oss.services.base import BaseService

Prediction = resolve_model("Prediction")


class PredictionService(
    BaseService[Prediction, PredictionCreate, PredictionCreate]
):
    """Service for storing and querying ML predictions."""

    def __init__(self, db_session: Session):
        super().__init__(Prediction, db_session)

    def latest_for_batch(self, batch_id: UUID) -> Optional[Prediction]:
        """Return the most recent prediction for a batch."""
        return (
            self.db_session.scalars(
                select(Prediction)
                .where(Prediction.batch_id == batch_id, Prediction.deleted_at.is_(None))
                .order_by(Prediction.created_at.desc())
                .limit(1)
            ).first()
        )

    def history_for_batch(self, batch_id: UUID) -> List[Prediction]:
        """Return all predictions for a batch, newest first."""
        return list(
            self.db_session.scalars(
                select(Prediction)
                .where(Prediction.batch_id == batch_id, Prediction.deleted_at.is_(None))
                .order_by(Prediction.created_at.desc())
            ).all()
        )

    def history_for_owners(self, owner_col, owner_ids):
        """Return `{owner_id: [predictions]}` newest first, in one query.

        `owner_col` is the column that names the relation — Prediction.batch_id,
        .device_id, .vessel_id or .tap_id — so the four dashboard loops share one
        implementation instead of four near-identical ones.
        """
        return group_by_owner(
            self.db_session, Prediction, owner_col, owner_ids,
            extra_where=[Prediction.deleted_at.is_(None)],
            order_by=Prediction.created_at.desc(),
        )

    def latest_for_owners(self, owner_col, owner_ids):
        """Return one current prediction per owner for dashboard summaries."""
        return latest_by_owner(
            self.db_session, Prediction, owner_col, owner_ids,
            extra_where=[Prediction.deleted_at.is_(None)],
        )

    def latest_for_device(self, device_id: UUID) -> Optional[Prediction]:
        """Return the most recent prediction for a device."""
        if not hasattr(Prediction, "device_id"):
            return None
        return (
            self.db_session.scalars(
                select(Prediction)
                .where(Prediction.device_id == device_id, Prediction.deleted_at.is_(None))
                .order_by(Prediction.created_at.desc())
                .limit(1)
            ).first()
        )

    def history_for_device(self, device_id: UUID) -> List[Prediction]:
        """Return all predictions for a device, newest first."""
        if not hasattr(Prediction, "device_id"):
            return []
        return list(
            self.db_session.scalars(
                select(Prediction)
                .where(Prediction.device_id == device_id, Prediction.deleted_at.is_(None))
                .order_by(Prediction.created_at.desc())
            ).all()
        )

    def latest_for_vessel(self, vessel_id: UUID) -> Optional[Prediction]:
        """Return the most recent prediction for a vessel."""
        if not hasattr(Prediction, "vessel_id"):
            return None
        return (
            self.db_session.scalars(
                select(Prediction)
                .where(Prediction.vessel_id == vessel_id, Prediction.deleted_at.is_(None))
                .order_by(Prediction.created_at.desc())
                .limit(1)
            ).first()
        )

    def history_for_vessel(self, vessel_id: UUID) -> List[Prediction]:
        """Return all predictions for a vessel, newest first."""
        if not hasattr(Prediction, "vessel_id"):
            return []
        return list(
            self.db_session.scalars(
                select(Prediction)
                .where(Prediction.vessel_id == vessel_id, Prediction.deleted_at.is_(None))
                .order_by(Prediction.created_at.desc())
            ).all()
        )

    def history_for_tap(self, tap_id: UUID) -> List[Prediction]:
        """Return all predictions for a tap, newest first.

        Tap-scoped predictions are about the plumbing — cleaning is due on a tap
        and stays with it across keg swaps. A keg's own predictions (`keg_empty`)
        belong to the vessel and are not returned here.
        """
        return list(
            self.db_session.scalars(
                select(Prediction)
                .where(Prediction.tap_id == tap_id, Prediction.deleted_at.is_(None))
                .order_by(Prediction.created_at.desc())
            ).all()
        )

    def soft_delete(self, prediction_id: int) -> bool:
        """Hide a prediction the brewer knows is wrong. Returns False if not found.

        The row stays on disk until the grace-window purge takes it, so the model's
        actual output remains available for evaluating the model — dismissing a bad
        prediction is not the same as claiming it never happened.
        """
        row = self.db_session.get(Prediction, prediction_id)
        if row is None or row.deleted_at is not None:
            return False
        row.deleted_at = datetime.now(UTC)
        self.db_session.commit()
        return True

    def history_cursor(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        column: str,
        owner_id: UUID,
        limit: int = 200,
        cursor: Optional[Cursor] = None,
    ) -> Tuple[List[Prediction], bool]:
        """Cursor page of one entity's predictions, newest first, plus has_more.

        Descending like the log endpoints and for the same reason: prediction history
        is read from the most recent backwards. `cursor` is the `(created_at, id)` of
        the last row on the previous page.
        """
        query = (
            select(Prediction)
            .where(getattr(Prediction, column) == owner_id, Prediction.deleted_at.is_(None))
        )
        query = apply_cursor_filter(query, Prediction, cursor, ascending=False)
        query = query.order_by(*cursor_order_by(Prediction, ascending=False))
        rows = list(self.db_session.scalars(query.limit(limit + 1)).all())
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def restore(self, prediction_id: int) -> Optional[Prediction]:
        """Undo a dismissal. Returns None when not found or not dismissed.

        The window is the grace period before the purge job removes the row — after
        that there is nothing to restore, which is the same bargain every other
        soft-deleted entity makes.
        """
        row = self.db_session.get(Prediction, prediction_id)
        if row is None or row.deleted_at is None:
            return None
        row.deleted_at = None
        self.db_session.commit()
        return row

    def list_all(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        batch_id: Optional[UUID] = None,
        device_id: Optional[UUID] = None,
        vessel_id: Optional[UUID] = None,
        tap_id: Optional[UUID] = None,
        prediction_type: Optional[str] = None,
        limit: int = 200,
    ) -> List[Prediction]:
        """Return predictions filtered by any combination of owner and type."""
        from core.enums import \
            PredictionType as PT  # pylint: disable=import-outside-toplevel
        stmt = (
            select(Prediction)
            .where(Prediction.deleted_at.is_(None))
            .order_by(Prediction.created_at.desc())
        )
        if batch_id is not None:
            stmt = stmt.where(Prediction.batch_id == batch_id)
        if device_id is not None:
            stmt = stmt.where(Prediction.device_id == device_id)
        if vessel_id is not None:
            stmt = stmt.where(Prediction.vessel_id == vessel_id)
        if tap_id is not None:
            stmt = stmt.where(Prediction.tap_id == tap_id)
        if prediction_type is not None:
            stmt = stmt.where(Prediction.prediction_type == PT(prediction_type))
        stmt = stmt.limit(limit)
        return list(self.db_session.scalars(stmt).all())
