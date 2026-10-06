# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""BatchNote service."""
import logging
from datetime import UTC, datetime
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models.registry import resolve_model
from oss.services._cursor import Cursor, apply_cursor_filter, cursor_order_by
from oss.services.base import BaseService

logger = logging.getLogger(__name__)

BatchNote = resolve_model("BatchNote")


class BatchNoteService(BaseService):
    """Service for managing notes attached to a batch."""

    def __init__(self, db_session: Session):
        super().__init__(BatchNote, db_session)

    def list_by_batch(self, batch_id: UUID) -> List[BatchNote]:
        """Return all non-deleted notes for a batch ordered by created_at ascending."""
        rows = self.db_session.scalars(
            select(self.model)
            .where(self.model.batch_id == batch_id, self.model.deleted_at.is_(None))
            .order_by(self.model.created_at.asc())
        ).all()
        logger.info("Fetched %d notes for batch %s", len(rows), batch_id)
        return list(rows)

    def list_by_batch_cursor(
        self,
        batch_id: UUID,
        limit: int = 200,
        cursor: Optional[Cursor] = None,
    ) -> Tuple[List[BatchNote], bool]:
        """Cursor page of a batch's notes, oldest first, plus has_more.

        Ascending, unlike the log and prediction histories: notes are read as a
        narrative of the brew from the start, the same way the reading lists are.
        """
        query = (
            select(self.model)
            .where(self.model.batch_id == batch_id, self.model.deleted_at.is_(None))
        )
        query = apply_cursor_filter(query, self.model, cursor)
        query = query.order_by(*cursor_order_by(self.model))
        rows = list(self.db_session.scalars(query.limit(limit + 1)).all())
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def create_for_batch(
        self,
        batch_id: UUID,
        content: str,
        created_at: datetime | None = None,
        meta: dict | None = None,
    ) -> BatchNote:
        """Create a note; uses provided created_at if given, otherwise current UTC
        time. meta carries optional created_by/note_type/test_result — the latter
        two for forced-diacetyl test notes."""
        meta = meta or {}
        now = datetime.now(UTC)
        db_obj = self.model(
            batch_id=batch_id,
            content=content,
            created_by=meta.get("created_by"),
            note_type=meta.get("note_type"),
            test_result=meta.get("test_result"),
            created_at=created_at or now,
            updated_at=now,
        )
        self.db_session.add(db_obj)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        self.db_session.refresh(db_obj)
        logger.info("Created note %s for batch %s", db_obj.id, batch_id)
        return db_obj

    def get_for_batch(self, batch_id: UUID, note_id: UUID) -> Optional[BatchNote]:
        """Return a note scoped to a batch (soft-deleted or not), or None.

        Deliberately not filtered on `deleted_at` here — update/delete/restore
        each apply their own not-found-vs-already-deleted semantics on top.
        Callers must go through this rather than a bare `db_session.get(note_id)`:
        a note ID resolved without checking `batch_id` lets a note from one batch
        be mutated through a different batch's URL.
        """
        return self.db_session.scalar(
            select(self.model).where(self.model.id == note_id, self.model.batch_id == batch_id)
        )

    def update_note(
        self,
        batch_id: UUID,
        note_id: UUID,
        content: str | None,
        note_type: str | None = None,
        test_result: str | None = None,
    ) -> BatchNote:
        """Update the content of an existing note owned by the given batch."""
        note = self.get_for_batch(batch_id, note_id)
        if note is None:
            raise HTTPException(status_code=404, detail="Note not found")

        if content is not None:
            note.content = content
        if note_type is not None:
            note.note_type = note_type
        if test_result is not None:
            note.test_result = test_result
        note.updated_at = datetime.now(UTC)

        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        self.db_session.refresh(note)
        return note

    def restore_note(self, batch_id: UUID, note_id: UUID) -> bool:
        """Clear a note's `deleted_at`. False when not found, not owned by this
        batch, or not deleted."""
        note = self.get_for_batch(batch_id, note_id)
        if note is None or note.deleted_at is None:
            return False
        note.deleted_at = None
        self.db_session.commit()
        return True

    def delete_note(self, batch_id: UUID, note_id: UUID) -> None:
        """Soft-delete a note owned by the given batch."""
        note = self.get_for_batch(batch_id, note_id)
        if note is None or note.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Note not found")
        note.deleted_at = datetime.now(UTC)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        logger.info("Soft-deleted note %s", note_id)
