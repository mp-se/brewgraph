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
import json
import uuid as _uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from starlette.exceptions import HTTPException

from core.config import get_settings
from core.db import create_session, get_session
from core.models.platform import IngestionLog
from core.models.registry import resolve_model
from oss.services.ingestion import IngestionService, UnstorableValueError
from oss.routers.ingest import (
    _check_device_request_quota,
    _check_throttle,
    _throttle_budget,
    _detect_device_type,
)
from tests.conftest import DEVICE_DEFAULTS, truncate_database

Device = resolve_model("Device")
Tap = resolve_model("Tap")
PourEvent = resolve_model("PourEvent")

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


def _count_rows(model) -> int:
    session = create_session()
    try:
        return session.query(model).count()
    finally:
        session.close()


@pytest.mark.parametrize("extra", [{"pour": 0.5}, {}])
def test_kegmon_no_active_vessel_is_ignored(app_client, extra):
    """A pour or level for a tap with no vessel answers 200, stores and logs nothing."""
    truncate_database()
    tap = _create_tap_with_token(app_client, "kegmon-test-tok")
    r = app_client.post(
        "/ingest/kegmon",
        json={"volume": 10.0, "maxVolume": 19.0, "temperature": 20.0, "token": tap["token"],
              **extra},
    )
    assert r.status_code == 200
    assert r.text == ""
    assert _count_rows(resolve_model("PourEvent")) == 0
    assert _count_rows(resolve_model("TempReading")) == 0
    assert _count_rows(IngestionLog) == 0


def _temps(vessel_id) -> list:
    session = create_session()
    try:
        model = resolve_model("TempReading")
        rows = session.query(model).filter_by(vessel_id=_uuid.UUID(vessel_id))
        return [row.temperature for row in rows]
    finally:
        session.close()


def test_kegmon_pour_with_temperature_stores_a_reading(app_client):
    """A pour's temperature is stored against the vessel and the pour is recorded."""
    tap, vessel_id = _kegmon_setup(app_client)
    r = app_client.post("/ingest/kegmon", json={
        "token": tap["token"], "pour": 1.0, "volume": 15.0, "maxVolume": 20.0,
        "temperature": 22.625, "eventId": "t1",
    })
    assert r.status_code == 200
    assert _temps(vessel_id) == [pytest.approx(22.625, abs=0.05)]
    assert len(_pours(app_client, vessel_id)) == 1


def test_kegmon_level_with_temperature_stores_one_reading(app_client):
    """A level report's temperature is stored once."""
    tap, vessel_id = _kegmon_setup(app_client)
    r = app_client.post("/ingest/kegmon", json={
        "token": tap["token"], "volume": 15.0, "maxVolume": 20.0, "temperature": 5.0,
    })
    assert r.status_code == 200
    assert _temps(vessel_id) == [5.0]


def test_kegmon_retried_pour_stores_the_temperature_once(app_client):
    """The same event sent twice does not store a second reading."""
    tap, vessel_id = _kegmon_setup(app_client)
    body = {"token": tap["token"], "pour": 1.0, "volume": 15.0, "maxVolume": 20.0,
            "temperature": 5.0, "eventId": "once"}
    assert app_client.post("/ingest/kegmon", json=body).status_code == 200
    assert app_client.post("/ingest/kegmon", json=body).status_code == 200
    assert _temps(vessel_id) == [5.0]


def test_kegmon_without_temperature_stores_no_reading(app_client):
    """An absent temperature stores no reading and logs nothing."""
    tap, vessel_id = _kegmon_setup(app_client)
    r = app_client.post("/ingest/kegmon", json={
        "token": tap["token"], "volume": 15.0, "maxVolume": 20.0,
    })
    assert r.status_code == 200
    assert _temps(vessel_id) == []
    assert _count_rows(IngestionLog) == 0


