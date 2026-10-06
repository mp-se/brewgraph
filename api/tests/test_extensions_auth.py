# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/extensions/auth.py — auth extension point."""
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from core.config import get_settings
from core.middleware.auth import AuthContext
from oss.extensions.auth import oss_auth_provider
from oss.extensions.quota import oss_quota_provider


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    def whoami(auth: AuthContext = Depends(oss_auth_provider)):
        return {"batches": auth.quota_limit("batches")}

    return app


def test_default_auth_resolves_shared_api_key_permissively():
    """The default provider accepts the configured API key and grants unlimited quota."""
    client = TestClient(_make_app())
    headers = {"Authorization": "Bearer " + get_settings().api_key.get_secret_value()}
    resp = client.get("/whoami", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["batches"] == -1


def test_auth_provider_override_applies():
    """dependency_overrides substitutes identity resolution at the call site."""
    app = _make_app()
    app.dependency_overrides[oss_auth_provider] = lambda: AuthContext(quota_limits={"batches": 3})
    client = TestClient(app)
    resp = client.get("/whoami")
    assert resp.status_code == 200
    assert resp.json()["batches"] == 3


def test_quota_provider_flows_through_real_auth_provider():
    """The quota extension affects the provider routers use, not just a toy route."""
    app = _make_app()
    app.dependency_overrides[oss_quota_provider] = lambda: (lambda _resource: 2)
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + get_settings().api_key.get_secret_value()}
    resp = client.get("/whoami", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["batches"] == 2
