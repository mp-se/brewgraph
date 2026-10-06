# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Extended ingest router tests — dispatch, kegmon, parse errors, and throttle."""
import hashlib
import uuid as _uuid
from unittest.mock import patch

import pytest
from starlette.exceptions import HTTPException

from core.config import get_settings
from core.db import get_session
from core.models.registry import resolve_model
from oss.routers.ingest import (
    _check_device_request_quota,
    _check_throttle,
    _throttle_budget,
    _detect_device_type,
)
from tests.conftest import DEVICE_DEFAULTS, truncate_database

Tap = resolve_model("Tap")

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

GRAVITY_PAYLOAD = {
    "name": "GravityMon",
    "id": "DISP01",
    "interval": 10,
    "temperature": 20.0,
    "temp_units": "C",
    "gravity": 1.050,
    "angle": 34.0,
    "battery": 3.85,
    "rssi": -76,
    "gravity-unit": "G",
}

PRESSURE_PAYLOAD = {
    "name": "PressureMon",
    "id": "PRES01",
    "interval": 10,
    "temperature": 21.0,
    "pressure": 14.7,
    "pressure_units": "psi",
    "temp_units": "C",
    "battery": 3.5,
    "rssi": -80,
}


def _create_device(app_client, chip_id: str, device_type: str = "gravitymon") -> dict:
    data = {
        "name": f"Device {chip_id}",
        "deviceType": device_type,
        "chipId": chip_id,
        **DEVICE_DEFAULTS,
    }
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


def _create_tap_with_token(app_client, token: str = "kegmon-test-token") -> dict:
    """Create a tap and set its token via ORM session (no HTTP token endpoint for taps).

    token_hash must be kept in sync with token here too — ingest resolution looks
    up taps by hashed token (see TapService.find_by_token), so setting token alone
    would make the tap unresolvable via the ingest endpoints under test.
    """
    r = app_client.post("/taps", json={"name": "Test Tap", "tapNumber": 1}, headers=headers)
    assert r.status_code == 201
    tap_id = r.json()["id"]
    db = next(get_session())
    tap = db.get(Tap, _uuid.UUID(tap_id))
    tap.token = token
    tap.token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.commit()
    return {"id": tap_id, "token": token}


# ---------------------------------------------------------------------------
# _detect_device_type unit tests (no HTTP)
# ---------------------------------------------------------------------------

def test_detect_gravitymon():
    """Returns 'gravitymon' when the payload has gravity-unit, even alongside gravity."""
    assert _detect_device_type({"gravity": 1.050, "gravity-unit": "G"}) == "gravitymon"


def test_detect_pressuremon():
    """Returns 'pressuremon' when payload contains pressure or pressure_units key."""
    assert _detect_device_type({"pressure": 14.7}) == "pressuremon"
    assert _detect_device_type({"pressure_units": "psi"}) == "pressuremon"


def test_detect_kegmon():
    """Returns 'kegmon' when payload contains the absolute-volume keys."""
    assert _detect_device_type({"volume": 10.0, "maxVolume": 19.0}) == "kegmon"


def test_detect_unknown_returns_none():
    """An unrecognized payload is not silently treated as iSpindel."""
    assert _detect_device_type({"name": "iSpindel"}) is None


# ---------------------------------------------------------------------------
# _check_throttle unit test (bypasses autouse patch)
# ---------------------------------------------------------------------------

