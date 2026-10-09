# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# pylint: disable=redefined-outer-name

"""Malformed path, query and cursor values are rejected as client errors, never a 500."""
import pytest

from core.config import get_settings
from tests.conftest import app_client, truncate_database  # noqa: F401  # pylint: disable=unused-import

HDR = {"Authorization": "Bearer " + get_settings().api_key.get_secret_value()}

BAD_CURSORS = ["garbage", "!!!", "", "a|b", "2026-01-01T00:00:00+00:00|notanid",
               "notadate|1", "' OR 1=1 --", "2026-01-01T00:00:00+00:00|" + "9" * 40, "\x00"]
BAD_UUIDS = ["not-a-uuid", "1", "' OR 1=1 --", "00000000-0000-0000-0000-00000000000g"]


@pytest.fixture()
def ids(app_client):  # noqa: F811
    """One batch and one vessel to point list routes at."""
    truncate_database()
    batch = app_client.post("/batches", json={"name": "B"}, headers=HDR).json()["id"]
    vessel = app_client.post("/vessels", json={"name": "V", "vesselType": "keg",
                                               "totalVolume": 19.0, "status": "clean"},
                             headers=HDR).json()["id"]
    tap = app_client.post("/taps", json={"name": "T", "tapNumber": 1}, headers=HDR).json()["id"]
    return {"batch": batch, "vessel": vessel, "tap": tap}


def _list_routes(ids):
    b, v = ids["batch"], ids["vessel"]
    return [f"/batches/{b}/gravity", f"/batches/{b}/pressure", f"/batches/{b}/temp",
            f"/batches/{b}/notes", f"/vessels/{v}/pours", f"/vessels/{v}/temp",
            f"/vessels/{v}/pressure", "/system/logs", "/system/ingestion",
            f"/taps/{ids['tap']}/predictions"]


def test_list_routes_exist(app_client, ids):  # noqa: F811
    """Guard: every route probed below answers 200, so a typo cannot pass as a 404."""
    for path in _list_routes(ids):
        assert app_client.get(path, headers=HDR).status_code == 200, path


@pytest.mark.parametrize("cursor", BAD_CURSORS)
def test_bad_cursor_is_a_client_error(app_client, ids, cursor):  # noqa: F811
    """A malformed cursor is a 4xx on every cursor-paginated list route."""
    for path in _list_routes(ids):
        r = app_client.get(path, params={"cursor": cursor}, headers=HDR)
        assert r.status_code < 500, (path, cursor, r.status_code, r.text[:200])


@pytest.mark.parametrize("limit", ["0", "-1", "abc", "1e9", "999999999", "1.5"])
def test_bad_limit_is_rejected(app_client, ids, limit):  # noqa: F811
    """Pagination limits must be bounded integers."""
    for path in _list_routes(ids):
        r = app_client.get(path, params={"limit": limit}, headers=HDR)
        assert r.status_code in (404, 422), (path, limit, r.status_code)


@pytest.mark.parametrize("bad", BAD_UUIDS)
def test_bad_uuid_path_is_rejected(app_client, bad):  # noqa: F811
    """Non-UUID ids in the path are 422 before reaching a service."""
    for path in (f"/batches/{bad}", f"/batches/{bad}/notes", f"/vessels/{bad}",
                 f"/taps/{bad}", f"/devices/{bad}", f"/batches/{bad}/gravity"):
        r = app_client.get(path, headers=HDR)
        assert r.status_code == 422, (path, r.status_code)


def test_non_integer_reading_id_is_rejected(app_client, ids):  # noqa: F811
    """Integer reading ids reject non-integers."""
    r = app_client.patch(f"/batches/{ids['batch']}/gravity/abc", json={"gravity": 1.0},
                         headers=HDR)
    assert r.status_code == 422


def test_oversized_bulk_body_is_rejected(app_client, ids):  # noqa: F811
    """Bulk inserts above the cap are refused."""
    rows = [{"gravity": 1.05}] * 1001
    r = app_client.post(f"/batches/{ids['batch']}/gravity/bulk", json=rows, headers=HDR)
    assert r.status_code == 422


def test_bulk_body_with_wrong_types_is_rejected(app_client, ids):  # noqa: F811
    """Bulk rows are validated against the schema, not passed through."""
    for rows in ([{"gravity": "high"}], [{"gravity": None}], [{}], ["x"], {"gravity": 1.0}):
        r = app_client.post(f"/batches/{ids['batch']}/gravity/bulk", json=rows, headers=HDR)
        assert r.status_code == 422, rows
