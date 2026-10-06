# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Contract tests for request-ID handling, error logging, and cursor ordering.

Covers three deviations from the documented contract:
  * X-Request-ID was echoed from the caller instead of generated per request.
  * 4xx responses were returned without any log line.
  * Vessel pour cursor pages were newest-first, against the normative ASC contract.

None of these had test coverage, which is how all three survived a green suite.
"""
import logging
import uuid

import pytest

from oss.schemas._page import parse_cursor

from core.config import get_settings
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


# --------------------------------------------------------------------------
# Request IDs — docs/architecture.md: "UUID generated per request by middleware"
# --------------------------------------------------------------------------

def test_request_id_is_generated_not_echoed(app_client):
    """A caller-supplied X-Request-ID must never be reflected back.

    Honouring it would let a client collapse unrelated requests onto one ID in
    the logs, or claim another request's ID.
    """
    r = app_client.get("/batches", headers={**headers, "X-Request-ID": "forged-id-12345"})
    assert r.headers["X-Request-ID"] != "forged-id-12345"
    uuid.UUID(r.headers["X-Request-ID"])  # raises if not a well-formed UUID


def test_request_ids_are_unique_per_call(app_client):
    """Every API call gets its own ID — 'unique across every API call'."""
    seen = {app_client.get("/batches", headers=headers).headers["X-Request-ID"]
            for _ in range(5)}
    assert len(seen) == 5


def test_error_response_request_id_matches_header(app_client):
    """The envelope's requestId is the same ID echoed in the response header."""
    r = app_client.get(f"/batches/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404
    assert r.json()["requestId"] == r.headers["X-Request-ID"]


# --------------------------------------------------------------------------
# Error logging — docs/architecture.md: "All errors must be logged"
# --------------------------------------------------------------------------

def test_4xx_is_logged_with_its_request_id(app_client, caplog):
    """A 404 must produce a log line carrying its requestId.

    A 4xx response with no matching log line leaves a user-reported requestId
    that appears nowhere in the logs.
    """
    with caplog.at_level(logging.WARNING):
        r = app_client.get(f"/batches/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404
    request_id = r.headers["X-Request-ID"]
    assert any(request_id in rec.getMessage() for rec in caplog.records), \
        "no log line carried the requestId of the 404 response"


def test_validation_error_is_logged_with_its_request_id(app_client, caplog):
    """422s log their requestId too."""
    with caplog.at_level(logging.ERROR):
        r = app_client.post("/batches", json={"brewDate": "not-a-date"}, headers=headers)
    assert r.status_code == 422
    request_id = r.headers["X-Request-ID"]
    assert any(request_id in rec.getMessage() for rec in caplog.records), \
        "no log line carried the requestId of the 422 response"


# --------------------------------------------------------------------------
# Cursor ordering — spec-api-conventions.md: "always ascending (created_at ASC)"
# --------------------------------------------------------------------------

def _vessel_with_pours(app_client, count: int) -> str:
    batch = app_client.post("/batches", json={"name": "Pour Order Batch"},
                            headers=headers).json()["id"]
    vessel_id = app_client.post("/vessels", json={
        "batchId": batch, "vesselNumber": 1, "vesselType": "keg", "name": "Keg 1",
        "fillDate": "2026-05-01", "totalVolume": 19.0, "volumeRemaining": 19.0,
        "status": "filled",
    }, headers=headers).json()["id"]
    for _ in range(count):
        r = app_client.post(f"/vessels/{vessel_id}/pours",
                            json={"pourAmount": 0.5}, headers=headers)
        assert r.status_code == 201
    return vessel_id


def test_pour_cursor_page_is_oldest_first(app_client):
    """GET /vessels/{id}/pours returns created_at ASC."""
    truncate_database()
    vessel_id = _vessel_with_pours(app_client, 4)

    body = app_client.get(f"/vessels/{vessel_id}/pours", headers=headers).json()
    stamps = [i["createdAt"] for i in body["items"]]
    assert stamps == sorted(stamps), f"expected oldest-first, got {stamps}"


def test_pour_cursor_walks_forward_without_repeats(app_client):
    """Paging with the returned cursor advances and never repeats an item.

    The direction flip also flipped the cursor comparison (`<` to `>`); getting
    only one of the two would silently return the same page forever or skip rows.
    """
    truncate_database()
    vessel_id = _vessel_with_pours(app_client, 5)

    seen: list[str] = []
    cursor = None
    for _ in range(5):  # bounded so a broken cursor cannot loop forever
        path = f"/vessels/{vessel_id}/pours?limit=2" + (f"&cursor={cursor}" if cursor else "")
        body = app_client.get(path, headers=headers).json()
        seen.extend(i["id"] for i in body["items"])
        if not body["hasMore"]:
            break
        cursor = body["nextCursor"]

    assert len(seen) == 5
    assert len(set(seen)) == 5, "cursor paging returned duplicate rows"


def test_cursor_survives_an_unencoded_plus_in_the_query_string():
    """A cursor pasted straight into a URL still parses.

    `next_cursor` ends `+00:00` wherever the database returns timezone-aware
    datetimes. A client that appends it to a query string without percent-encoding
    sends a space instead of the `+`, and every page after the first would 400.
    """
    mangled = parse_cursor("2026-08-22T10:00:00 00:00|42")
    proper = parse_cursor("2026-08-22T10:00:00+00:00|42")
    assert mangled == proper
    assert mangled[0].utcoffset().total_seconds() == 0
    assert mangled[1] == "42"

    naive = parse_cursor("2026-08-22T10:00:00|42")
    assert naive[0].tzinfo is None
    assert parse_cursor(None) is None

    with pytest.raises(ValueError):
        parse_cursor("not-a-timestamp|42")

    with pytest.raises(ValueError):
        parse_cursor("2026-08-22T10:00:00+00:00")  # missing |<id> component
