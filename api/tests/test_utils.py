# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for core/utils.py — get_client_ip header extraction."""
from unittest.mock import MagicMock, patch

import pytest

from core.utils import get_client_ip, truncate_ip


def _request(headers: dict, client_host: str | None = None) -> MagicMock:
    """Build a minimal mock Request object."""
    req = MagicMock()
    req.headers = headers
    if client_host is not None:
        req.client = MagicMock()
        req.client.host = client_host
    else:
        req.client = None
    return req


class TestGetClientIp:
    """Tests for get_client_ip header extraction logic."""

    @pytest.fixture(autouse=True)
    def trust_proxy(self):
        """Patch settings to trust proxy headers for all tests in this class."""
        with patch("core.config.get_settings") as mock_settings:
            mock_settings.return_value.trust_proxy_headers = True
            mock_settings.return_value.trusted_proxies = (
                "127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7")
            yield

    def test_x_real_ip_takes_priority(self):
        """X-Real-IP header takes priority over X-Forwarded-For."""
        req = _request({"x-real-ip": "1.2.3.4", "x-forwarded-for": "9.9.9.9"}, "10.0.0.1")
        assert get_client_ip(req) == "1.2.3.4"

    def test_x_real_ip_stripped_of_whitespace(self):
        """X-Real-IP value is stripped of surrounding whitespace."""
        req = _request({"x-real-ip": "  5.6.7.8  "}, "10.0.0.1")
        assert get_client_ip(req) == "5.6.7.8"

    def test_x_real_ip_empty_falls_through_to_forwarded_for(self):
        """Empty X-Real-IP causes fallthrough to X-Forwarded-For (rightmost entry used)."""
        req = _request({"x-real-ip": "  ", "x-forwarded-for": "2.2.2.2, 3.3.3.3"}, "10.0.0.1")
        assert get_client_ip(req) == "3.3.3.3"

    def test_x_forwarded_for_rightmost_ip_used(self):
        """Rightmost IP in X-Forwarded-For list is returned (set by trusted proxy)."""
        req = _request({"x-forwarded-for": "2.2.2.2, 3.3.3.3"}, "10.0.0.1")
        assert get_client_ip(req) == "3.3.3.3"

    def test_x_forwarded_for_single_ip(self):
        """Single IP in X-Forwarded-For is returned directly."""
        req = _request({"x-forwarded-for": "4.4.4.4"}, "10.0.0.1")
        assert get_client_ip(req) == "4.4.4.4"

    def test_x_forwarded_for_empty_falls_through_to_client(self):
        """Blank X-Forwarded-For causes fallthrough to client.host."""
        req = _request({"x-forwarded-for": "  "}, "10.0.0.1")
        assert get_client_ip(req) == "10.0.0.1"

    def test_direct_client_host_used_as_fallback(self):
        """client.host is used when no proxy headers are present."""
        req = _request({}, "192.168.1.1")
        assert get_client_ip(req) == "192.168.1.1"

    def test_no_headers_no_client_returns_unknown(self):
        """Returns 'unknown' when there are no headers and no client."""
        req = _request({}, client_host=None)
        assert get_client_ip(req) == "unknown"


class TestTrustedProxies:
    """Proxy headers are believed only from a trusted direct peer, and only if valid IPs."""

    @pytest.fixture(autouse=True)
    def trust_proxy(self):
        """Trust proxy headers, with the default trusted networks."""
        with patch("core.config.get_settings") as mock_settings:
            mock_settings.return_value.trust_proxy_headers = True
            mock_settings.return_value.trusted_proxies = (
                "127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7")
            self.settings = mock_settings.return_value
            yield

    @pytest.mark.parametrize("peer", ["127.0.0.1", "::1", "10.1.2.3", "172.16.0.5",
                                      "172.31.255.1", "192.168.1.9", "fd12::1"])
    def test_private_peer_is_trusted(self, peer):
        """Loopback and private-range peers have their headers believed."""
        assert get_client_ip(_request({"x-real-ip": "8.8.8.8"}, peer)) == "8.8.8.8"

    @pytest.mark.parametrize("peer", ["8.8.4.4", "172.32.0.1", "172.15.0.1", "2001:db8::1"])
    def test_public_peer_headers_ignored(self, peer):
        """A spoofed header from a non-proxy peer is ignored; the peer address is used."""
        req = _request({"x-real-ip": "1.1.1.1", "x-forwarded-for": "2.2.2.2"}, peer)
        assert get_client_ip(req) == peer

    def test_no_peer_headers_ignored(self):
        """Without a direct peer address the headers are not trusted."""
        assert get_client_ip(_request({"x-real-ip": "1.1.1.1"}, None)) == "unknown"

    def test_invalid_real_ip_falls_to_forwarded_for(self):
        """A non-IP X-Real-IP is ignored."""
        req = _request({"x-real-ip": "not-an-ip", "x-forwarded-for": "3.3.3.3"}, "10.0.0.1")
        assert get_client_ip(req) == "3.3.3.3"

    def test_invalid_headers_fall_back_to_peer(self):
        """Garbage in both headers yields the peer address."""
        req = _request({"x-real-ip": "x", "x-forwarded-for": "1.1.1.1, <script>"}, "10.0.0.1")
        assert get_client_ip(req) == "10.0.0.1"

    def test_custom_trusted_proxies(self):
        """TRUSTED_PROXIES narrows trust to the configured addresses."""
        self.settings.trusted_proxies = "10.0.0.2"
        assert get_client_ip(_request({"x-real-ip": "9.9.9.9"}, "10.0.0.3")) == "10.0.0.3"
        assert get_client_ip(_request({"x-real-ip": "9.9.9.9"}, "10.0.0.2")) == "9.9.9.9"

    def test_invalid_entry_ignored(self):
        """A malformed TRUSTED_PROXIES entry is skipped, not fatal."""
        self.settings.trusted_proxies = "bogus,10.0.0.0/8"
        assert get_client_ip(_request({"x-real-ip": "9.9.9.9"}, "10.0.0.3")) == "9.9.9.9"


class TestTruncateIp:
    """Tests for truncate_ip — coarsening a client IP before it is logged/stored."""

    def test_ipv4_zeroes_last_octet(self):
        """IPv4 keeps the first three octets and zeroes the last."""
        assert truncate_ip("203.0.113.77") == "203.0.113.0"

    def test_ipv6_keeps_first_48_bits(self):
        """IPv6 keeps its first 48 bits and zeroes the rest."""
        assert truncate_ip("2001:db8:1234:5678::1") == "2001:db8:1234::"

    def test_ipv4_mapped_ipv6_truncated_as_ipv4(self):
        """An IPv4-mapped IPv6 address is truncated using the IPv4 rule."""
        assert truncate_ip("::ffff:198.51.100.23") == "198.51.100.0"

    def test_non_ip_string_returns_dash(self):
        """A non-IP string (e.g. TestClient's default host) returns '-'."""
        assert truncate_ip("testclient") == "-"

    def test_empty_string_returns_dash(self):
        """An empty string returns '-'."""
        assert truncate_ip("") == "-"

    def test_none_returns_dash(self):
        """None returns '-' rather than raising."""
        assert truncate_ip(None) == "-"
