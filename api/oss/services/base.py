# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Base service class providing generic CRUD operations for database models."""
import logging
from typing import Any, Generic, List, Optional, Tuple, Type, TypeVar

import sqlalchemy
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from core.enums import BatchStatus
from core.models import Base
from core.models.registry import resolve_model

logger = logging.getLogger(__name__)

model_t = TypeVar("model_t", bound=Base)  # pylint: disable=invalid-name
create_schema_t = TypeVar("create_schema_t", bound=BaseModel)  # pylint: disable=invalid-name
update_schema_t = TypeVar("update_schema_t", bound=BaseModel)  # pylint: disable=invalid-name


class BaseService(Generic[model_t, create_schema_t, update_schema_t]):
    """Generic base service class providing CRUD operations for database models."""

    # Non-column schema fields must be named by the owning service. This keeps
    # relationship inputs and computed response helpers explicit while rejecting
    # accidental model/schema drift everywhere else.
    transient_fields: frozenset[str] = frozenset()

    def __init__(self, model: Type[model_t], db_session: Session):
        self.model = model
        self.db_session = db_session

    def get(self, item_id: Any) -> Optional[model_t]:
        """Retrieve a single item by ID, returns None if not found."""
        obj: Optional[model_t] = self.db_session.get(self.model, item_id)
        return obj

    def get_active(self, item_id: Any) -> Optional[model_t]:
        """Like `get()`, but returns None for a soft-deleted row too.

        `get()` deliberately stays deleted-agnostic — restore()/soft_delete() on
        every service need to see the row they are about to flip. Any caller
        that must reject a soft-deleted row before mutating it (PATCH, token
        rotation, and similar write paths) should use this instead. A model with
        no `deleted_at` column behaves exactly like `get()`.
        """
        obj = self.get(item_id)
        if obj is not None and getattr(obj, "deleted_at", None) is not None:
            return None
        return obj

    def list(self) -> List[model_t]:
        """Retrieve all items of this model type, newest first."""
        objs: List[model_t] = self.db_session.scalars(
            select(self.model).order_by(self.model.created_at.desc())
        ).all()
        return objs

    def _model_columns(self) -> set:
        """Return the set of mapped column names for this model."""
        return {c.key for c in sa_inspect(self.model).mapper.column_attrs}

    def _filter_for_model(self, data: dict) -> dict:
        """Reject data that the mapped model cannot persist.

        Silently dropping schema fields hides an ORM/schema mismatch and returns a
        successful response for a write that lost user data. Every create schema
        should describe fields the selected model owns; intentional transient
        inputs belong in the calling service, not this generic persistence path.
        """
        cols = self._model_columns()
        unknown = set(data) - cols - self.transient_fields
        if unknown:
            raise ValueError(
                f"{self.model.__name__} has no mapped columns for: "
                f"{', '.join(sorted(unknown))}"
            )
        return {key: value for key, value in data.items() if key in cols}

    def build(self, obj: create_schema_t) -> model_t:
        """Stage a new item on the session without committing it.

        Split out of create() so a caller with follow-on work in the same
        transaction — a vessel that also packages its batch, say — can commit
        once at the end rather than leaving a committed row behind if the
        second step fails.
        """
        db_obj: model_t = self.model(**self._filter_for_model(obj.model_dump()))
        self.db_session.add(db_obj)
        return db_obj

    def commit(self) -> None:
        """Commit the session, translating a duplicate key into a 409."""
        try:
            self.db_session.commit()
        except sqlalchemy.exc.IntegrityError as e:
            self.db_session.rollback()
            raise HTTPException(status_code=409, detail="Conflict Error") from e
        except Exception as e:
            self.db_session.rollback()
            raise e

    def create(self, obj: create_schema_t) -> model_t:
        """Create a new item in the database."""
        db_obj: model_t = self.build(obj)
        try:
            self.db_session.commit()
        except sqlalchemy.exc.IntegrityError as e:
            self.db_session.rollback()
            raise HTTPException(status_code=409, detail="Conflict Error") from e
        except Exception as e:
            self.db_session.rollback()
            raise e

        return db_obj

    def create_list(self, lst: List[create_schema_t]) -> List[model_t]:
        """Create multiple items in the database."""
        db_obj_lst = []
        for obj in lst:
            db_obj: model_t = self.model(**self._filter_for_model(obj.model_dump()))
            self.db_session.add(db_obj)
            db_obj_lst.append(db_obj)
        try:
            self.db_session.commit()
        except sqlalchemy.exc.IntegrityError as e:
            self.db_session.rollback()
            raise HTTPException(status_code=409, detail="Conflict Error") from e
        except Exception as e:
            self.db_session.rollback()
            raise e

        return db_obj_lst

    def update(self, item_id: Any, obj: update_schema_t) -> Optional[model_t]:
        """Update an existing item in the database, returns None if not found
        or soft-deleted."""
        db_obj = self.get_active(item_id)
        if db_obj is None:
            return None
        for column, value in obj.model_dump(exclude_unset=True).items():
            setattr(db_obj, column, value)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return db_obj

    # There is deliberately no generic `delete()` here.
    #
    # Every entity carrying `deleted_at` is soft-deleted on the request path and
    # hard-deleted only by a scheduled purge job. That puts every irreversible act
    # behind a grace window on a timer rather than a button that can be clicked
    # twice. A hard delete inherited by every
    # service is the easiest way to lose that property by accident, so the base class
    # does not offer one. A job that needs to destroy rows writes the query itself.

    def _validate_batch_exists(self, batch_id: int):
        """Validate that a batch exists, is not soft-deleted, and is not archived.

        Raises HTTPException if not. An archived batch is done fermenting and
        packaged away — new manual/bulk measurements against it are as much a
        lifecycle violation as writing to a soft-deleted one, so both states
        reject here the same way.
        """
        batch = self.db_session.get(resolve_model("Batch"), batch_id)
        logger.info("Searching for batch with id=%s %s", batch_id, batch)
        if (
            batch is None
            or batch.deleted_at is not None
            or batch.status == BatchStatus.ARCHIVED.value
        ):
            raise HTTPException(
                status_code=404,
                detail=f"Batch with id = {batch_id} not found.",
            )
        return batch

    def update_for_owner(self, item_id: Any, owner_column: str, owner_id: Any, obj):
        """Update one reading only when it belongs to the requested parent."""
        item = self.db_session.scalars(
            select(self.model).where(
                self.model.id == item_id,
                getattr(self.model, owner_column) == owner_id,
                self.model.deleted_at.is_(None),
            )
        ).first()
        if item is None:
            return None
        for column, value in obj.model_dump(exclude_unset=True).items():
            setattr(item, column, value)
        try:
            self.db_session.commit()
        except Exception as exc:
            self.db_session.rollback()
            raise exc
        return item

    def count(self) -> int:
        """Return number of active (non-soft-deleted) records for this model."""
        stmt = select(func.count()).select_from(self.model)  # pylint: disable=not-callable
        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return self.db_session.scalar(stmt) or 0

    def list_page(self, page: int = 1, page_size: int = 50) -> Tuple[List[model_t], int]:
        """Return one offset page of items and the total row count."""
        offset = (page - 1) * page_size
        total: int = self.db_session.scalar(
            select(func.count()).select_from(self.model)  # pylint: disable=not-callable
        ) or 0
        items: List[model_t] = list(
            self.db_session.scalars(
                select(self.model)
                .order_by(self.model.created_at.desc())
                .offset(offset)
                .limit(page_size)
            ).all()
        )
        return items, total

    def _search_by_filter(self, filters: dict) -> List[model_t]:
        """Generic search by filter dictionary."""
        objs: List[model_t] = self.db_session.scalars(
            select(self.model).filter_by(**filters).order_by(self.model.created_at.desc())
        ).all()
        return objs
