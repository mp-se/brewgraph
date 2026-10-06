# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Extended device router tests covering proxy_fetch branches and latest-reading endpoints."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from core.config import get_settings
from oss.routers import devices
from tests.conftest import DEVICE_DEFAULTS, truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

DEVICE_DATA = {
    "name": "Ext Device",
    "chipId": "EXTD01",
    **DEVICE_DEFAULTS,
}


def _create_device(app_client, overrides=None) -> dict:
    data = {**DEVICE_DATA, **(overrides or {})}
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# proxy_fetch — header, method, non-200, and text-body branches
# ---------------------------------------------------------------------------

def _mock_httpx(status_code=200, json_data=None, text_data=None, raise_json=False):
    mock_response = MagicMock(status_code=status_code)
    content = (text_data or "plain text").encode() if raise_json else json.dumps(
        json_data or {"ok": True}
    ).encode()
    async def response_chunks():
        yield content
    mock_response.aiter_bytes = response_chunks
    mock_response.aclose = AsyncMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.build_request = MagicMock()
    mock_client.send = AsyncMock(return_value=mock_response)
    return mock_client


def test_proxy_fetch_with_header(app_client):
    """proxy_fetch parses Authorization: Bearer style header."""
    truncate_database()
    mock_client = _mock_httpx()
    with patch(
        "core.utils.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("192.168.1.100", 0))],
    ), \
         patch("httpx.AsyncClient", return_value=mock_client):
        r = app_client.post(
            "/devices/proxy-fetch",
            json={
                "url": "http://device.local/api",
                "method": "GET",
                "body": "",
                "header": "Authorization: Bearer token123",
            },
            headers=headers,
        )
    assert r.status_code == 200


def test_proxy_fetch_rejects_unsupported_method(app_client):
    """Only the documented proxy methods are accepted."""
    r = app_client.post(
        "/devices/proxy-fetch",
        json={"url": "http://device.local/api", "method": "PATCH", "body": "", "header": ""},
        headers=headers,
    )
    assert r.status_code == 422


def test_proxy_fetch_non_200_remote_raises(app_client):
    """proxy_fetch raises HTTPException when remote returns non-200."""
    mock_client = _mock_httpx(status_code=500)
    with patch(
        "core.utils.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("192.168.1.100", 0))],
    ), \
         patch("httpx.AsyncClient", return_value=mock_client):
        r = app_client.post(
            "/devices/proxy-fetch",
            json={"url": "http://device.local/api", "method": "GET", "body": "", "header": ""},
            headers=headers,
        )
    assert r.status_code == 500


def test_proxy_fetch_text_body_when_json_parse_fails(app_client):
    """proxy_fetch returns plain text when remote response is not JSON."""
    mock_client = _mock_httpx(raise_json=True, text_data="OK")
    with patch(
        "core.utils.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("192.168.1.100", 0))],
    ), \
         patch("httpx.AsyncClient", return_value=mock_client):
        r = app_client.post(
            "/devices/proxy-fetch",
            json={"url": "http://device.local/api", "method": "GET", "body": "", "header": ""},
            headers=headers,
        )
    assert r.status_code == 200


def test_proxy_fetch_post_method(app_client):
    """proxy_fetch forwards a POST request to the device."""
    mock_client = _mock_httpx()
    with patch(
        "core.utils.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("192.168.1.100", 0))],
    ), \
         patch("httpx.AsyncClient", return_value=mock_client):
        r = app_client.post(
            "/devices/proxy-fetch",
            json={"url": "http://device.local/save", "method": "POST", "body": "{}", "header": ""},
            headers=headers,
        )
    assert r.status_code == 200
    request = mock_client.build_request.call_args.args
    assert request[0] == "POST"


def test_proxy_fetch_preserves_hostname_for_pinned_https(app_client):
    """The TCP peer is pinned, while TLS verifies the configured hostname."""
    mock_client = _mock_httpx()
    with patch(
        "core.utils.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("192.168.1.100", 0))],
    ), \
         patch("httpx.AsyncClient", return_value=mock_client):
        response = app_client.post(
            "/devices/proxy-fetch",
            json={"url": "https://device.local:8443/api", "method": "GET"},
            headers=headers,
        )
    assert response.status_code == 200
    _, url = mock_client.build_request.call_args.args
    assert url == "https://192.168.1.100:8443/api"
    assert mock_client.build_request.call_args.kwargs["headers"]["Host"] == "device.local:8443"
    assert mock_client.build_request.call_args.kwargs["extensions"] == {
        "sni_hostname": "device.local"
    }


