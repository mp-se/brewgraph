# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/extensions/tenant.py — tenant extension point."""
import uuid

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from oss.extensions.tenant import DEFAULT_TENANT_ID, oss_tenant_provider


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/tenant")
    def get_tenant(tenant_id=Depends(oss_tenant_provider)):
        return {"tenant_id": str(tenant_id)}

    return app


def test_default_tenant_is_the_single_constant():
    """This app is single-tenant: every request resolves to DEFAULT_TENANT_ID."""
    client = TestClient(_make_app())
    resp = client.get("/tenant")
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == str(DEFAULT_TENANT_ID)


def test_default_tenant_is_the_nil_uuid():
    """The constant must be a real UUID, not a string.

    It is written to the tenant_id column, which is Uuid, so a string sentinel cannot be
    used as a column default. The nil UUID also cannot collide with any row's own id —
    those come from uuid4.
    """
    assert isinstance(DEFAULT_TENANT_ID, uuid.UUID)
    assert DEFAULT_TENANT_ID == uuid.UUID(int=0)


def test_tenant_provider_override_applies():
    """dependency_overrides substitutes tenant resolution at the call site."""
    app = _make_app()
    app.dependency_overrides[oss_tenant_provider] = lambda: "org_acme"
    client = TestClient(app)
    resp = client.get("/tenant")
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "org_acme"
