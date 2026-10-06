# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for system endpoints."""
import json
import uuid

from core.config import get_settings
from core.db import create_session
from core.enums import IngestionSource
from core.models.platform import IngestionLog
from core.models.registry import resolve_model
from oss.schemas.device import DeviceCreate
from oss.services.device import DeviceService
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def test_init():
    """Reset database state before test scenarios."""
    truncate_database()


def test_health(app_client):
    """Test /system/health endpoint."""
    r = app_client.get("/system/health")
    assert r.status_code == 200
    data = json.loads(r.text)
    assert data["status"] == "ok"


def test_root_health(app_client):
    """Test /health root endpoint."""
    r = app_client.get("http://testserver/health")
    assert r.status_code == 200
    data = json.loads(r.text)
    assert data["status"] == "ok"


def test_info(app_client):
    """Test /system/info endpoint."""
    r = app_client.get("/system/info", headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert "version" in data
    assert data["version"] == "2.0.0"
    assert "databaseOk" in data


def test_get_settings(app_client):
    """Test GET /tenant/settings."""
    r = app_client.get("/tenant/settings", headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert "temperatureFormat" in data
    assert "gravityFormat" in data


def test_update_settings(app_client):
    """Test PATCH /tenant/settings."""
    app_client.get("/tenant/settings", headers=headers)

    update = {
        "temperatureFormat": "f",
        "pressureFormat": "kpa",
        "gravityFormat": "p",
        "volumeFormat": "metric",
    }
    r = app_client.patch("/tenant/settings", json=update, headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert data["temperatureFormat"] == "f"
    assert data["gravityFormat"] == "p"


def test_system_log_list(app_client):
    """Test GET /system/logs."""
    r = app_client.get("/system/logs", headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert "items" in data
    assert "hasMore" in data
    assert "nextCursor" in data
    assert isinstance(data["items"], list)


def test_system_log_pagination(app_client):
    """Test system log pagination."""
    r = app_client.get("/system/logs?limit=2", headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert len(data["items"]) <= 2
    assert isinstance(data["hasMore"], bool)


def test_ingest_errors_list(app_client):
    """Test GET /system/ingestion."""
    r = app_client.get("/system/ingestion", headers=headers)
    assert r.status_code == 200
    data = json.loads(r.text)
    assert "items" in data
    assert "hasMore" in data
    assert isinstance(data["items"], list)


def test_auth_required(app_client):
    """Test that auth is required for protected endpoints."""
    r = app_client.get("/tenant/settings")
    assert r.status_code == 401

    r = app_client.get("/system/logs")
    assert r.status_code == 401


def test_self_test(app_client):
    """GET /system/self-test returns database status and job list."""
    r = app_client.get("/system/self-test", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "databaseConnection" in data
    assert "backgroundJobs" in data
    assert "log" in data
    assert data["databaseConnection"] is True


def test_scheduler_status(app_client):
    """GET /system/scheduler returns a list of scheduled jobs."""
    r = app_client.get("/system/scheduler", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)




def test_ingest_errors_pagination(app_client):
    """GET /system/ingestion?limit=5 honours pagination."""
    r = app_client.get("/system/ingestion?limit=5", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) <= 5
    assert "nextCursor" in data


def test_ingest_errors_include_device_id(app_client):
    """GET /system/ingestion exposes deviceId — populated when set, null otherwise."""
    truncate_database()
    session = create_session()
    known_device_id = uuid.uuid4()
    try:
        session.add(IngestionLog(
            device_id=known_device_id,
            source_type=IngestionSource.GRAVITY,
            device_type="gravitymon",
            ip_address="127.0.0.1",
            reason="unknown_token",
        ))
        session.add(IngestionLog(
            device_id=None,
            source_type=IngestionSource.PRESSURE,
            device_type="pressuremon",
            ip_address="127.0.0.1",
            reason="unknown_token",
        ))
        session.commit()
    finally:
        session.close()

    r = app_client.get("/system/ingestion", headers=headers)
    assert r.status_code == 200
    entries = r.json()["items"]
    assert len(entries) == 2
    by_device = {str(known_device_id): False, "null": False}
    for entry in entries:
        assert "deviceId" in entry
        if entry["deviceId"] == str(known_device_id):
            by_device[str(known_device_id)] = True
        elif entry["deviceId"] is None:
            by_device["null"] = True
    assert all(by_device.values())


def test_get_settings_no_settings_returns_404(app_client):
    """GET /tenant/settings returns 404 when no tenant settings record exists."""
    from unittest.mock import \
        MagicMock  # pylint: disable=import-outside-toplevel

    from oss.services import \
        get_settings_service  # pylint: disable=import-outside-toplevel
    from main_oss import app  # pylint: disable=import-outside-toplevel

    mock_svc = MagicMock()
    mock_svc.list.return_value = []
    app.dependency_overrides[get_settings_service] = lambda: mock_svc
    try:
        r = app_client.get("/tenant/settings", headers=headers)
    finally:
        app.dependency_overrides.pop(get_settings_service, None)
    assert r.status_code == 404


def test_update_settings_no_settings_returns_404(app_client):
    """PATCH /tenant/settings returns 404 when no tenant settings record exists."""
    from unittest.mock import \
        MagicMock  # pylint: disable=import-outside-toplevel

    from oss.services import \
        get_settings_service  # pylint: disable=import-outside-toplevel
    from main_oss import app  # pylint: disable=import-outside-toplevel

    mock_svc = MagicMock()
    mock_svc.list.return_value = []
    app.dependency_overrides[get_settings_service] = lambda: mock_svc
    try:
        r = app_client.patch("/tenant/settings", json={"temperatureFormat": "f"}, headers=headers)
    finally:
        app.dependency_overrides.pop(get_settings_service, None)
    assert r.status_code == 404


def test_self_test_redis_exception_path(app_client):
    """self_test swallows exceptions from Redis and still returns 200."""
    from unittest.mock import patch  # pylint: disable=import-outside-toplevel
    with patch("oss.routers.system.write_key", side_effect=Exception("redis down")):
        r = app_client.get("/system/self-test", headers=headers)
    assert r.status_code == 200
    assert r.json()["databaseConnection"] is True


def test_self_test_with_log_cache_keys(app_client):
    """self_test returns log entries for cached log_* keys."""
    from unittest.mock import (  # pylint: disable=import-outside-toplevel
        MagicMock, patch)
    mock_val = MagicMock()
    mock_val.decode.return_value = "some-value"
    with patch("oss.routers.system.find_key", return_value=[b"log_device_abc"]), \
         patch("oss.routers.system.read_key", return_value=mock_val):
        r = app_client.get("/system/self-test", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["log"], list)
    assert len(data["log"]) >= 1
    # The scanner does not write `ble_*` keys, so there is no `ble` array.
    # Asserted absent, not merely unused: a reinstated field would be permanently empty.
    assert "ble" not in data


def test_self_test_db_error_path(app_client):
    """self_test sets databaseConnection=False when DB raises SQLAlchemyError."""
    from unittest.mock import MagicMock, patch  # pylint: disable=import-outside-toplevel
    from sqlalchemy.exc import SQLAlchemyError  # pylint: disable=import-outside-toplevel

    mock_svc = MagicMock()
    mock_svc.list.side_effect = SQLAlchemyError("db down")
    with patch("oss.routers.system.TenantSettingsService", return_value=mock_svc):
        r = app_client.get("/system/self-test", headers=headers)
    assert r.status_code == 200
    assert r.json()["databaseConnection"] is False


def test_system_info_db_error_path(app_client):
    """GET /system/info returns databaseOk=False when DB raises SQLAlchemyError."""
    from unittest.mock import MagicMock  # pylint: disable=import-outside-toplevel
    from sqlalchemy.exc import SQLAlchemyError  # pylint: disable=import-outside-toplevel
    from main_oss import app  # pylint: disable=import-outside-toplevel
    from oss.services import get_settings_service  # pylint: disable=import-outside-toplevel

    mock_svc = MagicMock()
    mock_svc.list.side_effect = SQLAlchemyError("db down")
    app.dependency_overrides[get_settings_service] = lambda: mock_svc
    try:
        r = app_client.get("/system/info", headers=headers)
    finally:
        app.dependency_overrides.pop(get_settings_service, None)
    assert r.status_code == 200
    assert r.json()["databaseOk"] is False


def test_system_logs_db_error_returns_empty(app_client):
    """GET /system/logs returns empty list when DB raises SQLAlchemyError."""
    from unittest.mock import MagicMock  # pylint: disable=import-outside-toplevel
    from sqlalchemy.exc import SQLAlchemyError  # pylint: disable=import-outside-toplevel

    mock_session = MagicMock()
    mock_session.query.return_value.count.side_effect = SQLAlchemyError("db error")
    from core.db import get_session  # pylint: disable=import-outside-toplevel
    from main_oss import app  # pylint: disable=import-outside-toplevel
    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        r = app_client.get("/system/logs", headers=headers)
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert r.status_code == 200
    data = r.json()
    assert data["hasMore"] == 0
    assert data["items"] == []


def test_ingestion_logs_db_error_returns_empty(app_client):
    """GET /system/ingestion returns empty list when DB raises SQLAlchemyError."""
    from unittest.mock import MagicMock  # pylint: disable=import-outside-toplevel
    from sqlalchemy.exc import SQLAlchemyError  # pylint: disable=import-outside-toplevel
    from core.db import get_session  # pylint: disable=import-outside-toplevel
    from main_oss import app  # pylint: disable=import-outside-toplevel

    mock_session = MagicMock()
    mock_session.query.return_value.count.side_effect = SQLAlchemyError("db error")
    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        r = app_client.get("/system/ingestion", headers=headers)
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert r.status_code == 200
    data = r.json()
    assert data["hasMore"] == 0
    assert data["items"] == []


def test_self_test_redis_success_path(app_client):
    """self_test returns redisConnection=True when the Redis round-trip succeeds."""
    from unittest.mock import patch  # pylint: disable=import-outside-toplevel

    with patch("oss.routers.system.write_key"), \
         patch("oss.routers.system.read_key", return_value=b"testing"):
        r = app_client.get("/system/self-test", headers=headers)
    assert r.status_code == 200
    assert r.json()["redisConnection"] is True


def test_purge_deleted_hard_deletes_a_soft_deleted_row(app_client):
    """POST /system/purge-deleted removes a soft-deleted row for real.

    This is what frees a device's (device_type, chip_id) unique constraint for
    restore: soft-delete alone leaves the row in place, still occupying the
    constraint, so recreating the same device during restore would conflict.
    """
    truncate_database()
    session = create_session()
    device = DeviceService(session).create(
        DeviceCreate(name="PurgeTest", device_type="ispindel", chip_id="chip-purge-1")
    )
    device_id = device.id
    DeviceService(session).soft_delete(device_id)

    r = app_client.post("/system/purge-deleted", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    verify_session = create_session()
    assert verify_session.get(resolve_model("Device"), device_id) is None


def test_purge_deleted_leaves_active_rows_untouched(app_client):
    """POST /system/purge-deleted must not touch a row that was never deleted."""
    truncate_database()
    session = create_session()
    device = DeviceService(session).create(
        DeviceCreate(name="KeepMe", device_type="ispindel", chip_id="chip-keep-1")
    )
    device_id = device.id

    r = app_client.post("/system/purge-deleted", headers=headers)
    assert r.status_code == 200

    verify_session = create_session()
    assert verify_session.get(resolve_model("Device"), device_id) is not None


def test_purge_deleted_requires_auth(app_client):
    """POST /system/purge-deleted is behind api_key_auth like the rest of /system."""
    r = app_client.post("/system/purge-deleted")
    assert r.status_code in (401, 403)