def test_kegmon_numeric_string_temperature_is_dropped_and_logged(app_client):
    """A numeric string is not a JSON number and is dropped with a parse log."""
    tap, vessel_id = _kegmon_setup(app_client)
    r = app_client.post("/ingest/kegmon", json={
        "token": tap["token"], "volume": 15.0, "maxVolume": 20.0, "temperature": "7.5",
    })
    assert r.status_code == 200
    assert _temps(vessel_id) == []
    session = create_session()
    try:
        row = session.query(IngestionLog).one()
        assert row.error_detail.startswith("temperature:")
        assert "7.5" not in row.error_detail
    finally:
        session.close()


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", True, {"a": 1}, [1], "warm"])
def test_kegmon_unusable_temperature_is_dropped_and_logged(app_client, value):
    """An unusable temperature never refuses the pour; the log names the field, not the value."""
    tap, vessel_id = _kegmon_setup(app_client)
    r = app_client.post("/ingest/kegmon", json={
        "token": tap["token"], "pour": 1.0, "volume": 15.0, "maxVolume": 20.0,
        "temperature": value, "eventId": "bad-temp",
    })
    assert r.status_code == 200
    assert _temps(vessel_id) == []
    assert len(_pours(app_client, vessel_id)) == 1
    session = create_session()
    try:
        rows = session.query(IngestionLog).all()
        assert len(rows) == 1
        assert rows[0].error_detail.startswith("temperature:")
        assert "warm" not in rows[0].error_detail
    finally:
        session.close()