def test_proxy_fetch_stops_streaming_response_at_size_cap(app_client, monkeypatch):
    """The remote response is rejected before an unbounded body reaches memory."""
    monkeypatch.setattr(devices, "_MAX_PROXY_BYTES", 4)
    mock_client = _mock_httpx(text_data="oversized")
    with patch(
        "core.utils.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("192.168.1.100", 0))],
    ), \
         patch("httpx.AsyncClient", return_value=mock_client):
        response = app_client.post(
            "/devices/proxy-fetch",
            json={"url": "http://device.local/api", "method": "GET"},
            headers=headers,
        )
    assert response.status_code == 502


# ---------------------------------------------------------------------------
# delete device log
# ---------------------------------------------------------------------------

def test_get_device_log(app_client, monkeypatch, tmp_path):
    """GET /devices/logs/{chip_id} returns a log only with API authentication."""
    monkeypatch.setattr(devices, "LOG_DIR", tmp_path)
    (tmp_path / "ABCDEF.log").write_text("first line\n", encoding="utf-8")
    (tmp_path / "ABCDEF.log.1").write_text("previous line\n", encoding="utf-8")

    current = app_client.get("/devices/logs/ABCDEF", headers=headers)
    previous = app_client.get("/devices/logs/ABCDEF?rotated=true", headers=headers)

    assert current.status_code == 200
    assert current.text == "first line\n"
    assert current.headers["content-type"].startswith("text/plain")
    assert previous.status_code == 200
    assert previous.text == "previous line\n"


def test_get_device_log_rejects_invalid_or_missing_file(app_client, monkeypatch, tmp_path):
    """Log reads validate the chip id and do not expose arbitrary files."""
    monkeypatch.setattr(devices, "LOG_DIR", tmp_path)

    assert app_client.get("/devices/logs/not-a-chip", headers=headers).status_code == 400
    assert app_client.get("/devices/logs/ABCDEF", headers=headers).status_code == 404


def test_get_device_log_returns_bounded_tail_for_oversized_file(app_client, monkeypatch, tmp_path):
    """An oversized serial log cannot make the API allocate an unbounded response."""
    monkeypatch.setattr(devices, "LOG_DIR", tmp_path)
    monkeypatch.setattr(devices, "_MAX_DEVICE_LOG_BYTES", 16)
    (tmp_path / "ABCDEF.log").write_bytes(b"old content\n" + b"x" * 12 + b" newest\n")

    response = app_client.get("/devices/logs/ABCDEF", headers=headers)

    assert response.status_code == 200
    assert response.headers["x-log-truncated"] == "true"
    assert response.text.startswith("[... older log content omitted ...]\n")
    assert response.text.endswith(" newest\n")
    assert len(response.content) <= 16 + len("[... older log content omitted ...]\n")


def test_delete_device_log_no_file(app_client):
    """DELETE /devices/logs/{chip_id} returns 204 even when no log file exists."""
    r = app_client.delete("/devices/logs/ABCDEF", headers=headers)
    assert r.status_code == 204


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# mDNS scan (cache-backed)
# ---------------------------------------------------------------------------

