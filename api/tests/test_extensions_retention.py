# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/extensions/retention.py — retention extension point."""
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from core.middleware.auth import AuthContext, api_key_auth
from oss.extensions.retention import oss_retention_provider


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/cutoff")
    def get_cutoff(cutoff=Depends(oss_retention_provider)):
        return {"cutoff": cutoff.isoformat() if cutoff else None}

    return app


def test_default_retention_keeps_everything():
    """Default (retention_days=-1 on AuthContext) yields no cutoff."""
    app = _make_app()
    app.dependency_overrides[api_key_auth] = AuthContext
    client = TestClient(app)
    resp = client.get("/cutoff")
    assert resp.status_code == 200
    assert resp.json()["cutoff"] is None


def test_retention_provider_override_applies():
    """dependency_overrides substitutes the retention cutoff at the call site."""
    app = _make_app()
    fixed_cutoff = datetime(2020, 1, 1, tzinfo=timezone.utc)
    app.dependency_overrides[oss_retention_provider] = lambda: fixed_cutoff
    client = TestClient(app)
    resp = client.get("/cutoff")
    assert resp.status_code == 200
    assert resp.json()["cutoff"] == fixed_cutoff.isoformat()
