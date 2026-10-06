# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for /api/tenant/settings endpoints."""
from unittest.mock import MagicMock

from core.config import get_settings
from oss.precision import DECIMALS
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def test_init():
    """Reset database state before test scenarios."""
    truncate_database()


def test_get_tenant_settings(app_client):
    """GET /tenant returns tenant settings."""
    r = app_client.get("/tenant/settings", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "temperatureFormat" in data
    assert "gravityFormat" in data
    assert data["precision"] == DECIMALS


def test_update_tenant_settings(app_client):
    """PATCH /tenant updates and returns updated settings."""
    r = app_client.patch(
        "/tenant/settings",
        json={"temperatureFormat": "f", "gravityFormat": "p"},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["temperatureFormat"] == "f"
    assert data["gravityFormat"] == "p"


def test_update_tenant_settings_includes_public_display_presentation(app_client):
    """Authenticated settings owns OSS display branding, never an access gate."""
    r = app_client.patch(
        "/tenant/settings",
        json={
            "breweryName": "Sunset Brewing",
            "logoUrl": "https://example.com/logo.png",
            "theme": "minimal",
            "primaryColor": "#f59e0b",
        },
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["breweryName"] == "Sunset Brewing"
    assert data["logoUrl"] == "https://example.com/logo.png"
    assert data["theme"] == "minimal"
    assert data["primaryColor"] == "#f59e0b"


def test_update_tenant_settings_ignores_precision(app_client):
    """PATCH /tenant cannot alter precision -- it is not a field on TenantSettingsUpdate."""
    r = app_client.patch(
        "/tenant/settings",
        json={"temperatureFormat": "c", "precision": {"temperature": 99}},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["precision"] == DECIMALS


def test_get_tenant_settings_404_when_no_settings(app_client):
    """GET /tenant returns 404 when no settings record exists."""
    from main_oss import app  # pylint: disable=import-outside-toplevel
    from oss.services import get_settings_service  # pylint: disable=import-outside-toplevel

    mock_svc = MagicMock()
    mock_svc.list.return_value = []
    app.dependency_overrides[get_settings_service] = lambda: mock_svc
    try:
        r = app_client.get("/tenant/settings", headers=headers)
    finally:
        app.dependency_overrides.pop(get_settings_service, None)
    assert r.status_code == 404
    assert r.json()["message"] == "settings_not_found"


def test_update_tenant_settings_404_when_no_settings(app_client):
    """PATCH /tenant returns 404 when no settings record exists."""
    from main_oss import app  # pylint: disable=import-outside-toplevel
    from oss.services import get_settings_service  # pylint: disable=import-outside-toplevel

    mock_svc = MagicMock()
    mock_svc.list.return_value = []
    app.dependency_overrides[get_settings_service] = lambda: mock_svc
    try:
        r = app_client.patch("/tenant/settings", json={"temperatureFormat": "c"}, headers=headers)
    finally:
        app.dependency_overrides.pop(get_settings_service, None)
    assert r.status_code == 404


def test_tenant_auth_required(app_client):
    """GET /tenant requires auth."""
    r = app_client.get("/tenant/settings")
    assert r.status_code == 401
