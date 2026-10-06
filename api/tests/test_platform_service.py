# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Direct unit tests for platform service methods not exposed via HTTP endpoints."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from core.db import create_session
from core.enums import IngestionSource
from oss.schemas.platform import IngestionLogCreate, SystemLogCreate
from oss.services.platform import IngestionLogService, SystemLogService
from tests.conftest import truncate_database


@pytest.fixture(autouse=True)
def clean_logs():
    """Truncate log tables before and after each test."""
    truncate_database()
    yield
    truncate_database()


def _syslog_entry(**kw):
    defaults = {"event": "test_event", "message": "test message", "level": "INFO"}
    defaults.update(kw)
    return SystemLogCreate(**defaults)


def _ingest_entry(**kw):
    defaults = {
        "source_type": IngestionSource.GRAVITY,
        "ip_address": "192.168.1.1",
        "reason": "test",
        "device_type": "gravitymon",
    }
    defaults.update(kw)
    return IngestionLogCreate(**defaults)


class TestSystemLogService:
    """Tests for SystemLogService CRUD and purge methods."""

    def test_list_returns_entries(self):
        """list() returns all created system log entries."""
        svc = SystemLogService(create_session())
        svc.create(_syslog_entry(event="ev1"))
        svc.create(_syslog_entry(event="ev2"))
        result = svc.list(limit=10)
        assert len(result) >= 2

    def test_list_respects_limit(self):
        """list() returns at most limit entries."""
        svc = SystemLogService(create_session())
        for i in range(5):
            svc.create(_syslog_entry(event=f"ev{i}"))
        result = svc.list(limit=2)
        assert len(result) == 2

    def test_list_ordered_newest_first(self):
        """list() returns entries with the most recent first."""
        svc = SystemLogService(create_session())
        svc.create(_syslog_entry(event="first"))
        svc.create(_syslog_entry(event="second"))
        result = svc.list(limit=10)
        assert len(result) >= 2

    def test_delete_by_timestamp_removes_old_entries(self):
        """delete_by_timestamp() removes entries older than the given day threshold."""
        svc = SystemLogService(create_session())
        svc.create(_syslog_entry(event="old"))
        session = create_session()
        old_ts = datetime.now(UTC) - timedelta(days=60)
        session.execute(
            text("UPDATE system_log SET created_at = :ts"), {"ts": old_ts}
        )
        session.commit()
        deleted = svc.delete_by_timestamp(days=30)
        assert deleted >= 1

    def test_delete_by_timestamp_keeps_recent_entries(self):
        """delete_by_timestamp() does not remove entries newer than the threshold."""
        svc = SystemLogService(create_session())
        svc.create(_syslog_entry(event="recent"))
        deleted = svc.delete_by_timestamp(days=30)
        assert deleted == 0


class TestIngestionLogService:
    """Tests for IngestionLogService CRUD and purge methods."""

    def test_create_and_list(self):
        """Created ingestion log entries are returned by list()."""
        svc = IngestionLogService(create_session())
        svc.create(_ingest_entry())
        result = svc.list()
        assert len(result) >= 1

    def test_delete_by_timestamp_removes_old_entries(self):
        """delete_by_timestamp() removes ingestion log entries older than the threshold."""
        svc = IngestionLogService(create_session())
        svc.create(_ingest_entry(reason="old error"))
        session = create_session()
        old_ts = datetime.now(UTC) - timedelta(days=100)
        session.execute(
            text("UPDATE ingestion_log SET created_at = :ts"), {"ts": old_ts}
        )
        session.commit()
        deleted = svc.delete_by_timestamp(days=90)
        assert deleted >= 1

    def test_delete_by_timestamp_keeps_recent(self):
        """delete_by_timestamp() does not remove entries newer than the threshold."""
        svc = IngestionLogService(create_session())
        svc.create(_ingest_entry(reason="recent"))
        deleted = svc.delete_by_timestamp(days=90)
        assert deleted == 0
