# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Utility functions for request handling, logging, and shared pure logic."""
import ipaddress
import logging
import math
import secrets
import socket
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from fastapi import Request

logger = logging.getLogger(__name__)


def safe_float(value, default: float = 0.0, lo: float = -1e9, hi: float = 1e9) -> float:
    """Convert value to float, clamping to [lo, hi] and replacing NaN/Inf with default."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(f):
        return default
    return max(lo, min(hi, f))


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    if "_" not in string:
        return string
    words = string.split("_")
    return words[0] + "".join(w.capitalize() for w in words[1:])


def generate_token(nbytes: int = 24) -> str:
    """Generate a random URL-safe token string."""
    return secrets.token_urlsafe(nbytes)


_PRIVATE_URL_PORTS = {80, 443, 8080, 8443}


def _resolve_host_addresses(host: str) -> set:
    """Resolve a host to its DNS answers, exactly once. Shared by both address checks below."""
    try:
        candidates = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            candidates = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            }
        except socket.gaierror as exc:
            raise ValueError(f"Cannot resolve host {host!r}: {exc}") from exc
    if not candidates:
        raise ValueError(f"Cannot resolve host {host!r}")
    return candidates


def _private_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Resolve a host once and reject any non-private DNS answer."""
    candidates = _resolve_host_addresses(host)
    for candidate in candidates:
        if not candidate.is_private or candidate.is_loopback or candidate.is_link_local:
            raise ValueError(
                f"URL resolves to disallowed address {candidate} (must be private LAN)"
            )
    return sorted(candidates, key=str)[0]


def _outbound_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Resolve a host once and reject only loopback/link-local DNS answers.

    For an admin-configured *destination* the server calls out to (a forwarding
    target, a webhook) rather than a LAN device the server reaches on the
    operator's behalf. Unlike `_private_address`, a legitimate target here can be
    public internet (Brewfather, Thingspeak) or private LAN (a self-hosted Home
    Assistant instance) — both are ordinary configurations. Only loopback
    (127.0.0.0/8, ::1) and link-local (169.254.0.0/16, ::/10-scoped — this range
    is what every major cloud provider's metadata endpoint,
    169.254.169.254, lives in) are rejected, since neither is ever a legitimate
    forwarding destination and both are classic SSRF targets.
    """
    candidates = _resolve_host_addresses(host)
    for candidate in candidates:
        if candidate.is_loopback or candidate.is_link_local:
            raise ValueError(
                f"URL resolves to disallowed address {candidate} (loopback/link-local)"
            )
    return sorted(candidates, key=str)[0]


def _pin_url_to_address(parsed, ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    """Rebuild a parsed URL with its netloc replaced by a resolved, validated address."""
    address = f"[{ip}]" if ip.version == 6 else str(ip)
    userinfo = ""
    if parsed.username is not None:
        userinfo = parsed.username
        if parsed.password is not None:
            userinfo += f":{parsed.password}"
        userinfo += "@"
    netloc = f"{userinfo}{address}"
    if parsed.port is not None:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


@dataclass(frozen=True)
class OutboundUrl:
    """A forwarding destination pinned to a validated address."""

    url: str
    host_header: str
    sni_hostname: str


def resolve_and_pin_private_url(url: str) -> str:
    """Return a private-LAN URL rebuilt with its validated address pinned.

    Rejects loopback (127.x), link-local (169.254.x), and all public IPs to
    prevent SSRF attacks via administrator-configured device URLs. DNS is resolved
    exactly once; the returned URL contains that address rather than the hostname.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme must be http or https, got {parsed.scheme!r}")
    host = parsed.hostname or ""
    if not host:
        raise ValueError(f"Cannot resolve empty host in URL: {url!r}")
    ip = _private_address(host)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in _PRIVATE_URL_PORTS:
        raise ValueError(f"Port {port} is not permitted")
    return _pin_url_to_address(parsed, ip)


