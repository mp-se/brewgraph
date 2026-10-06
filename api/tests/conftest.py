# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Pytest configuration and shared fixtures."""
import gc
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from tests.test_db_env import DEFAULT_TEST_DATABASE_URL
from core.db import engine
from core.models import Base
from main_oss import app


@pytest.fixture(scope="session", autouse=True)
def recreate_tables():
    """Drop and recreate all tables so schema changes are always applied."""
    dev_db_url = "sqlite:///./brewgraph.sqlite"
    resolved = str(engine.url)
    assert resolved != dev_db_url, (
        f"DATABASE_URL resolved to the dev database ({dev_db_url}); "
        f"this fixture drops every table. Unset DATABASE_URL to use the "
        f"isolated test default ({DEFAULT_TEST_DATABASE_URL}) or point it "
        f"at a dedicated test database."
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def disable_ingest_throttle():
    """Disable Redis-based ingest throttling and IP rate limiting for all tests.

    Every ``core.cache`` call ``api_key_auth`` makes must be stubbed here, including
    ``delete_key`` (it clears the failure counter on a *successful* key check). An
    unstubbed call needs a live Redis: it passes on a developer machine that has one,
    and times out in CI where none exists — worst for tests that patch
    ``core.utils.socket.getaddrinfo``, which is the global ``socket`` function, so
    Redis's own hostname lookup gets redirected to the fake device address too.
    """
    with patch("oss.routers.ingest._check_throttle"), \
         patch("core.middleware.auth.exist_key", return_value=False), \
         patch("core.middleware.auth.increment_key", return_value=0), \
         patch("core.middleware.auth.delete_key"):
        yield


@pytest.fixture()
def app_client():
    """App client."""
    with TestClient(app, base_url="http://testserver/api") as client:
        yield client


@pytest.fixture
def root_client():
    """App client rooted at the origin, not at /api.

    Needed for endpoints mounted outside the /api prefix — currently the SSE
    stream at GET /events. `app_client` cannot reach them: httpx resolves
    request paths against its base_url, so "/events" there becomes "/api/events".
    """
    with TestClient(app, base_url="http://testserver") as client:
        yield client


def truncate_database():
    """Truncate all application tables."""
    print("Truncate all tables")
    # Force GC so unreferenced sqlite3.Connection objects (from prior requests)
    # release their file handles before we attempt a write lock via DELETE.
    gc.collect()
    engine.dispose()
    # device.batch_id, device.vessel_id and tap.device_id are the use_alter=True columns
    # that break the batch/device/vessel/tap FK cycle at DDL time (see the models' own
    # comments) — no DELETE order below can satisfy a real cycle, so null them out first.
    # SQLite has no PRAGMA foreign_keys here, so it never enforced the cycle and this went
    # unnoticed: `DELETE FROM batch` before `device` silently left orphaned device rows
    # instead of raising. Postgres enforces it, catches the violation in the except below,
    # and — because the delete never actually ran — leaks that test's rows into the next
    # one. Two symptoms of the same bug: an unexpected surviving Batch row, and duplicate
    # Tap rows from an earlier test.
    cycle_breakers = [
        ("device", "batch_id"),
        ("device", "vessel_id"),
        ("tap", "device_id"),
    ]
    with engine.connect() as con:
        for table, column in cycle_breakers:
            try:
                con.execute(text(f"UPDATE {table} SET {column} = NULL"))
                con.commit()
            except SQLAlchemyError as e:
                con.rollback()
                print(f"Could not clear {table}.{column}: {e}")
    # Dependency order (leaves first), after the cycle breakers above are cleared:
    # readings/notes/predictions reference batch/device/storage_vessel/tap and nothing
    # references them back, so they go first; storage_vessel references batch/tap so it
    # must be deleted before both; device has no remaining incoming references once the
    # readings above are gone. `storage_vessel` used to sit before `gravity_reading`/
    # `pressure_reading` here, which is backwards (both reference `vessel_id`) — SQLite
    # never caught it for the same PRAGMA foreign_keys reason as the cycle above.
    tables = [
        "batch_dry_hop",
        "batch_note",
        "fermentation_step",
        "gravity_reading",
        "pour_event",
        "prediction",
        "pressure_reading",
        "temp_reading",
        "device",
        "storage_vessel",
        "batch",
        "tap",
        "integration",
        "system_log",
        "ingestion_log",
        "tenant_settings",
    ]
    with engine.connect() as con:
        for table in tables:
            try:
                con.execute(text(f"DELETE FROM {table}"))
                con.commit()
            except SQLAlchemyError as e:
                con.rollback()
                print(f"Could not truncate {table}: {e}")


# Shared device field defaults reused across test modules.
DEVICE_DEFAULTS = {
    "deviceType": "gravitymon",
    "mdns": "",
    "description": "",
    "chipFamily": "ESP32",
    "url": "",
    "config": "",
    "deviceColor": "white",
    "collectLogs": False,
}
