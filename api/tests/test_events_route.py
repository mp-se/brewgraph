# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Contract tests for the SSE route mounting — GET /events.

Distinct from tests/test_events.py, which covers core/events.py internals
(EventBroadcaster, notify_clients, subscribe). This file only asserts *where*
the stream is mounted and that it is authenticated.

Full round-trip streaming behavior (heartbeats, data events) is covered by
tests/test_events.py against core.events.subscribe() directly — the SSE stream
never terminates, so it cannot be exercised through the test client's
httpx.ASGITransport, which only returns a Response once the ASGI app call
itself completes.
"""
from main_oss import app


def test_events_rejects_missing_token(root_client):
    """GET /events returns 401 when no Authorization header is supplied."""
    r = root_client.get("/events")
    assert r.status_code == 401


def test_events_rejects_invalid_token(root_client):
    """GET /events returns 401 when the supplied token is wrong."""
    r = root_client.get("/events", headers={"Authorization": "Bearer wrong-token"})
    assert r.status_code == 401


def test_events_mounted_outside_api_prefix():
    """The stream is at GET /events, NOT under /api.

    The SSE endpoint lives outside /api by design, and nginx proxies `/events`
    specifically. Re-prefixing this route would break the frontend and
    silently disable real-time updates, so pin the path here.
    """
    paths = app.openapi()["paths"]
    assert "/events" in paths
    assert "get" in paths["/events"]
    assert not [p for p in paths if p.endswith("/events") and p != "/events"]


def test_events_route_is_authenticated():
    """The route carries an auth dependency after being moved off system.router.

    The events router declares `api_key_auth` independently rather than
    inheriting it from the system router's `dependencies`; if that
    declaration is ever dropped the stream would serve tenant data
    anonymously.
    """
    assert app.openapi()["paths"]["/events"]["get"].get("security")
