# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/extensions/throttle.py — throttle extension point."""
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from core.middleware.auth import AuthContext, ingest_auth
from oss.extensions.throttle import ThrottleLimits, oss_throttle_provider


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/throttle")
    def get_throttle(limits: ThrottleLimits = Depends(oss_throttle_provider)):
        return {
            "pre_auth_per_minute": limits.pre_auth_per_minute,
            "per_device_min_interval_seconds": limits.per_device_min_interval_seconds,
        }

    return app


def test_default_throttle_is_fixed_and_permissive():
    """Returns the same fixed limits for every caller."""
    client = TestClient(_make_app())
    resp = client.get("/throttle")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pre_auth_per_minute"] == 120
    assert body["per_device_min_interval_seconds"] == 0


def test_throttle_provider_override_applies():
    """dependency_overrides substitutes the throttle limits at the call site."""
    app = _make_app()
    app.dependency_overrides[oss_throttle_provider] = lambda: ThrottleLimits(
        pre_auth_per_minute=10, per_device_min_interval_seconds=30
    )
    client = TestClient(app)
    resp = client.get("/throttle")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pre_auth_per_minute"] == 10
    assert body["per_device_min_interval_seconds"] == 30


def _make_ingest_auth_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ingest-auth")
    def get_ingest_auth(auth: AuthContext = Depends(ingest_auth)):
        return {"ingest_interval_seconds": auth.ingest_interval_seconds}

    return app


def test_ingest_auth_uses_throttle_provider_interval():
    """ingest_auth's interval comes from the throttle provider, not a hardcoded default."""
    app = _make_ingest_auth_app()
    app.dependency_overrides[oss_throttle_provider] = lambda: ThrottleLimits(
        pre_auth_per_minute=2, per_device_min_interval_seconds=99
    )
    with patch("core.middleware.auth.exist_key", return_value=False), \
         patch("core.middleware.auth.increment_key", return_value=0):
        client = TestClient(app)
        resp = client.get("/ingest-auth")
    assert resp.status_code == 200
    assert resp.json()["ingest_interval_seconds"] == 99


def test_ingest_auth_rate_limit_trips_at_provider_value_not_hardcoded_120():
    """The pre-auth rate limit trip point tracks the throttle provider, not the old constant."""
    app = _make_ingest_auth_app()
    app.dependency_overrides[oss_throttle_provider] = lambda: ThrottleLimits(
        pre_auth_per_minute=2, per_device_min_interval_seconds=0
    )
    with patch("core.middleware.auth.exist_key", return_value=False), \
         patch("core.middleware.auth.increment_key", return_value=2), \
         patch("core.middleware.auth.system_log_security"):
        client = TestClient(app)
        resp = client.get("/ingest-auth")
    assert resp.status_code == 429
