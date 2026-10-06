# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Shared mechanics for the four measurement-forwarding job pairs
(gravity/pressure/pour/temp — see oss/jobs/gravity_forward.py and its
pressure/pour/temp siblings).

Each measurement has its own queue, its own Integration query, and its own
subject key (device_id for gravity/pressure/temp, tap_id for pour) — those
stay in each job module. What is genuinely shared is the measurement-agnostic
plumbing: `${key}` template substitution over a plain `values: dict` (rather
than device/reading objects, so pour's tap-keyed shape fits the same helper
as the three device-keyed measurements), and the HTTP POST/GET dispatch used
to deliver a rendered custom_forward payload.
"""
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlparse

import httpx

from core.cache import delete_key, set_key_if_absent
from core.log import LogLevel, system_log_scheduler
from core.utils import assert_outbound_url_safe, resolve_and_pin_outbound_url

logger = logging.getLogger(__name__)

# "skipped": nothing was sent on purpose (e.g. a per-device minimum interval) --
# neither a success nor a failure, so the target's counters are left alone.
DeliveryOutcome = Literal["delivered", "blocked", "failed", "skipped"]
_AUTO_DISABLE_THRESHOLD = 3


def as_uuid(value):
    """Coerce a string or uuid.UUID to a uuid.UUID object.

    A queue item's subject/tenant ids round-trip through JSON as plain
    strings. SQLAlchemy's `Uuid(as_uuid=True)` column type — used for every
    id column these jobs look up or filter by — needs an actual `uuid.UUID`
    to bind on dialects with no native UUID storage (SQLite): its bind
    processor calls `.hex` on the value, which a plain `str` does not have.
    Raises `ValueError` for a value that isn't a valid UUID either way, so
    callers can treat it the same as any other malformed queue item.
    """
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def retry_or_dead_letter(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    item: dict, raw, *, queue: str, dead_letter: str, max_retries: int,
    label: str, push, acknowledge, log: logging.Logger,
) -> None:
    """Apply the common reliable-forward retry state transition.

    The queue-specific modules own their Redis adapters and test doubles; this
    helper owns the invariant shared by every measurement: acknowledge only
    after the retry/dead-letter hand-off has succeeded.
    """
    attempts = item.get("attempts", 0) + 1
    if attempts < max_retries:
        item["attempts"] = attempts
        pushed = push(queue, json.dumps(item))
        action = "requeue"
    else:
        log.warning("%s: dead-lettering item after %d attempts", label, attempts)
        pushed = push(dead_letter, raw.decode() if isinstance(raw, bytes) else raw)
        action = "dead-letter"

    if pushed:
        acknowledge(raw)
    else:
        log.error(
            "%s: failed to %s item, leaving in processing for the reclaim sweep",
            label, action,
        )


def reclaim_stale_items(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    *, processing: str, processing_timestamps: str, queue: str,
    visibility_timeout: int, now, list_stale, reclaim,
) -> int:
    """Reclaim stale processing entries using a queue module's Redis adapters."""
    stale = list_stale(processing_timestamps, now() - visibility_timeout)
    return sum(
        1 for raw in stale
        if reclaim(processing, processing_timestamps, queue, raw)
    )


_TIMEOUT = httpx.Timeout(10.0, connect=5.0, read=10.0)
_JSON_HEADERS = {"Content-Type": "application/json"}

_http_client_box: list = []
_pinned_https_client_box: list = []


