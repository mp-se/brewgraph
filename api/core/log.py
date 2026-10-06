# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Custom logging configuration and handlers for application event logging."""
import logging
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from core.db import create_session
from core.models.platform import IngestionLog, SystemLog


class SystemLogCreate(BaseModel):
    """Schema for creating a system log entry."""

    level: str = Field(default="INFO", max_length=10)
    event: str = Field(max_length=80)
    message: str = Field(max_length=500)


class SystemLogWriter:
    """Service for persisting and managing system log entries."""

    def __init__(self, db):
        """Initialize with a DB session or session factory."""
        self._db = db if not callable(db) else db()

    def create(self, obj: SystemLogCreate) -> SystemLog:
        """Persist a new system log entry and return it."""
        entry = SystemLog(level=obj.level, event=obj.event, message=obj.message)
        self._db.add(entry)
        self._db.commit()
        return entry

    def delete_by_timestamp(self, days: int = 30) -> int:
        """Delete log entries older than the given number of days; returns deleted count."""
        from datetime import UTC  # pylint: disable=import-outside-toplevel
        dt = datetime.now(UTC) - timedelta(days=days)
        result = self._db.execute(delete(SystemLog).where(SystemLog.created_at <= dt))
        self._db.commit()
        return result.rowcount

logger = logging.getLogger(__name__)


class LogLevel(str):
    """System log level constants."""
    DEBUG    = "DEBUG"
    INFO     = "INFO"
    WARNING  = "WARNING"
    ERROR    = "ERROR"
    CRITICAL = "CRITICAL"


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[:max_length - 3] + "..."


def system_log(
    event: str,
    message: str,
    level: str = LogLevel.INFO,
) -> None:
    """Log a system event to the database."""
    session_factory = create_session()
    owns_session = not session_factory.registry.has()
    session = session_factory()
    try:
        entry = SystemLogCreate(
            level=level,
            event=_truncate(event, 80),
            message=_truncate(message, 500),
        )
        service = SystemLogWriter(session)
        service.create(entry)
    except SQLAlchemyError as e:
        logger.error("Failed to write system log: %s", e)
    finally:
        if owns_session:
            session_factory.remove()


def system_log_purge(days: int = 60) -> None:
    """Purge system log entries older than the given number of days."""
    logger.info("Purging system log records older than %d days", days)
    session_factory = create_session()
    owns_session = not session_factory.registry.has()
    session = session_factory()
    try:
        count = SystemLogWriter(session).delete_by_timestamp(days)
        logger.info("Deleted %d records from system log", count)
    finally:
        if owns_session:
            session_factory.remove()


def system_log_scheduler(message: str, level: str = LogLevel.INFO) -> None:
    """Log a scheduler-related system event."""
    system_log("scheduler_event", message=message, level=level)


def system_log_security(message: str, level: str = LogLevel.INFO) -> None:
    """Log a security-related system event."""
    system_log("security_event", message=message, level=level)


def system_log_fermentationcontrol(message: str, level: str = LogLevel.INFO) -> None:
    """Log a fermentation control system event."""
    system_log("fermentation_control_event", message=message, level=level)


def system_log_purge_scheduler(message: str, level: str = LogLevel.INFO) -> None:
    """Log a purge-related system event."""
    system_log("purge_event", message=message, level=level)


def ingestion_log_purge(days: int = 120) -> None:
    """Delete ingestion error log entries older than specified days."""
    session_factory = create_session()
    owns_session = not session_factory.registry.has()
    session = session_factory()
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = (
            session.query(IngestionLog)
            .filter(IngestionLog.created_at < cutoff_date)
            .delete()
        )
        session.commit()
        if deleted_count > 0:
            logger.info(
                "Purged %d ingestion error log records older than %d days",
                deleted_count, days,
            )
    except SQLAlchemyError as e:
        logger.error("Failed to purge ingestion error logs: %s", e)
    finally:
        if owns_session:
            session_factory.remove()