def test_check_throttle_raises_429_when_key_exists():
    """_check_throttle raises HTTP 429 when set_key_if_absent loses the atomic claim."""
    with patch("oss.routers.ingest.set_key_if_absent", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            _check_throttle("device-abc", 60)
        assert exc_info.value.status_code == 429


def test_check_throttle_writes_key_when_not_throttled():
    """_check_throttle atomically claims the cache key when no throttle is active.

    It must go through the single `set_key_if_absent` claim rather than a
    separate `read_key` then `write_key` — two round-trips race two concurrent
    requests, exactly the failure §8 closes.
    """
    with patch("oss.routers.ingest.set_key_if_absent", return_value=True) as mock_claim:
        _check_throttle("device-xyz", 30)
        mock_claim.assert_called_once_with("ingest_throttle_device-xyz", "1", ttl=30)


def test_check_throttle_disabled_when_min_interval_zero():
    """min_interval<=0 (the permissive default) must skip the atomic claim
    entirely — calling write_key(key, "1", ttl=0) raises Redis's ResponseError
    for an invalid expire time.
    """
    with patch("oss.routers.ingest.set_key_if_absent") as mock_claim:
        _check_throttle("device-permissive", 0)
        mock_claim.assert_not_called()

        # Negative interval should behave identically (defensive).
        _check_throttle("device-permissive", -1)
        mock_claim.assert_not_called()


# ---------------------------------------------------------------------------
# _throttle_budget — the claimed interval is released when the reading is rejected
# ---------------------------------------------------------------------------

@pytest.fixture(name="real_throttle")
def _real_throttle():
    """Undo conftest's autouse ``_check_throttle`` patch for these tests.

    The autouse patch exists so route tests aren't rate limited. These tests are
    about the throttle itself, so they need the real claim to run — otherwise the
    429 case can never fire and the test passes vacuously.
    """
    with patch("oss.routers.ingest._check_throttle", _check_throttle):
        yield


@pytest.mark.usefixtures("real_throttle")
def test_throttle_budget_keeps_key_when_reading_accepted():
    """A handler that returns normally keeps its claimed interval."""
    with patch("oss.routers.ingest.set_key_if_absent", return_value=True), \
         patch("oss.routers.ingest.delete_key") as mock_delete:
        with _throttle_budget("device-ok", 60):
            pass
        mock_delete.assert_not_called()


@pytest.mark.usefixtures("real_throttle")
@pytest.mark.parametrize("status", [401, 409, 422, 503])
def test_throttle_budget_releases_key_when_reading_rejected(status):
    """A rejected reading stores nothing, so it must not cost the full interval:
    the claimed key must be released immediately, not held until expiry —
    otherwise a conflicting pour or an unusable payload locks the device out
    for an interval it never used, indistinguishable from a real rate limit
    from the device's side.
    """
    with patch("oss.routers.ingest.set_key_if_absent", return_value=True), \
         patch("oss.routers.ingest.delete_key") as mock_delete:
        with pytest.raises(HTTPException):
            with _throttle_budget("device-reject", 60):
                raise HTTPException(status_code=status, detail="nope")
        mock_delete.assert_called_once_with("ingest_throttle_device-reject")


@pytest.mark.usefixtures("real_throttle")
def test_throttle_budget_does_not_release_on_429():
    """A 429 must not clear the key that produced it — a throttle undoing itself."""
    with patch("oss.routers.ingest.set_key_if_absent", return_value=True), \
         patch("oss.routers.ingest.delete_key") as mock_delete:
        with pytest.raises(HTTPException):
            with _throttle_budget("device-429", 60):
                raise HTTPException(status_code=429, detail="throttled")
        mock_delete.assert_not_called()


@pytest.mark.usefixtures("real_throttle")
def test_throttle_budget_releases_key_on_unexpected_error():
    """A non-HTTP failure stored nothing either — release, then re-raise unchanged."""
    with patch("oss.routers.ingest.set_key_if_absent", return_value=True), \
         patch("oss.routers.ingest.delete_key") as mock_delete:
        with pytest.raises(RuntimeError):
            with _throttle_budget("device-boom", 60):
                raise RuntimeError("db went away")
        mock_delete.assert_called_once_with("ingest_throttle_device-boom")


@pytest.mark.usefixtures("real_throttle")
def test_throttle_budget_raises_429_before_entering_block():
    """An already-throttled device never runs the body, and keeps its live key."""
    entered = False
    with patch("oss.routers.ingest.set_key_if_absent", return_value=False), \
         patch("oss.routers.ingest.delete_key") as mock_delete:
        with pytest.raises(HTTPException) as exc_info:
            with _throttle_budget("device-busy", 60):
                entered = True
        assert exc_info.value.status_code == 429
    assert entered is False
    mock_delete.assert_not_called()


@pytest.mark.usefixtures("real_throttle")
def test_throttle_budget_concurrent_first_ingest_exactly_one_wins():
    """Two simultaneous first-ingest claims for one device: exactly one passes.

    `_check_throttle` must not race two concurrent requests via a separate
    read-then-write — `set_key_if_absent` is a single atomic `SET NX EX`;
    simulate two racing callers against one shared, stateful fake so only the
    first claim can ever win.
    """
    claimed: set[str] = set()

    def fake_set_key_if_absent(key, _value, ttl):
        del ttl
        if key in claimed:
            return False
        claimed.add(key)
        return True

    with patch("oss.routers.ingest.set_key_if_absent", side_effect=fake_set_key_if_absent), \
         patch("oss.routers.ingest.delete_key"):
        results = []
        for _ in range(2):
            try:
                with _throttle_budget("device-race", 60):
                    results.append("ok")
            except HTTPException as exc:
                results.append(exc.status_code)

    assert results.count("ok") == 1
    assert results.count(429) == 1


# ---------------------------------------------------------------------------
# _check_device_request_quota unit tests
# ---------------------------------------------------------------------------

def test_check_device_request_quota_raises_429_over_limit():
    """Exceeding the 60/60s ceiling raises HTTP 429 regardless of the interval throttle."""
    with patch("core.middleware.auth.increment_key", return_value=61):
        with pytest.raises(HTTPException) as exc_info:
            _check_device_request_quota("some-device-token")
        assert exc_info.value.status_code == 429


def test_check_device_request_quota_allows_under_limit():
    """Requests at or under the ceiling must not raise."""
    with patch("core.middleware.auth.increment_key", return_value=60):
        _check_device_request_quota("some-device-token")  # no raise


def test_check_device_request_quota_skips_when_no_token():
    """A missing token has nothing to rate-limit on; must not touch the cache."""
    with patch("core.middleware.auth.increment_key") as mock_increment:
        _check_device_request_quota(None)
        mock_increment.assert_not_called()


def test_check_device_request_quota_key_is_hashed():
    """The cache key must never contain the plaintext token or an 8-char prefix of it."""
    token = "abcd1234" + "x" * 40
    with patch("core.middleware.auth.increment_key", return_value=1) as mock_increment:
        _check_device_request_quota(token)

    key = mock_increment.call_args.args[0]
    assert token not in key, f"plaintext token leaked into cache key: {key}"
    assert token[:8] not in key, "an 8-char prefix is still guessable/collidable"
    assert hashlib.sha256(token.encode()).hexdigest() in key


# ---------------------------------------------------------------------------
# Dispatch endpoint
# ---------------------------------------------------------------------------

def test_dispatch_gravitymon_payload(app_client):
    """POST /ingest/dispatch routes gravitymon payload correctly."""
    truncate_database()
    device = _create_device(app_client, "DISP01", "gravitymon")
    token = device["token"]
    payload = {**GRAVITY_PAYLOAD, "token": token}
    r = app_client.post("/ingest/dispatch", json=payload)
    assert r.status_code == 200


def test_dispatch_pressuremon_payload(app_client):
    """POST /ingest/dispatch routes pressuremon payload correctly."""
    truncate_database()
    device = _create_device(app_client, "PRES01", "pressuremon")
    token = device["token"]
    payload = {**PRESSURE_PAYLOAD, "token": token}
    r = app_client.post("/ingest/dispatch", json=payload)
    assert r.status_code == 200


def test_dispatch_kegmon_no_tap_returns_401(app_client):
    """POST /ingest/dispatch with kegmon payload and unknown token returns 401."""
    truncate_database()
    r = app_client.post(
        "/ingest/dispatch",
        json={"pour": 0.5, "volume": 10.0, "maxVolume": 19.0, "token": "bad-token"},
    )
    assert r.status_code == 401


def test_dispatch_parse_error_returns_422(app_client):
    """POST /ingest/dispatch with invalid JSON body returns 422."""
    r = app_client.post(
        "/ingest/dispatch",
        content=b"not-json-at-all",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# KegMon endpoint
# ---------------------------------------------------------------------------

def test_kegmon_unknown_tap_returns_401(app_client):
    """POST /ingest/kegmon with unknown token returns 401."""
    truncate_database()
    r = app_client.post(
        "/ingest/kegmon",
        json={"pour": 0.5, "volume": 10.0, "maxVolume": 19.0,
              "token": "unknown-tap-token"},
    )
    assert r.status_code == 401


def test_kegmon_no_active_vessel_returns_409(app_client):
    """POST /ingest/kegmon with valid tap but no tapped vessel returns 409."""
    truncate_database()
    tap = _create_tap_with_token(app_client, "kegmon-test-tok")
    r = app_client.post(
        "/ingest/kegmon",
        json={"pour": 0.5, "volume": 10.0, "maxVolume": 19.0, "token": tap["token"]},
    )
    assert r.status_code == 409


def test_kegmon_parse_error_returns_422(app_client):
    """POST /ingest/kegmon with invalid JSON returns 422."""
    r = app_client.post(
        "/ingest/kegmon",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GravityMon endpoint parse error
# ---------------------------------------------------------------------------

def test_gravitymon_parse_error_returns_422(app_client):
    """POST /ingest/gravitymon with invalid JSON returns 422."""
    r = app_client.post(
        "/ingest/gravitymon",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# iSpindel endpoint
# ---------------------------------------------------------------------------

def test_ispindel_parse_error_returns_422(app_client):
    """POST /ingest/ispindel with invalid JSON returns 422."""
    r = app_client.post(
        "/ingest/ispindel",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


def test_ispindel_unregistered_returns_401(app_client):
    """POST /ingest/ispindel with no token and unknown chip_id returns 401."""
    truncate_database()
    r = app_client.post("/ingest/ispindel", json={"name": "orphan", "gravity": 1.05})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# PressureMon endpoint
# ---------------------------------------------------------------------------

def test_pressuremon_unregistered_returns_401(app_client):
    """POST /ingest/pressuremon with unknown token/chip_id returns 401."""
    truncate_database()
    payload = {**PRESSURE_PAYLOAD, "token": "bad-pressure-token"}
    r = app_client.post("/ingest/pressuremon", json=payload)
    assert r.status_code == 401


def test_pressuremon_parse_error_returns_422(app_client):
    """POST /ingest/pressuremon with invalid JSON returns 422."""
    r = app_client.post(
        "/ingest/pressuremon",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422
