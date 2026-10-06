# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Unit tests for core/log.py utility functions."""
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

from core.log import (LogLevel, _truncate, ingestion_log_purge,
                      system_log, system_log_fermentationcontrol,
                      system_log_purge, system_log_purge_scheduler,
                      system_log_scheduler, system_log_security)
from tests.conftest import truncate_database


def test_truncate_short_string():
    """Returns the original string when it is shorter than the limit."""
    assert _truncate("hello", 10) == "hello"


def test_truncate_exact_length():
    """Returns the original string when length equals the limit exactly."""
    assert _truncate("hello", 5) == "hello"


def test_truncate_long_string():
    """Truncates to the limit and appends ellipsis."""
    result = _truncate("a" * 20, 10)
    assert len(result) == 10
    assert result.endswith("...")


def test_system_log_writes_to_db():
    """system_log persists an entry to the database without raising."""
    truncate_database()
    system_log("test_event", "Test message", LogLevel.INFO)


def test_system_log_long_event_and_message():
    """system_log silently truncates oversized event and message strings."""
    truncate_database()
    system_log("x" * 100, "y" * 600)


def test_system_log_db_error_is_swallowed():
    """SQLAlchemyError during system_log must not propagate."""
    with patch("core.log.SystemLogWriter") as mock_svc_cls, \
         patch("core.log.create_session") as mock_session_factory:
        factory = MagicMock()
        mock_session_factory.return_value = factory
        factory.registry.has.return_value = False
        mock_svc = MagicMock()
        mock_svc.create.side_effect = OperationalError("", {}, Exception())
        mock_svc_cls.return_value = mock_svc
        system_log("ev", "msg")  # must not raise
    factory.remove.assert_called_once()


def test_system_log_purge_removes_old_entries():
    """system_log_purge deletes entries older than the given days threshold."""
    truncate_database()
    system_log("old_ev", "old message")
    system_log_purge(days=0)


def test_system_log_scheduler():
    """system_log_scheduler writes a scheduler-category log entry."""
    truncate_database()
    system_log_scheduler("scheduler fired")


def test_system_log_security():
    """system_log_security writes a security-category log entry."""
    truncate_database()
    system_log_security("auth failed", LogLevel.WARNING)


def test_system_log_fermentationcontrol():
    """system_log_fermentationcontrol writes a fermentation-control log entry."""
    truncate_database()
    system_log_fermentationcontrol("step changed")


def test_system_log_purge_scheduler():
    """system_log_purge_scheduler writes a purge-scheduler log entry."""
    truncate_database()
    system_log_purge_scheduler("purge ran")


def test_ingestion_log_purge_runs():
    """ingestion_log_purge deletes entries older than the given days threshold."""
    truncate_database()
    ingestion_log_purge(days=0)


def test_ingestion_log_purge_db_error_swallowed():
    """SQLAlchemyError in ingestion_log_purge must not propagate."""
    with patch("core.log.create_session") as mock_session_factory:
        factory = MagicMock()
        mock_session_factory.return_value = factory
        factory.registry.has.return_value = False
        factory.return_value.query.side_effect = OperationalError("", {}, Exception())
        ingestion_log_purge(days=30)  # must not raise
    factory.remove.assert_called_once()


def test_system_log_purge_releases_scoped_session():
    """Standalone maintenance must not retain a thread-local SQLAlchemy session."""
    with patch("core.log.SystemLogWriter") as mock_svc_cls, \
         patch("core.log.create_session") as mock_session_factory:
        factory = MagicMock()
        mock_session_factory.return_value = factory
        factory.registry.has.return_value = False
        mock_svc_cls.return_value.delete_by_timestamp.return_value = 0
        system_log_purge(days=30)
    factory.remove.assert_called_once()


def test_system_log_keeps_a_request_owned_scoped_session():
    """system_log must not detach ORM rows owned by an active request."""
    with patch("core.log.SystemLogWriter"), \
         patch("core.log.create_session") as mock_session_factory:
        factory = MagicMock()
        mock_session_factory.return_value = factory
        factory.registry.has.return_value = True
        system_log("ev", "msg")
    factory.remove.assert_not_called()