def get_http_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient for forwarding POSTs, creating it lazily.

    A single drain can make many HTTP calls across several targets; opening a
    fresh AsyncClient (and TLS handshake) per call throws away connection
    reuse at that volume. A one-item list stands in for a module-level
    singleton without a `global` rebind.
    """
    if not _http_client_box:
        _http_client_box.append(httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False))
    return _http_client_box[0]


def get_pinned_https_client() -> httpx.AsyncClient:
    """Return the HTTPS client used for DNS-pinned forwarding destinations.

    A pinned request's URL origin is its resolved IP while TLS identity is the
    original hostname supplied through ``sni_hostname``.  Keeping idle
    connections would let httpx reuse a connection for another configured
    hostname that resolves to that same IP, skipping that hostname's own TLS
    handshake.  No idle connections makes each HTTPS delivery authenticate its
    configured hostname while retaining the regular HTTP client's reuse.
    """
    if not _pinned_https_client_box:
        _pinned_https_client_box.append(
            httpx.AsyncClient(
                timeout=_TIMEOUT,
                follow_redirects=False,
                limits=httpx.Limits(max_keepalive_connections=0),
            )
        )
    return _pinned_https_client_box[0]


def _pinned_request(url: str, headers: dict | None) -> tuple[str, dict, dict]:
    """Build a request that connects to a validated IP but retains HTTPS identity."""
    target = resolve_and_pin_outbound_url(url)
    safe_headers = {
        key: value for key, value in (headers or {}).items() if key.lower() != "host"
    }
    safe_headers["Host"] = target.host_header
    return target.url, safe_headers, {"sni_hostname": target.sni_hostname}


async def close_http_client() -> None:
    """Close forwarding clients during application shutdown."""
    for box in (_http_client_box, _pinned_https_client_box):
        if box:
            client = box.pop()
            await client.aclose()


def recover_forwarding_error(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    db, *, label: str, subject_id, item: dict, raw, retry,
    log: logging.Logger, exc: Exception,
) -> None:
    """Reset a failed worker session before handing one queue item to retry logic.

    A failed SQLAlchemy commit leaves its Session in a pending-rollback state.
    Workers process several queue items with one session, so omitting this reset
    turns one database outage into failures for every later item in that drain.
    """
    db().rollback()
    log.error("%s: error processing item %s: %s", label, subject_id, exc)
    retry(item, raw)


# Template tokens that hold a number. A missing (None) one renders as the JSON
# literal `null`, so a JSON template stays valid JSON; a missing text token
# renders as an empty string. A forward never substitutes a made-up value.
NUMERIC_TOKENS = frozenset({
    "gravity", "temperature", "angle", "velocity", "battery", "rssi",
    "pressure", "pourAmount", "volumeRemaining",
})


def render_template(template: str, values: dict) -> str:
    """Plain ${key} string substitution — deliberately not a general-purpose
    template engine, since the string is user-supplied and rendered
    server-side on every forward. A None value renders as `null` for a
    numeric token and as an empty string for any other."""
    result = template
    for key, value in values.items():
        if value is None:
            text = "null" if key in NUMERIC_TOKENS else ""
        else:
            text = str(value)
        result = result.replace(f"${{{key}}}", text)
    return result


async def http_post(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    url: str, payload, subject_id, label: str, *, raw: str = "", headers: dict | None = None
) -> bool:
    """POST a rendered payload — JSON if `payload` is not None, else `raw` as
    plain text (a custom_forward template that didn't parse as JSON)."""
    try:
        pinned_url, pinned_headers, extensions = _pinned_request(url, headers)
        client = (
            get_pinned_https_client()
            if urlparse(pinned_url).scheme == "https"
            else get_http_client()
        )
        if payload is not None:
            merged = {**_JSON_HEADERS, **pinned_headers}
            resp = await client.post(
                pinned_url, headers=merged, json=payload, extensions=extensions
            )
        else:
            merged = {"Content-Type": "text/plain", **pinned_headers}
            resp = await client.post(
                pinned_url, headers=merged, content=raw, extensions=extensions
            )
        logger.info("%s subject=%s → HTTP %s", label, subject_id, resp.status_code)
        return 200 <= resp.status_code < 300
    except (httpx.ReadTimeout, httpx.ConnectError, httpx.ConnectTimeout) as exc:
        logger.warning("%s subject=%s: %s", label, subject_id, exc)
    except (httpx.RequestError, ValueError) as exc:
        logger.warning("%s subject=%s: %s", label, subject_id, exc)
    return False


async def http_get(url: str, query: str, headers: dict, subject_id, label: str) -> bool:
    """GET a custom_forward target, merging the rendered template as query params
    onto the destination URL (query may itself already carry params)."""
    try:
        params = parse_qsl(query, keep_blank_values=True)
        separator = "&" if "?" in url else "?"
        full_url = f"{url}{separator}{urlencode(params)}" if params else url
        pinned_url, pinned_headers, extensions = _pinned_request(full_url, headers)
        client = (
            get_pinned_https_client()
            if urlparse(pinned_url).scheme == "https"
            else get_http_client()
        )
        resp = await client.get(pinned_url, headers=pinned_headers, extensions=extensions)
        logger.info("%s subject=%s → HTTP %s", label, subject_id, resp.status_code)
        return 200 <= resp.status_code < 300
    except (httpx.ReadTimeout, httpx.ConnectError, httpx.ConnectTimeout) as exc:
        logger.warning("%s subject=%s: %s", label, subject_id, exc)
    except (httpx.RequestError, ValueError) as exc:
        logger.warning("%s subject=%s: %s", label, subject_id, exc)
    return False


async def deliver_custom(
    config: dict, values: dict, subject_id, label: str,
) -> DeliveryOutcome:
    """Deliver a custom_forward target: render config['template'] against `values`
    and send it with config['method'] (default POST). "blocked" on an SSRF-blocked
    destination -- not retried, but distinct from "delivered" for the per-target
    consecutive_failures counter (see apply_delivery_outcome)."""
    url = config.get("url", "")
    try:
        assert_outbound_url_safe(url)
    except ValueError as exc:
        logger.warning("%s: blocked custom_forward URL for %s: %s", label, subject_id, exc)
        return "blocked"  # Don't retry a blocked destination
    rendered = render_template(config.get("template") or "", values)
    headers = dict(config.get("headers") or {})
    method = config.get("method", "POST")

    if method == "GET":
        get_ok = await http_get(url, rendered, headers, subject_id, label)
        return "delivered" if get_ok else "failed"

    try:
        payload = json.loads(rendered)
    except (json.JSONDecodeError, ValueError):
        payload = None
    ok = await http_post(url, payload, subject_id, label, raw=rendered, headers=headers)
    return "delivered" if ok else "failed"


async def apply_delivery_outcome(
    integration, outcome: DeliveryOutcome, on_disable=None,
) -> None:
    """Update integration.consecutive_failures per one delivery outcome, auto-disabling
    the target once it reaches _AUTO_DISABLE_THRESHOLD consecutive failures: a target
    that fails that many attempts in a row is broken, not flaky, and continuing to
    retry it (and log each attempt) serves nothing. A successful delivery resets the
    counter to 0. Shared by all four measurement-forward jobs' `_forward()` functions,
    so this logic exists exactly once regardless of measurement. `on_disable`, if
    given, is an async callable awaited with the integration after it's disabled and
    the system-log entry below has fired -- an extension point for a caller that needs
    to react further (e.g. raising its own in-app notification and publishing a
    real-time update, both of which need to await I/O); this module itself passes
    nothing. Does not commit -- the caller commits once after applying every target's
    outcome for one queue item, so all per-target updates for that item land in a
    single transaction."""
    if outcome == "skipped":
        return
    if outcome == "delivered":
        integration.consecutive_failures = 0
        integration.last_success_at = datetime.now(UTC)
        integration.last_failure_code = None
        return
    integration.last_failure_at = datetime.now(UTC)
    integration.last_failure_code = (
        "outbound_blocked" if outcome == "blocked" else "delivery_failed"
    )
    integration.consecutive_failures = (integration.consecutive_failures or 0) + 1
    if integration.consecutive_failures >= _AUTO_DISABLE_THRESHOLD:
        integration.enabled = False
        integration.disabled_reason = "delivery_failures"
        integration.consecutive_failures = 0
        system_log_scheduler(
            f"integration {integration.name!r} ({integration.id}) auto-disabled after "
            f"{_AUTO_DISABLE_THRESHOLD} consecutive delivery failures",
            level=LogLevel.WARNING,
        )
        if on_disable is not None:
            await on_disable(integration)


# Brewfather ignores a device that logs more often than this.
BREWFATHER_FORWARD_MIN_INTERVAL_SECONDS = 900
_BREWFATHER_LAST_PREFIX = "brewfather_forward_last:"


def without_missing(payload: dict) -> dict:
    """Drop keys whose value is None: a forward never invents a value the
    device did not send."""
    return {key: value for key, value in payload.items() if value is not None}


async def deliver_built_in(
    integration, payload: dict, subject_id, label: str, *, once_per_interval: bool = False,
) -> DeliveryOutcome:
    """Deliver a built-in (fixed payload shape) target: check the destination, then POST
    `payload` as JSON. "blocked" on an SSRF-blocked destination -- not retried.

    With `once_per_interval` (brewfather_forward, for every measurement) at most one
    request per (integration, device) goes out per BREWFATHER_FORWARD_MIN_INTERVAL_SECONDS,
    because Brewfather ignores more. The marker is set before the request and cleared if
    it fails, so a retry is not suppressed by an attempt that never landed; a request
    skipped by the window is "skipped", neither a success nor a failure.
    """
    url = integration.config.get("url", "")
    try:
        assert_outbound_url_safe(url)
    except ValueError as exc:
        logger.warning(
            "%s: blocked %s URL for device %s: %s", label, integration.type, subject_id, exc,
        )
        return "blocked"  # Don't retry a blocked destination
    last_key = f"{_BREWFATHER_LAST_PREFIX}{integration.id}:{subject_id}"
    if once_per_interval and not set_key_if_absent(
        last_key, "1", ttl=BREWFATHER_FORWARD_MIN_INTERVAL_SECONDS
    ):
        return "skipped"
    ok = await http_post(url, payload, subject_id, integration.type)
    if not ok and once_per_interval:
        delete_key(last_key)
    return "delivered" if ok else "failed"
