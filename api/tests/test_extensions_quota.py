# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/extensions/quota.py — quota extension point."""
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from oss.extensions.quota import QUOTA_RESOURCES, oss_quota_provider


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/quota/{resource}")
    def get_quota(resource: str, limiter=Depends(oss_quota_provider)):
        return {"limit": limiter(resource)}

    return app


def test_default_quota_is_unlimited_for_every_resource():
    """Returns -1 (unlimited) for every declared resource."""
    client = TestClient(_make_app())
    for resource in QUOTA_RESOURCES:
        resp = client.get(f"/quota/{resource}")
        assert resp.status_code == 200
        assert resp.json()["limit"] == -1


def test_quota_provider_override_applies():
    """dependency_overrides substitutes the resource->limit lookup at the call site."""
    app = _make_app()
    app.dependency_overrides[oss_quota_provider] = lambda: (lambda _resource: 5)
    client = TestClient(app)
    resp = client.get("/quota/batches")
    assert resp.status_code == 200
    assert resp.json()["limit"] == 5
