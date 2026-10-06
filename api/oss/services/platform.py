# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Platform services: TenantSettingsService and SystemLogService."""
import logging
from datetime import UTC, datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from core.models.platform import IngestionLog, SystemLog
from core.models.registry import resolve_model
from oss.schemas.platform import (IngestionLogCreate, SystemLogCreate,
                                   SystemLogResponse)
from oss.services._cursor import Cursor, apply_cursor_filter, cursor_order_by
from oss.services.base import BaseService

logger = logging.getLogger(__name__)

TenantSettings = resolve_model("TenantSettings")


class TenantSettingsService(BaseService):
    """Service for managing BrewGraph application settings."""

    def __init__(self, db_session: Session):
        super().__init__(TenantSettings, db_session)

    def list(self):
        return self.db_session.scalars(
            select(TenantSettings).order_by(TenantSettings.updated_at.desc())
        ).all()


class SystemLogService(BaseService[SystemLog, SystemLogCreate, SystemLogResponse]):
    """Service for managing system log entries and event tracking."""

    def __init__(self, db_session: Session):
        super().__init__(SystemLog, db_session)

    def list(self, limit: int = 100) -> List[SystemLog]:
        objs: List[SystemLog] = (
            self.db_session.query(SystemLog)
            .order_by(SystemLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return objs

    def list_cursor(
        self, limit: int = 50, cursor: Optional[Cursor] = None
    ) -> Tuple[List[SystemLog], bool]:
        """Return up to `limit` entries newest-first, plus whether more remain.

        Logs are time-series, so they take the same cursor contract as the reading
        endpoints. Descending here rather than ascending: a log is read from the
        most recent entry backwards, and `cursor` is the `(created_at, id)` of the
        last row on the previous page.
        """
        query = self.db_session.query(SystemLog)
        query = apply_cursor_filter(query, SystemLog, cursor, ascending=False)
        query = query.order_by(*cursor_order_by(SystemLog, ascending=False))
        rows = query.limit(limit + 1).all()
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def list_paginated(self, skip: int = 0, limit: int = 50) -> Tuple[List[SystemLog], int]:
        """Return one page of system log entries (newest first) and the total count."""
        total = self.db_session.query(SystemLog).count()
        objs: List[SystemLog] = (
            self.db_session.query(SystemLog)
            .order_by(SystemLog.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return objs, total

    def delete_by_timestamp(self, days: int = 30) -> int:
        """Delete system log entries older than the specified number of days."""
        dt = datetime.now(UTC) - timedelta(days=days)
        statement = delete(SystemLog).where(SystemLog.created_at <= dt)
        result = self.db_session.execute(statement)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return result.rowcount


class IngestionLogService(BaseService[IngestionLog, IngestionLogCreate, IngestionLogCreate]):
    """Service for managing ingestion log entries."""

    def __init__(self, db_session: Session):
        super().__init__(IngestionLog, db_session)

    def list_cursor(
        self, limit: int = 50, cursor: Optional[Cursor] = None
    ) -> Tuple[List[IngestionLog], bool]:
        """Return up to `limit` entries newest-first, plus whether more remain.

        Logs are time-series, so they take the same cursor contract as the reading
        endpoints. Descending here rather than ascending: a log is read from the
        most recent entry backwards, and `cursor` is the `(created_at, id)` of the
        last row on the previous page.
        """
        query = self.db_session.query(IngestionLog)
        query = apply_cursor_filter(query, IngestionLog, cursor, ascending=False)
        query = query.order_by(*cursor_order_by(IngestionLog, ascending=False))
        rows = query.limit(limit + 1).all()
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def list_paginated(self, skip: int = 0, limit: int = 50) -> Tuple[List[IngestionLog], int]:
        """Return one page of ingestion log entries (newest first) and the total count."""
        total = self.db_session.query(IngestionLog).count()
        objs: List[IngestionLog] = (
            self.db_session.query(IngestionLog)
            .order_by(IngestionLog.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return objs, total

    def delete_by_timestamp(self, days: int = 90) -> int:
        """Delete ingestion log entries older than the specified number of days."""
        dt = datetime.now(UTC) - timedelta(days=days)
        statement = delete(IngestionLog).where(IngestionLog.created_at <= dt)
        result = self.db_session.execute(statement)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return result.rowcount