def test_mdns_scan_empty(app_client):
    """GET /devices/mdns/ returns empty list when no mDNS cache entries exist."""
    with patch("oss.routers.devices.find_key", return_value=[]):
        r = app_client.get("/devices/mdns", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


def test_mdns_scan_returns_cached_devices(app_client):
    """GET /devices/mdns/ returns devices found in the Redis cache."""
    cached = json.dumps({"name": "gravitymon-abc", "ip": "192.168.1.50"}).encode()
    mock_value = MagicMock()
    mock_value.decode.return_value = cached.decode()

    with patch("oss.routers.devices.find_key", return_value=[b"gravitymon-abc.local."]), \
         patch("oss.routers.devices.read_key", return_value=mock_value):
        r = app_client.get("/devices/mdns", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "gravitymon-abc"


# ---------------------------------------------------------------------------
# mDNS report (POST) — round trip through an in-memory stand-in for the cache
# ---------------------------------------------------------------------------

class _FakeCache:
    """Minimal find/read/write cache honouring the glob suffix the GET scans."""

    def __init__(self):
        self.values = {}
        self.ttls = {}

    def write_key(self, key, value, ttl):
        """Store a value and remember its TTL."""
        self.values[key] = value
        self.ttls[key] = ttl
        return True

    def find_key(self, pattern, **_):
        """Return keys ending in the pattern's literal suffix."""
        suffix = pattern.lstrip("*")
        return [k.encode() for k in self.values if k.endswith(suffix)]

    def read_key(self, key):
        """Return the stored value as bytes."""
        return self.values[key.decode()].encode()


def _patched_cache(cache):
    return (
        patch("oss.routers.devices.write_key", cache.write_key),
        patch("oss.routers.devices.find_key", cache.find_key),
        patch("oss.routers.devices.read_key", cache.read_key),
    )


MDNS_RECORD = {
    "type": "_gravitymon._tcp.local.",
    "host": "192.168.1.10:80",
    "name": "gravitymon-abc.local",
}


def test_mdns_report_is_returned_by_scan(app_client):
    """A reported device is stored with a TTL and listed by GET /devices/mdns."""
    cache = _FakeCache()
    p1, p2, p3 = _patched_cache(cache)
    with p1, p2, p3:
        r = app_client.post("/devices/mdns", json=MDNS_RECORD, headers=headers)
        assert r.status_code == 204
        listed = app_client.get("/devices/mdns", headers=headers).json()
    assert len(listed) == 1
    assert MDNS_RECORD.items() <= listed[0].items()
    key = next(iter(cache.values))
    assert key.endswith(".local.")
    assert cache.ttls[key] == devices._MDNS_TTL_SECONDS  # pylint: disable=protected-access


def test_mdns_report_replaces_and_separates_services(app_client):
    """Re-reporting replaces a record; another service on the same host is kept."""
    cache = _FakeCache()
    p1, p2, p3 = _patched_cache(cache)
    with p1, p2, p3:
        app_client.post("/devices/mdns", json=MDNS_RECORD, headers=headers)
        app_client.post(
            "/devices/mdns", json={**MDNS_RECORD, "host": "192.168.1.11:80"}, headers=headers
        )
        app_client.post(
            "/devices/mdns",
            json={**MDNS_RECORD, "type": "_gravitymon-gateway._tcp.local."},
            headers=headers,
        )
        listed = app_client.get("/devices/mdns", headers=headers).json()
    assert len(listed) == 2
    assert {d["type"] for d in listed} == {
        "_gravitymon._tcp.local.", "_gravitymon-gateway._tcp.local."}
    assert any(d["host"] == "192.168.1.11:80" for d in listed)
    assert not any(d["host"] == "192.168.1.10:80" and d["type"] == "_gravitymon._tcp.local."
                   for d in listed)


def test_mdns_report_rejects_invalid_body(app_client):
    """A body without a usable host name, or that is not an object, is a 422."""
    cache = _FakeCache()
    p1, p2, p3 = _patched_cache(cache)
    with p1, p2, p3:
        assert app_client.post("/devices/mdns", json={"host": "1.2.3.4:80"},
                               headers=headers).status_code == 422
        assert app_client.post("/devices/mdns", json={"name": "a*.local"},
                               headers=headers).status_code == 422
        assert app_client.post("/devices/mdns", json={"name": "x", "port": "abc"},
                               headers=headers).status_code == 422
        assert app_client.post("/devices/mdns", json=["x"], headers=headers).status_code == 422
    assert not cache.values


def test_mdns_report_requires_auth(app_client):
    """Without the API key the POST is rejected like every other devices route."""
    cache = _FakeCache()
    p1, p2, p3 = _patched_cache(cache)
    with p1, p2, p3:
        r = app_client.post("/devices/mdns", json=MDNS_RECORD)
    assert r.status_code in (401, 403)
    assert not cache.values


def test_mdns_report_cache_failure_is_503(app_client):
    """A cache that refuses the write is surfaced rather than silently dropped."""
    with patch("oss.routers.devices.write_key", return_value=False):
        r = app_client.post("/devices/mdns", json=MDNS_RECORD, headers=headers)
    assert r.status_code == 503
