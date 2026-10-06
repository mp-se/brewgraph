# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""BatchDryHop service — dry hop schedule management and trigger evaluation."""
import logging
from datetime import UTC, datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.enums import DryHopTriggerMethod
from core.models.registry import resolve_model
from oss.schemas.batch_dry_hop import BatchDryHopCreate, BatchDryHopUpdate
from oss.services.base import BaseService

BatchDryHop = resolve_model("BatchDryHop")

logger = logging.getLogger(__name__)


class BatchDryHopService(BaseService):
    """CRUD and trigger evaluation for BatchDryHop rows."""

    def __init__(self, db_session: Session):
        super().__init__(BatchDryHop, db_session)

    def list_for_batch(self, batch_id: UUID) -> List["BatchDryHop"]:
        """Return all non-deleted dry hops for a batch ordered by created_at."""
        return list(
            self.db_session.scalars(
                select(self.model)
                .where(self.model.batch_id == batch_id, self.model.deleted_at.is_(None))
                .order_by(self.model.created_at.asc())
            ).all()
        )

    def create_list_for_batch(
        self, batch_id: UUID, items: List[BatchDryHopCreate]
    ) -> List["BatchDryHop"]:
        """Bulk insert dry hops for a batch in a single transaction.

        Named ``*_for_batch`` to match the neighbouring ``list_for_batch``, and
        deliberately *not* ``create_list``: ``BaseService.create_list(lst)`` takes
        one argument, so a same-named method with a different signature shadows it
        rather than overriding it. ``BaseService.update`` calls inherited methods
        on ``self``, so a shadowed base name turns an inherited call into a
        ``TypeError`` — or, worse, silently misreads its first positional
        argument. Same defect and same fix as ``BatchNoteService``.
        """
        created = []
        for item in items:
            row = self.model(
                batch_id=batch_id,
                name=item.name,
                amount=item.amount,
                trigger_method=item.trigger_method.value,
                trigger_gravity=item.trigger_gravity,
                trigger_hours_before=item.trigger_hours_before,
            )
            self.db_session.add(row)
            created.append(row)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return created

    def get_for_batch(self, batch_id: UUID, hop_id: UUID) -> Optional["BatchDryHop"]:
        """Return a single non-deleted dry hop scoped to a batch, or None."""
        return self.db_session.scalars(
            select(self.model).where(
                self.model.id == hop_id,
                self.model.batch_id == batch_id,
                self.model.deleted_at.is_(None),
            )
        ).first()

    def update_hop(
        self, batch_id: UUID, hop_id: UUID, obj: BatchDryHopUpdate
    ) -> Optional["BatchDryHop"]:
        """Partially update a dry hop, including marking it complete or un-complete.

        Replaces the former `complete()`, which could only ever stamp `completed_at` to
        now and never clear it, so a mis-click was permanent.

        `exclude_unset`, not `is None`: `completedAt: null` means "this hop is not done
        after all" and must be distinguishable from a PATCH that only renames the hop.
        """
        hop = self.get_for_batch(batch_id, hop_id)
        if hop is None:
            return None

        fields = obj.model_dump(exclude_unset=True)
        for column, value in fields.items():
            setattr(hop, column, value)

        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return hop

    def delete_hop(self, batch_id: UUID, hop_id: UUID) -> bool:
        """Soft-delete a dry hop. Returns True if found and deleted."""
        hop = self.get_for_batch(batch_id, hop_id)
        if hop is None:
            return False
        hop.deleted_at = datetime.now(UTC)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return True

    def check_and_trigger(
        self,
        batch_id: UUID,
        gravity: Optional[float],
        hours_left: Optional[float],
    ) -> None:
        """Evaluate pending dry hops and set triggered_at if conditions are met.

        Idempotent: once triggered_at is set, the hop is never re-evaluated.
        """
        pending = self.db_session.scalars(
            select(self.model).where(
                self.model.batch_id == batch_id,
                self.model.triggered_at.is_(None),
                self.model.deleted_at.is_(None),
            )
        ).all()

        now = datetime.now(UTC)
        for hop in pending:
            if hop.trigger_method == DryHopTriggerMethod.GRAVITY_LEVEL.value:
                if gravity is not None and hop.trigger_gravity is not None:
                    if gravity <= hop.trigger_gravity:
                        hop.triggered_at = now
            else:  # hours_before_completion
                if hours_left is not None and hop.trigger_hours_before is not None:
                    if hours_left <= hop.trigger_hours_before:
                        hop.triggered_at = now

        if pending:
            try:
                self.db_session.commit()
            except Exception as e:
                self.db_session.rollback()
                raise e
