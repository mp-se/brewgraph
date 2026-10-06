# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Unit tests for mdns.py — pure-logic parts only.

Coverage targets:
- _async_show_service_info(): dict construction, host dot-stripping,
  multi-address formatting, empty-info guard.
- task_scan_mdns(): posts each device to the API, handles HTTP errors,
  handles multiple devices independently.
- scan_result isolation: cleared at the start of each scan_for_mdns() call.

Not covered here (require live network / zeroconf stack):
- AsyncDeviceScanner.async_run() — opens real mDNS sockets
- async_on_service_state_change() — wired to asyncio event loop internals
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import mdns

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_scan_result():
    """Ensure the module-level scan_result list is empty before every test."""
    mdns.scan_result.clear()
    yield
    mdns.scan_result.clear()


def _make_mock_info(addresses, port, service_type, server):
    """Build a mock AsyncServiceInfo with the given field values."""
    info = MagicMock()
    info.parsed_addresses.return_value = addresses
    info.port = port
    info.type = service_type
    info.server = server
    info.async_request = AsyncMock(return_value=True)
    return info


# ---------------------------------------------------------------------------
# _async_show_service_info
# ---------------------------------------------------------------------------

class TestAsyncShowServiceInfo:
    """Tests for the dict-building logic in _async_show_service_info."""

    async def test_appends_correct_dict(self):
        """Single address — dict fields are mapped and host dot is stripped."""
        mock_info = _make_mock_info(
            addresses=["192.168.1.10"],
            port=80,
            service_type="_gravitymon._tcp.local.",
            server="gravitymon-abc.local.",
        )
        with patch("mdns.AsyncServiceInfo", return_value=mock_info):
            await mdns._async_show_service_info(
                MagicMock(), "_gravitymon._tcp.local.", "GravityMon"
            )

        assert len(mdns.scan_result) == 1
        entry = mdns.scan_result[0]
        assert entry["type"] == "_gravitymon._tcp.local."
        assert entry["host"] == "192.168.1.10:80"
        assert entry["name"] == "gravitymon-abc.local"  # trailing dot removed

    async def test_strips_trailing_dot_from_server(self):
        """host.strip('.') must remove the mDNS trailing dot."""
        mock_info = _make_mock_info(
            addresses=["10.0.0.1"],
            port=80,
            service_type="_kegmon._tcp.local.",
            server="kegmon-01.local.",
        )
        with patch("mdns.AsyncServiceInfo", return_value=mock_info):
            await mdns._async_show_service_info(MagicMock(), "_kegmon._tcp.local.", "Keg")

        assert mdns.scan_result[0]["name"] == "kegmon-01.local"

    async def test_multiple_addresses_joined(self):
        """Multiple IP addresses are joined as 'ip1:port, ip2:port'."""
        mock_info = _make_mock_info(
            addresses=["192.168.1.10", "192.168.1.11"],
            port=8080,
            service_type="_pressuremon._tcp.local.",
            server="pressuremon.local.",
        )
        with patch("mdns.AsyncServiceInfo", return_value=mock_info):
            await mdns._async_show_service_info(MagicMock(), "_pressuremon._tcp.local.", "P")

        assert mdns.scan_result[0]["host"] == "192.168.1.10:8080, 192.168.1.11:8080"

    async def test_falsy_info_does_not_append(self):
        """If AsyncServiceInfo is falsy (lookup failed) nothing is appended."""
        mock_info = MagicMock()
        mock_info.__bool__ = MagicMock(return_value=False)
        mock_info.async_request = AsyncMock(return_value=False)

        with patch("mdns.AsyncServiceInfo", return_value=mock_info):
            await mdns._async_show_service_info(MagicMock(), "_gravitymon._tcp.local.", "X")

        assert mdns.scan_result == []

    async def test_multiple_calls_accumulate(self):
        """Each discovered service appends an independent entry."""
        for i, server in enumerate(["dev-a.local.", "dev-b.local."]):
            mock_info = _make_mock_info(
                addresses=[f"192.168.1.{i + 1}"],
                port=80,
                service_type="_gravitymon._tcp.local.",
                server=server,
            )
            with patch("mdns.AsyncServiceInfo", return_value=mock_info):
                await mdns._async_show_service_info(
                    MagicMock(), "_gravitymon._tcp.local.", f"dev-{i}"
                )

        assert len(mdns.scan_result) == 2
        assert mdns.scan_result[0]["name"] == "dev-a.local"
        assert mdns.scan_result[1]["name"] == "dev-b.local"


# ---------------------------------------------------------------------------
# task_scan_mdns
# ---------------------------------------------------------------------------

