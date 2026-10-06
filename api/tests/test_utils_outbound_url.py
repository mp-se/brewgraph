# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for core/utils.py — assert_outbound_url_safe SSRF guard.

Covers the integration-forwarding use case: an admin-configured destination
that is assumed public internet (Brewfather, a custom webhook) but may
incidentally be private LAN too — unlike assert_private_url, which requires
private LAN and would reject every real Brewfather/Thingspeak/etc. target.
"""
import pytest

from core.utils import assert_outbound_url_safe


class TestAssertOutboundUrlSafe:
    """Tests for assert_outbound_url_safe SSRF guard."""

    def test_public_ip_allowed(self):
        """Does not raise for a public IP address — the expected common case."""
        assert_outbound_url_safe("https://8.8.8.8/stream")  # must not raise

    def test_private_192_allowed(self):
        """Does not raise for a private-LAN target either (e.g. a self-hosted service)."""
        assert_outbound_url_safe("http://192.168.1.50:8123/api/hook")  # must not raise

    def test_loopback_rejected(self):
        """Raises ValueError for loopback address 127.0.0.1."""
        with pytest.raises(ValueError, match="disallowed"):
            assert_outbound_url_safe("http://127.0.0.1/hook")

    def test_ipv6_loopback_rejected(self):
        """Raises ValueError for IPv6 loopback ::1."""
        with pytest.raises(ValueError, match="disallowed"):
            assert_outbound_url_safe("http://[::1]/hook")

    def test_link_local_rejected(self):
        """Raises ValueError for link-local 169.254.x.x, which covers the cloud-metadata
        endpoint (169.254.169.254) every major cloud provider uses."""
        with pytest.raises(ValueError, match="disallowed"):
            assert_outbound_url_safe("http://169.254.169.254/latest/meta-data/")

    def test_ftp_scheme_rejected(self):
        """Raises ValueError for a non-http(s) scheme."""
        with pytest.raises(ValueError, match="scheme"):
            assert_outbound_url_safe("ftp://example.com/file")

    def test_empty_host_rejected(self):
        """Raises ValueError when the URL contains no host."""
        with pytest.raises(ValueError):
            assert_outbound_url_safe("http:///hook")

    def test_unresolvable_host_rejected(self):
        """Raises ValueError for a hostname that cannot be resolved."""
        with pytest.raises(ValueError, match="Cannot resolve host"):
            assert_outbound_url_safe("http://this.host.does.not.exist.invalid/")

    def test_arbitrary_port_allowed(self):
        """No port restriction — unlike assert_private_url, a forwarding target may
        reasonably run on any port."""
        assert_outbound_url_safe("http://8.8.8.8:9999/hook")  # must not raise

    def test_returns_nothing(self):
        """Deliberately validate-only: unlike resolve_and_pin_private_url, there is no
        pinned/rewritten URL to return — the caller connects by hostname, so TLS
        certificate verification still works."""
        assert assert_outbound_url_safe("https://8.8.8.8/hook") is None