def assert_outbound_url_safe(url: str) -> None:
    """Validate an admin-configured forwarding target (Brewfather, a custom webhook).

    This is the persistence-time half of outbound validation. Delivery calls
    ``resolve_and_pin_outbound_url`` immediately before connecting, closing the
    DNS-rebinding gap while preserving hostname-based TLS.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme must be http or https, got {parsed.scheme!r}")
    host = parsed.hostname or ""
    if not host:
        raise ValueError(f"Cannot resolve empty host in URL: {url!r}")
    _outbound_address(host)


def resolve_and_pin_outbound_url(url: str) -> OutboundUrl:
    """Resolve a forwarding URL once and pin its eventual TCP peer.

    The original hostname remains available for HTTP ``Host`` and TLS SNI, so
    HTTPS certificate validation continues to verify the configured hostname.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme must be http or https, got {parsed.scheme!r}")
    host = parsed.hostname or ""
    if not host:
        raise ValueError(f"Cannot resolve empty host in URL: {url!r}")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Outbound URLs must not contain userinfo; use configured headers")
    address = _outbound_address(host)
    host_header = host if ":" not in host else f"[{host}]"
    if parsed.port is not None:
        host_header = f"{host_header}:{parsed.port}"
    return OutboundUrl(
        url=_pin_url_to_address(parsed, address),
        host_header=host_header,
        sni_hostname=host,
    )


def assert_private_url(url: str) -> None:
    """Validate that a URL targets a permitted private-LAN address."""
    resolve_and_pin_private_url(url)


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse a header or peer value as an IP address; None when it is not one."""
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def _is_trusted_proxy(peer: str | None, trusted: str) -> bool:
    """True when the direct peer address lies in one of the trusted networks."""
    address = _parse_ip(peer or "")
    if address is None:
        return False
    for entry in trusted.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            if address in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            logger.warning("Ignoring invalid TRUSTED_PROXIES entry: %r", entry)
    return False


def get_client_ip(request: Request) -> str:
    """Extract real client IP address from the request.

    Proxy headers are only trusted when TRUST_PROXY_HEADERS=true (default false)
    and the direct peer is inside TRUSTED_PROXIES (loopback and private ranges by
    default). A header value that is not a valid IP address is ignored.
    """
    from core.config import \
        get_settings  # pylint: disable=import-outside-toplevel
    settings = get_settings()
    peer = request.client.host if request.client else None
    if settings.trust_proxy_headers and _is_trusted_proxy(peer, settings.trusted_proxies):
        # Starlette's Headers is case-insensitive, but normalising here keeps
        # the policy correct for alternate ASGI request implementations too.
        headers = {key.lower(): value for key, value in request.headers.items()}
        if "x-real-ip" in headers:
            real_ip = _parse_ip(headers["x-real-ip"])
            if real_ip:
                return str(real_ip)
        if "x-forwarded-for" in headers:
            # Use the rightmost entry — it's set by the trusted proxy.
            # The leftmost entry is attacker-controlled in multi-hop deployments.
            client_ip = _parse_ip(headers["x-forwarded-for"].split(",")[-1])
            if client_ip:
                return str(client_ip)

    if request.client:
        return request.client.host

    return "unknown"


def truncate_ip(address: str | None) -> str:
    """Truncate a client IP to a coarser prefix before it is logged or stored.

    IPv4 keeps its first three octets and zeroes the last (a /24). IPv6 keeps
    its first 48 bits and zeroes the rest. An IPv4-mapped IPv6 address is
    truncated as IPv4. Anything that isn't a parseable IP address — including
    an empty string or ``None`` — returns ``"-"``.
    """
    if not address:
        return "-"
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return "-"
    mapped = parsed.ipv4_mapped if parsed.version == 6 else None
    if mapped is not None:
        parsed = mapped
    prefix = 24 if parsed.version == 4 else 48
    network = ipaddress.ip_network(f"{parsed}/{prefix}", strict=False)
    return str(network.network_address)