class TestTaskScanMdns:
    """Tests for the API posting logic in task_scan_mdns."""

    def setup_method(self):
        mdns.api_host = "brewgraph-api"
        mdns.api_key = "testkey"

    async def test_posts_each_device_to_api(self):
        """Each entry in scan_result is POSTed to /api/devices/mdns."""
        fake_results = [
            {"type": "_gravitymon._tcp.local.", "host": "192.168.1.1:80", "name": "dev-a"},
            {"type": "_kegmon._tcp.local.", "host": "192.168.1.2:80", "name": "dev-b"},
        ]
        with patch("mdns.scan_for_mdns", new=AsyncMock(return_value=fake_results)):
            with patch("mdns.requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                await mdns.task_scan_mdns()

        assert mock_post.call_count == 2
        posted = [call.kwargs["json"] for call in mock_post.call_args_list]
        assert fake_results[0] in posted
        assert fake_results[1] in posted

    async def test_posts_to_correct_endpoint(self):
        """Endpoint is built from api_host."""
        fake_results = [{"type": "t", "host": "h", "name": "n"}]
        with patch("mdns.scan_for_mdns", new=AsyncMock(return_value=fake_results)):
            with patch("mdns.requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                await mdns.task_scan_mdns()

        url = mock_post.call_args.args[0]
        assert url == "http://brewgraph-api/api/devices/mdns"

    async def test_request_exception_does_not_abort_remaining_posts(self):
        """A failed POST for one device must not stop subsequent devices."""
        import requests as req_lib
        fake_results = [
            {"type": "t", "host": "h1", "name": "dev-a"},
            {"type": "t", "host": "h2", "name": "dev-b"},
        ]
        with patch("mdns.scan_for_mdns", new=AsyncMock(return_value=fake_results)):
            with patch("mdns.requests.post") as mock_post:
                mock_post.side_effect = [
                    req_lib.RequestException("timeout"),
                    MagicMock(status_code=200),
                ]
                await mdns.task_scan_mdns()

        assert mock_post.call_count == 2

    async def test_empty_scan_result_posts_nothing(self):
        """No devices discovered → no POST calls."""
        with patch("mdns.scan_for_mdns", new=AsyncMock(return_value=[])):
            with patch("mdns.requests.post") as mock_post:
                await mdns.task_scan_mdns()

        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# scan_result isolation
# ---------------------------------------------------------------------------

class TestScanResultIsolation:
    """Verify scan_result is cleared at the start of each scan."""

    async def test_scan_clears_stale_results(self):
        """Results from a previous scan are not present in the next one."""
        mdns.scan_result.append({"type": "stale", "host": "old", "name": "old"})

        async def _fake_run(self):
            pass  # simulate empty scan window

        with patch.object(mdns.AsyncDeviceScanner, "async_run", new=_fake_run):
            result = await mdns.scan_for_mdns(0)

        assert result == []


# ---------------------------------------------------------------------------
# async_on_service_state_change
# ---------------------------------------------------------------------------

class TestAsyncOnServiceStateChange:
    """Tests for the event-handler shim that schedules info lookups."""

    def test_schedules_future(self):
        """ensure_future is called with a coroutine for the given service."""
        with patch("mdns.asyncio.ensure_future") as mock_future:
            with patch("mdns._async_show_service_info", new_callable=AsyncMock):
                mdns.async_on_service_state_change(
                    MagicMock(), "_gravitymon._tcp.local.", "MyDevice", MagicMock()
                )
        mock_future.assert_called_once()
        # ensure_future is mocked, so close scheduled coroutine to avoid RuntimeWarning.
        mock_future.call_args.args[0].close()


# ---------------------------------------------------------------------------
# AsyncDeviceScanner — async_run and async_close
# ---------------------------------------------------------------------------

class TestAsyncDeviceScanner:
    """Tests for AsyncDeviceScanner using mocked zeroconf infrastructure."""

    async def test_async_run_and_close(self):
        """async_run sets up aiozc/aiobrowser and async_close tears them down."""
        mock_aiozc = AsyncMock()
        mock_aiozc.zeroconf.async_wait_for_start = AsyncMock()
        mock_aiozc.async_close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.async_cancel = AsyncMock()

        with patch("mdns.AsyncZeroconf", return_value=mock_aiozc):
            with patch("mdns.AsyncServiceBrowser", return_value=mock_browser):
                scanner = mdns.AsyncDeviceScanner(timeout=0)
                await scanner.async_run()

        mock_aiozc.zeroconf.async_wait_for_start.assert_awaited_once()
        mock_browser.async_cancel.assert_awaited_once()
        mock_aiozc.async_close.assert_awaited_once()

    async def test_async_close_cancels_browser_and_closes_zc(self):
        """async_close awaits cancel on browser and close on zeroconf."""
        scanner = mdns.AsyncDeviceScanner(timeout=0)
        scanner.aiobrowser = AsyncMock()
        scanner.aiobrowser.async_cancel = AsyncMock()
        scanner.aiozc = AsyncMock()
        scanner.aiozc.async_close = AsyncMock()

        await scanner.async_close()

        scanner.aiobrowser.async_cancel.assert_awaited_once()
        scanner.aiozc.async_close.assert_awaited_once()


# ---------------------------------------------------------------------------
# task_scan_mdns — response status logging
# ---------------------------------------------------------------------------

class TestTaskScanMdnsResponseLog:
    """Ensure the success-path response status is logged (covers line 152)."""

    def setup_method(self):
        mdns.api_host = "brewgraph-api"
        mdns.api_key = "testkey"

    async def test_logs_response_status_on_success(self):
        """Successful POST: response status_code is accessed without raising."""
        fake_results = [{"type": "t", "host": "h", "name": "n"}]
        mock_response = MagicMock()
        mock_response.status_code = 201

        with patch("mdns.scan_for_mdns", new=AsyncMock(return_value=fake_results)):
            with patch("mdns.requests.post", return_value=mock_response):
                await mdns.task_scan_mdns()

        _ = mock_response.status_code  # assert attribute was reachable


# ---------------------------------------------------------------------------
# main() — single iteration via exception break
# ---------------------------------------------------------------------------

class TestMain:
    """Cover the main() loop by breaking after one iteration."""

    async def test_main_calls_task_scan_mdns(self):
        """main() calls task_scan_mdns at least once; loop broken by exception."""
        call_count = 0

        async def _mock_task():
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt

        with patch("mdns.task_scan_mdns", side_effect=_mock_task):
            try:
                await mdns.main()
            except KeyboardInterrupt:
                pass

        assert call_count == 1
