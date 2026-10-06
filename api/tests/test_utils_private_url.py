# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for core/utils.py — assert_private_url SSRF guard."""
import socket
from unittest.mock import patch

import pytest

from core.utils import assert_private_url, resolve_and_pin_private_url


class TestAssertPrivateUrl:
    """Tests for assert_private_url SSRF guard."""

    def test_private_192_allowed(self):
        """Does not raise for a 192.168.x.x private address."""
        assert_private_url("http://192.168.1.10/api")  # must not raise

    def test_private_10_allowed(self):
        """Does not raise for a 10.x.x.x private address."""
        assert_private_url("http://10.0.0.5/api")  # must not raise

    def test_private_172_allowed(self):
        """Does not raise for a 172.16.x.x private address."""
        assert_private_url("http://172.16.0.1/api")  # must not raise

    def test_loopback_rejected(self):
        """Raises ValueError for loopback address 127.0.0.1."""
        with pytest.raises(ValueError, match="disallowed"):
            assert_private_url("http://127.0.0.1/api")

    def test_link_local_rejected(self):
        """Raises ValueError for link-local 169.254.x.x address."""
        with pytest.raises(ValueError, match="disallowed"):
            assert_private_url("http://169.254.1.1/api")

    def test_public_ip_rejected(self):
        """Raises ValueError for a public IP address."""
        with pytest.raises(ValueError, match="disallowed"):
            assert_private_url("http://8.8.8.8/api")

    def test_empty_host_rejected(self):
        """Raises ValueError when the URL contains no host."""
        with pytest.raises(ValueError):
            assert_private_url("http:///api")

    def test_unsupported_scheme_rejected(self):
        """The LAN HTTP proxy rejects schemes its HTTP client cannot send."""
        with pytest.raises(ValueError, match="scheme must be http or https"):
            assert_private_url("ftp://192.168.1.10/status")

    def test_unresolvable_host_rejected(self):
        """Raises ValueError for a hostname that cannot be resolved."""
        with pytest.raises(ValueError, match="Cannot resolve host"):
            assert_private_url("http://this.host.does.not.exist.invalid/")


class TestResolveAndPinPrivateUrlRegressions:
    """Regression tests for the scenarios named in the SSRF-hardening audit.

    `assert_private_url` is a thin wrapper around `resolve_and_pin_private_url`
    that discards the pinned result — these tests call the pinning function
    directly since the property under test (what got pinned, not just whether
    validation passed) requires the return value.
    """

    def test_mixed_case_hostname_resolves_and_pins(self):
        """A mixed-case hostname still resolves (case doesn't affect DNS) and pins correctly.

        `urlparse` lowercases `.hostname` per stdlib-documented behavior, so
        resolution must be keyed off the lowercased form; confirm that and that
        the pinned URL carries the resolved IP.
        """
        fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.50", 0))]
        with patch(
            "core.utils.socket.getaddrinfo", return_value=fake_addrinfo
        ) as mock_resolve:
            pinned = resolve_and_pin_private_url("http://DEVICE.LOCAL/status")
        mock_resolve.assert_called_once()
        assert mock_resolve.call_args[0][0] == "device.local"
        assert pinned == "http://192.168.1.50/status"

    def test_userinfo_collision_pins_the_authority_host_not_the_username(self):
        """A hostname repeated in userinfo cannot fool the host replacement.

        `http://device.local@device.local/...` is the concrete bypass example
        named in the audit: a naive `url.replace(host, ip, 1)` would rewrite
        the *username* (the first textual occurrence) and leave the real
        authority host untouched and unpinned. Component-based reconstruction
        (rebuilding `netloc` from `parsed.username`/`parsed.password` plus the
        resolved address, rather than string-replacing into the original URL)
        makes this structurally impossible — assert the authority host in the
        result is the resolved IP, not the original hostname text.
        """
        fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.9", 0))]
        with patch("core.utils.socket.getaddrinfo", return_value=fake_addrinfo):
            pinned = resolve_and_pin_private_url("http://device.local@device.local/status")
        assert pinned == "http://device.local@10.0.0.9/status"

    def test_ipv6_loopback_literal_rejected(self):
        """IPv6 loopback literal [::1] is rejected the same as 127.0.0.1."""
        with pytest.raises(ValueError, match="disallowed"):
            assert_private_url("http://[::1]/status")

    def test_ipv6_private_literal_accepted_and_pinned(self):
        """A private IPv6 (ULA, fc00::/7) literal is accepted and pinned, bracketed."""
        pinned = resolve_and_pin_private_url("http://[fd00::1]/status")
        assert pinned == "http://[fd00::1]/status"

    def test_ipv6_only_hostname_resolves_via_aaaa_record(self):
        """A hostname with only an AAAA record (no A record) resolves via IPv6.

        The pre-fix implementation resolved via `socket.gethostbyname`, which
        is IPv4-only and would raise `gaierror` for an IPv6-only host. The
        current `getaddrinfo`-based resolution must succeed and pin the IPv6
        address, not silently fail the way the old implementation would have.
        """
        fake_addrinfo = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fd00::2", 0, 0, 0))]
        with patch("core.utils.socket.getaddrinfo", return_value=fake_addrinfo):
            pinned = resolve_and_pin_private_url("http://ipv6only.local/status")
        assert pinned == "http://[fd00::2]/status"

    def test_explicit_allowed_port_is_preserved_when_pinned(self):
        """An explicit allowed port (8443) on a private URL is preserved in the pinned URL."""
        pinned = resolve_and_pin_private_url("https://192.168.1.10:8443/status")
        assert pinned == "https://192.168.1.10:8443/status"

    def test_explicit_disallowed_port_rejected(self):
        """An explicit port outside the allowed set (80/443/8080/8443) is rejected."""
        with pytest.raises(ValueError, match="not permitted"):
            assert_private_url("http://192.168.1.10:9999/status")

    def test_dns_rebinding_uses_only_the_first_resolution(self):
        """DNS-rebinding simulation: a later, different resolution is never consulted.

        `resolve_and_pin_private_url` resolves exactly once and pins that
        address into the returned URL — it does not re-resolve. Simulate a
        rebinding DNS server that would answer with a private IP on a first
        lookup and a public/disallowed IP on a second: the mock is queued to
        do exactly that, and the assertions confirm both that the pinned
        result reflects the first (validated) answer and that no second
        resolution call happened within this function — the caller is
        responsible for actually using the pinned URL for its connection
        rather than reconnecting to the original hostname, which is the
        contract this "pin" exists to support.
        """
        private_response = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.77", 0))]
        public_response = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))]
        with patch(
            "core.utils.socket.getaddrinfo",
            side_effect=[private_response, public_response],
        ) as mock_resolve:
            pinned = resolve_and_pin_private_url("http://rebind.local/status")
        assert pinned == "http://192.168.1.77/status"
        mock_resolve.assert_called_once()
