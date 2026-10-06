# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

# pylint: disable=protected-access
"""Direct unit tests for BaseService CRUD methods."""
from unittest.mock import patch

import pytest
import sqlalchemy
from starlette.exceptions import HTTPException

from core.db import create_session
from oss.schemas.platform import SystemLogCreate
from oss.services.platform import SystemLogService
from tests.conftest import truncate_database


def _svc():
    return SystemLogService(create_session())


def _entry(event="ev", message="msg"):
    return SystemLogCreate(event=event, message=message, level="INFO")


# ---------------------------------------------------------------------------
# list_page
# ---------------------------------------------------------------------------

def test_list_page_returns_first_page():
    """list_page returns the first page of results with correct total count."""
    truncate_database()
    svc = _svc()
    for i in range(5):
        svc.create(_entry(event=f"ev{i}"))
    items, total = svc.list_page(page=1, page_size=3)
    assert total == 5
    assert len(items) == 3


def test_list_page_returns_second_page():
    """list_page returns the second page with remaining items."""
    truncate_database()
    svc = _svc()
    for i in range(5):
        svc.create(_entry(event=f"ev{i}"))
    items, total = svc.list_page(page=2, page_size=3)
    assert total == 5
    assert len(items) == 2


def test_list_page_empty():
    """list_page returns empty items and zero total when no records exist."""
    truncate_database()
    items, total = _svc().list_page()
    assert total == 0
    assert not items


# ---------------------------------------------------------------------------
# no generic hard delete
# ---------------------------------------------------------------------------

def test_base_service_offers_no_generic_hard_delete():
    """`BaseService` must not expose a `delete()` every service inherits.

    Anything carrying `deleted_at` is soft-deleted on the request path and hard-deleted
    only by a scheduled job. A generic hard delete on the base class is the easiest way
    to lose that property by accident — the next service that wants a delete finds it
    first and reaches for it.
    """
    assert not hasattr(_svc(), "delete"), (
        "BaseService grew a generic delete() again — hard deletes belong in jobs"
    )


def test_filter_for_model_rejects_unpersistable_schema_field():
    """A schema/model mismatch must not produce a successful lossy write."""
    with pytest.raises(ValueError, match="unmapped_field"):
        _svc()._filter_for_model({"event": "ev", "unmapped_field": "lost"})


# ---------------------------------------------------------------------------
# create / create_list — every IntegrityError is translated to a 409
# ---------------------------------------------------------------------------

def test_create_integrity_error_translated_to_409():
    """Any IntegrityError at commit is translated to a 409, not re-raised.

    `create()`/`create_list()` must translate every IntegrityError from commit
    into a 409 unconditionally — gating on a `"duplicate key" in str(e)`
    substring check would silently pass through on SQLite (this app's actual
    dialect), whose message is "UNIQUE constraint failed", not Postgres's.
    This matches `BaseService.commit()`'s ungated behavior.
    """
    svc = _svc()
    orig_exc = sqlalchemy.exc.IntegrityError("stmt", {}, Exception("constraint"))
    with patch.object(svc.db_session, "commit", side_effect=orig_exc):
        with pytest.raises(HTTPException) as exc_info:
            svc.create(_entry())
    assert exc_info.value.status_code == 409


def test_create_list_integrity_error_translated_to_409():
    """Bulk writes translate every database integrity failure to a 409.

    SQLite reports a unique violation as ``UNIQUE constraint failed`` rather
    than PostgreSQL's ``duplicate key``; error translation must not depend on
    a dialect-specific substring.
    """
    svc = _svc()
    orig_exc = sqlalchemy.exc.IntegrityError("stmt", {}, Exception("constraint"))
    with patch.object(svc.db_session, "commit", side_effect=orig_exc):
        with pytest.raises(HTTPException) as exc_info:
            svc.create_list([_entry()])
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# _search_by_filter
# ---------------------------------------------------------------------------

def test_search_by_filter_returns_matching_entries():
    """_search_by_filter returns only entries that match the given filter dict."""
    truncate_database()
    svc = _svc()
    svc.create(_entry(event="find_me"))
    svc.create(_entry(event="ignore_me"))
    results = svc._search_by_filter({"event": "find_me"})
    assert len(results) == 1
    assert results[0].event == "find_me"


def test_search_by_filter_empty_when_no_match():
    """_search_by_filter returns empty list when no entries match the filter."""
    truncate_database()
    svc = _svc()
    svc.create(_entry(event="only_this"))
    results = svc._search_by_filter({"event": "nonexistent"})
    assert results == []