def test_kegmon_non_finite_temperature_literals_are_dropped(app_client):
    """Bare NaN and Infinity JSON tokens, as some firmware emits, drop the temperature too."""
    tap, vessel_id = _kegmon_setup(app_client)
    prefix = json.dumps({"token": tap["token"], "volume": 15.0, "maxVolume": 20.0})[:-1]
    raw = prefix + ', "temperature": NaN}'
    r = app_client.post("/ingest/kegmon", content=raw,
                        headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    assert _temps(vessel_id) == []


def test_kegmon_temperature_does_not_excuse_a_rejected_volume(app_client):
    """A payload whose volume is refused stays refused and stores no temperature."""
    tap, vessel_id = _kegmon_setup(app_client)
    r = app_client.post("/ingest/kegmon", json={
        "token": tap["token"], "volume": "NaN", "maxVolume": 20.0, "temperature": 5.0,
    })
    assert r.status_code == 422
    assert _temps(vessel_id) == []


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


# ---------------------------------------------------------------------------
# KegMon stores the volume it reports
# ---------------------------------------------------------------------------

def _kegmon_setup(app_client, token: str = "kegmon-store-token", total: float = 20.0) -> tuple:
    """Create a tap carrying a keg of ``total`` litres; return (tap, vessel_id)."""
    truncate_database()
    tap = _create_tap_with_token(app_client, token)
    batch_id = app_client.post("/batches", json={"name": "Keg Batch"}, headers=headers).json()["id"]
    vessel_id = app_client.post("/vessels", json={
        "batchId": batch_id, "vesselType": "keg", "name": "Keg", "fillDate": "2026-05-01",
        "totalVolume": total, "volumeRemaining": total, "status": "serving",
    }, headers=headers).json()["id"]
    app_client.patch(f"/vessels/{vessel_id}", json={"tapId": tap["id"]}, headers=headers)
    return tap, vessel_id


def _vessel(app_client, vessel_id) -> dict:
    return app_client.get(f"/vessels/{vessel_id}", headers=headers).json()


def test_kegmon_volume_above_max_volume_raises_the_capacity(app_client):
    """A volume above the reported capacity is stored as received; the capacity follows it."""
    tap, vessel_id = _kegmon_setup(app_client)
    r = app_client.post("/ingest/kegmon", json={
        "token": tap["token"], "volume": 25.0, "maxVolume": 19.0,
    })
    assert r.status_code == 200
    vessel = _vessel(app_client, vessel_id)
    assert vessel["volumeRemaining"] == 25.0
    assert vessel["totalVolume"] == 25.0


def test_kegmon_volumes_have_no_upper_bound(app_client):
    """Neither volume nor capacity is clamped to the old 30000 limit."""
    tap, vessel_id = _kegmon_setup(app_client)
    r = app_client.post("/ingest/kegmon", json={
        "token": tap["token"], "volume": 50000.0, "maxVolume": 60000.0,
    })
    assert r.status_code == 200
    vessel = _vessel(app_client, vessel_id)
    assert vessel["volumeRemaining"] == 50000.0
    assert vessel["totalVolume"] == 60000.0


def test_kegmon_pour_amount_is_stored_as_received(app_client):
    """A pour is recorded with the amount reported, whatever its size."""
    tap, vessel_id = _kegmon_setup(app_client, total=100000.0)
    r = app_client.post("/ingest/kegmon", json={
        "token": tap["token"], "volume": 10.0, "maxVolume": 100000.0, "pour": 40000.0,
    })
    assert r.status_code == 200
    pours = app_client.get(f"/vessels/{vessel_id}/pours", headers=headers).json()["items"]
    assert pours[0]["pourAmount"] == 40000.0


def _pours(app_client, vessel_id) -> list:
    return app_client.get(f"/vessels/{vessel_id}/pours", headers=headers).json()["items"]


def _unstorable_pour(field: str):
    """Make the pour use case refuse the payload as it does for a value it cannot store."""
    return patch.object(
        IngestionService, "write_pour", side_effect=UnstorableValueError(field, "not storable")
    )


def _last_seen(model, key: dict):
    session = create_session()
    try:
        return session.query(model).filter_by(**key).one().last_seen
    finally:
        session.close()


@pytest.mark.parametrize("field", ["volume", "maxVolume"])
def test_kegmon_negative_level_is_stored_as_received(app_client, field):
    """No sign check: a negative level is stored, and the vessel level equals it."""
    tap, vessel_id = _kegmon_setup(app_client)
    body = {"token": tap["token"], "volume": 10.0, "maxVolume": 19.0, field: -1.0}
    assert app_client.post("/ingest/kegmon", json=body).status_code == 200
    vessel = _vessel(app_client, vessel_id)
    if field == "volume":
        assert vessel["volumeRemaining"] == -1.0
        assert vessel["totalVolume"] == 19.0
    else:
        assert vessel["volumeRemaining"] == 10.0
        assert vessel["totalVolume"] == 10.0


def test_kegmon_pour_after_level_report_with_same_volume_is_stored(app_client):
    """A pour carrying an event id is recorded even when the level did not move down."""
    tap, vessel_id = _kegmon_setup(app_client)
    level = {"token": tap["token"], "volume": 15.0, "maxVolume": 20.0}
    assert app_client.post("/ingest/kegmon", json=level).status_code == 200
    assert _pours(app_client, vessel_id) == []
    pour = {**level, "pour": 0.5, "eventId": "after-level"}
    assert app_client.post("/ingest/kegmon", json=pour).status_code == 200
    pours = _pours(app_client, vessel_id)
    assert [p["pourAmount"] for p in pours] == [0.5]
    assert _vessel(app_client, vessel_id)["volumeRemaining"] == 15.0


def test_kegmon_retried_pour_is_one_event(app_client):
    """The same event id sent twice is recorded once."""
    tap, vessel_id = _kegmon_setup(app_client)
    pour = {"token": tap["token"], "volume": 15.0, "maxVolume": 20.0, "pour": 0.5, "eventId": "e1"}
    assert app_client.post("/ingest/kegmon", json=pour).status_code == 200
    assert app_client.post("/ingest/kegmon", json=pour).status_code == 200
    assert len(_pours(app_client, vessel_id)) == 1


def test_kegmon_pour_without_event_id_needs_a_lower_volume(app_client):
    """Without an event id a pour is recorded only when the level moved down."""
    tap, vessel_id = _kegmon_setup(app_client)
    body = {"token": tap["token"], "maxVolume": 20.0, "pour": 0.5}
    assert app_client.post("/ingest/kegmon", json={**body, "volume": 20.0}).status_code == 200
    assert _pours(app_client, vessel_id) == []
    assert app_client.post("/ingest/kegmon", json={**body, "volume": 21.0}).status_code == 200
    assert _pours(app_client, vessel_id) == []
    assert app_client.post("/ingest/kegmon", json={**body, "volume": 19.5}).status_code == 200
    assert len(_pours(app_client, vessel_id)) == 1


def test_kegmon_level_only_creates_no_pour(app_client):
    """A payload without a pour only sets the level."""
    tap, vessel_id = _kegmon_setup(app_client)
    body = {"token": tap["token"], "volume": 12.0, "maxVolume": 20.0, "eventId": "level-1"}
    assert app_client.post("/ingest/kegmon", json=body).status_code == 200
    assert _pours(app_client, vessel_id) == []
    assert _vessel(app_client, vessel_id)["volumeRemaining"] == 12.0


def test_kegmon_refill_sets_the_level_and_creates_no_pour(app_client):
    """A higher volume is the new level; it is not a pour."""
    tap, vessel_id = _kegmon_setup(app_client)
    low = {"token": tap["token"], "volume": 5.0, "maxVolume": 20.0}
    assert app_client.post("/ingest/kegmon", json=low).status_code == 200
    assert app_client.post("/ingest/kegmon", json={**low, "volume": 20.0}).status_code == 200
    assert _vessel(app_client, vessel_id)["volumeRemaining"] == 20.0
    assert _pours(app_client, vessel_id) == []


def test_kegmon_repeated_unstorable_value_is_logged_once(app_client):
    """One parse_error row per tap and reason inside 15 minutes."""
    tap, _ = _kegmon_setup(app_client)
    body = {"token": tap["token"], "volume": 10.0, "maxVolume": 19.0}
    with _unstorable_pour("volume"):
        assert app_client.post("/ingest/kegmon", json=body).status_code == 422
        assert app_client.post("/ingest/kegmon", json=body).status_code == 422
    session = create_session()
    try:
        assert session.query(IngestionLog).filter(IngestionLog.reason == "parse_error").count() == 1
    finally:
        session.close()


def test_kegmon_unstorable_value_names_the_field_and_stamps_last_seen(app_client):
    """An unstorable level is a logged 422, releases the throttle, and the tap is still seen."""
    tap, vessel_id = _kegmon_setup(app_client)
    body = {"token": tap["token"], "volume": 10.0, "maxVolume": 19.0}
    with _unstorable_pour("maxVolume"), patch("oss.routers.ingest.delete_key") as release:
        assert app_client.post("/ingest/kegmon", json=body).status_code == 422
    release.assert_called_once()
    assert _vessel(app_client, vessel_id)["volumeRemaining"] == 20.0
    session = create_session()
    try:
        rows = session.query(IngestionLog).filter(IngestionLog.reason == "parse_error").all()
        assert [row.error_detail.split(":")[0] for row in rows] == ["maxVolume"]
    finally:
        session.close()
    assert _last_seen(Tap, {"id": _uuid.UUID(tap["id"])}) is not None


def test_kegmon_throttled_request_stamps_last_seen(app_client):
    """A 429 still records that the tap is alive."""
    tap, _ = _kegmon_setup(app_client)
    refusal = HTTPException(status_code=429, detail="throttled")
    body = {"token": tap["token"], "volume": 10.0, "maxVolume": 19.0}
    with patch("oss.routers.ingest._check_throttle", side_effect=refusal):
        assert app_client.post("/ingest/kegmon", json=body).status_code == 429
    assert _last_seen(Tap, {"id": _uuid.UUID(tap["id"])}) is not None


def test_kegmon_unknown_token_stamps_nothing(app_client):
    """A request that identifies no tap leaves every tap unseen."""
    tap, _ = _kegmon_setup(app_client)
    body = {"token": "not-a-token", "volume": 10.0, "maxVolume": 19.0}
    assert app_client.post("/ingest/kegmon", json=body).status_code == 401
    assert _last_seen(Tap, {"id": _uuid.UUID(tap["id"])}) is None


def test_gravity_throttled_request_stamps_last_seen(app_client):
    """A throttled gravity reading still records that the device is alive."""
    truncate_database()
    _create_device(app_client, "THR01")
    refusal = HTTPException(status_code=429, detail="throttled")
    with patch("oss.routers.ingest._check_throttle", side_effect=refusal):
        r = app_client.post("/ingest/gravitymon", json={**GRAVITY_PAYLOAD, "id": "THR01"})
    assert r.status_code == 429
    assert _last_seen(Device, {"chip_id": "THR01"}) is not None


def test_pressure_unstorable_value_stamps_last_seen(app_client):
    """An unstorable pressure is a 422 and the device is still seen."""
    truncate_database()
    device = _create_device(app_client, "UNS01", "pressuremon")
    payload = {**PRESSURE_PAYLOAD, "token": device["token"], "pressure": 1e307,
               "pressure_units": "bar"}
    assert app_client.post("/ingest/pressuremon", json=payload).status_code == 422
    assert _last_seen(Device, {"chip_id": "UNS01"}) is not None


def test_pressure_throttled_request_stamps_last_seen(app_client):
    """A throttled pressure reading still records that the device is alive."""
    truncate_database()
    device = _create_device(app_client, "THP01", "pressuremon")
    refusal = HTTPException(status_code=429, detail="throttled")
    with patch("oss.routers.ingest._check_throttle", side_effect=refusal):
        r = app_client.post(
            "/ingest/pressuremon", json={**PRESSURE_PAYLOAD, "token": device["token"]}
        )
    assert r.status_code == 429
    assert _last_seen(Device, {"chip_id": "THP01"}) is not None


def test_unknown_gravity_device_stamps_nothing(app_client):
    """An unregistered device is a 401 and no registered device is touched."""
    truncate_database()
    _create_device(app_client, "KNOWN01")
    payload = {**GRAVITY_PAYLOAD, "id": "OTHER01"}
    assert app_client.post("/ingest/gravitymon", json=payload).status_code == 401
    assert _last_seen(Device, {"chip_id": "KNOWN01"}) is None


@pytest.mark.parametrize("field", ["volume", "maxVolume", "pour"])
@pytest.mark.parametrize("bad", ["abc", "nan", "inf", None])
def test_kegmon_non_finite_number_dropped(app_client, field, bad):
    """Bad optional pours are dropped; required levels remain 422."""
    tap, vessel_id = _kegmon_setup(app_client)
    body = {"token": tap["token"], "volume": 10.0, "maxVolume": 19.0, "pour": 0.3, field: bad}
    r = app_client.post("/ingest/kegmon", json=body)
    if field == "pour" and bad is None:
        assert r.status_code == 200
    elif field == "pour":
        assert r.status_code == 200
        assert len(_pours(app_client, vessel_id)) == 0
        session = create_session()
        try:
            assert field in session.query(IngestionLog).one().error_detail
        finally:
            session.close()
    else:
        assert r.status_code == 422


def _pour_rows() -> list:
    session = create_session()
    try:
        return [(p.event_id, p.tap_id) for p in session.query(PourEvent).all()]
    finally:
        session.close()


def _logged_details() -> list:
    session = create_session()
    try:
        return [row.error_detail for row in session.query(IngestionLog).all()]
    finally:
        session.close()


@pytest.mark.parametrize("bad", [12, True, ["a"], {"a": 1}, "", "   ", "x" * 129, "x" * 5000])
def test_kegmon_unusable_event_id_is_dropped_logged_and_the_pour_stored(app_client, bad):
    """A bad optional eventId never refuses the pour; it is stored without an id."""
    tap, vessel_id = _kegmon_setup(app_client)
    body = {"token": tap["token"], "volume": 19.5, "maxVolume": 20.0, "pour": 0.5, "eventId": bad}
    assert app_client.post("/ingest/kegmon", json=body).status_code == 200
    assert [p["pourAmount"] for p in _pours(app_client, vessel_id)] == [0.5]
    assert [event_id for event_id, _ in _pour_rows()] == [None]
    assert any("eventId" in detail for detail in _logged_details())


def test_kegmon_null_event_id_is_absent(app_client):
    """null is not a dropped value: nothing is logged."""
    tap, vessel_id = _kegmon_setup(app_client)
    body = {"token": tap["token"], "volume": 19.5, "maxVolume": 20.0, "pour": 0.5,
            "eventId": None}
    assert app_client.post("/ingest/kegmon", json=body).status_code == 200
    assert len(_pours(app_client, vessel_id)) == 1
    assert _logged_details() == []


def test_kegmon_event_id_of_128_characters_is_stored(app_client):
    """The length limit is inclusive."""
    tap, _ = _kegmon_setup(app_client)
    event_id = "x" * 128
    body = {"token": tap["token"], "volume": 20.0, "maxVolume": 20.0, "pour": 0.5,
            "eventId": event_id}
    assert app_client.post("/ingest/kegmon", json=body).status_code == 200
    assert [stored for stored, _ in _pour_rows()] == [event_id]
    assert _logged_details() == []


@pytest.mark.parametrize("bad", ["", "  ", "x" * 129])
def test_kegmon_unusable_idempotency_header_is_dropped_and_logged(app_client, bad):
    """An Idempotency-Key that cannot be an event id is dropped, named in the log."""
    tap, vessel_id = _kegmon_setup(app_client)
    body = {"token": tap["token"], "volume": 19.5, "maxVolume": 20.0, "pour": 0.5}
    r = app_client.post("/ingest/kegmon", json=body, headers={"Idempotency-Key": bad})
    assert r.status_code == 200
    assert len(_pours(app_client, vessel_id)) == 1
    assert [event_id for event_id, _ in _pour_rows()] == [None]
    assert any("Idempotency-Key" in detail for detail in _logged_details())


def test_kegmon_unusable_event_id_through_dispatch_is_logged(app_client):
    """The dispatch endpoint records the dropped field as the dedicated one does."""
    tap, vessel_id = _kegmon_setup(app_client)
    body = {"token": tap["token"], "volume": 19.5, "maxVolume": 20.0, "pour": 0.5, "eventId": 7}
    assert app_client.post("/ingest/dispatch", json=body).status_code == 200
    assert len(_pours(app_client, vessel_id)) == 1
    assert any("eventId" in detail for detail in _logged_details())


def test_kegmon_same_event_id_on_two_taps_is_independent(app_client):
    """The id is unique per tap, not globally."""
    tap, _ = _kegmon_setup(app_client)
    other = _create_tap_with_token(app_client, "kegmon-other-token")
    batch_id = app_client.post("/batches", json={"name": "B2"}, headers=headers).json()["id"]
    other_vessel = app_client.post("/vessels", json={
        "batchId": batch_id, "vesselType": "keg", "name": "Keg2", "fillDate": "2026-05-01",
        "totalVolume": 20.0, "volumeRemaining": 20.0, "status": "serving",
    }, headers=headers).json()["id"]
    app_client.patch(f"/vessels/{other_vessel}", json={"tapId": other["id"]}, headers=headers)
    for token in (tap["token"], other["token"]):
        body = {"token": token, "volume": 19.5, "maxVolume": 20.0, "pour": 0.5, "eventId": "same"}
        assert app_client.post("/ingest/kegmon", json=body).status_code == 200
    assert sorted(str(tap_id) for _, tap_id in _pour_rows()) == sorted([tap["id"], other["id"]])


def test_kegmon_concurrent_duplicate_event_id_is_one_pour(app_client):
    """Two identical requests at once leave one PourEvent row."""
    tap, vessel_id = _kegmon_setup(app_client)
    body = {"token": tap["token"], "volume": 19.5, "maxVolume": 20.0, "pour": 0.5,
            "eventId": "race"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda _: app_client.post("/ingest/kegmon", json=body).status_code, range(2)
        ))
    assert results == [200, 200]
    assert len(_pour_rows()) == 1
    assert _vessel(app_client, vessel_id)["volumeRemaining"] == 19.5
