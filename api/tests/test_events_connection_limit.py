# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Concurrent /events connections are limited per client IP and in total."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from oss.routers import events


@pytest.fixture(autouse=True)
def clean_slots():
    """Start and finish each test with no open streams."""
    events._open_by_ip.clear()
    yield
    events._open_by_ip.clear()


def _settings(per_ip=2, total=3):
    s = MagicMock()
    s.sse_max_connections_per_ip = per_ip
    s.sse_max_connections = total
    return s


def test_per_ip_limit_rejects_with_429():
    """The connection after the per-IP limit is refused with 429 and a Retry-After."""
    with patch("oss.routers.events.get_settings", return_value=_settings()):
        events._acquire_slot("10.0.0.1")
        events._acquire_slot("10.0.0.1")
        with pytest.raises(HTTPException) as exc:
            events._acquire_slot("10.0.0.1")
        events._acquire_slot("10.0.0.2")  # another IP is unaffected
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"]


def test_total_limit_applies_across_ips():
    """The total limit (the per-key limit, as the key is shared) counts every IP."""
    with patch("oss.routers.events.get_settings", return_value=_settings()):
        for ip in ("10.0.0.1", "10.0.0.2", "10.0.0.3"):
            events._acquire_slot(ip)
        with pytest.raises(HTTPException) as exc:
            events._acquire_slot("10.0.0.4")
    assert exc.value.status_code == 429


def test_release_frees_a_slot():
    """Releasing a slot lets the next connection in."""
    with patch("oss.routers.events.get_settings", return_value=_settings(per_ip=1, total=0)):
        events._acquire_slot("10.0.0.1")
        events._release_slot("10.0.0.1")
        events._acquire_slot("10.0.0.1")


def test_zero_disables_a_limit():
    """A limit of 0 means unlimited."""
    with patch("oss.routers.events.get_settings", return_value=_settings(per_ip=0, total=0)):
        for _ in range(200):
            events._acquire_slot("10.0.0.1")


def test_route_refuses_when_limit_reached(root_client):
    """GET /events returns 429 (not a stream) once the limit is reached."""
    from core.config import get_settings  # pylint: disable=import-outside-toplevel
    headers = {"Authorization": "Bearer " + get_settings().api_key.get_secret_value()}
    events._open_by_ip["testclient"] = 1
    with patch("oss.routers.events.get_settings", return_value=_settings(per_ip=1, total=0)):
        r = root_client.get("/events", headers=headers)
    assert r.status_code == 429
    assert r.headers["Retry-After"]
