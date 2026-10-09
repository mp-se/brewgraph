# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""API key authentication middleware for BrewGraph API."""
import hmac
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.cache import delete_key, exist_key, increment_key, key_ttl
from core.config import get_settings
from core.errors import ApiError
from core.log import system_log_security
from core.utils import get_client_ip, truncate_ip
from oss.extensions.throttle import ThrottleLimits, oss_throttle_provider

logger = logging.getLogger(__name__)

oauth2_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    """Per-request auth context populated during authentication.

    Limits are held in a resource-keyed mapping rather than as one field per
    resource. The mapping is the quota provider's contract
    (``oss.extensions.quota``); a field named ``max_batches`` is not, because it
    bakes a fixed list of limitable resources into shared code and has to be
    edited here whenever a deployment limits something new. Absent key
    means ``-1``, and ``-1`` means unlimited, which is the whole answer for a
    self-hosted instance: one operator, nothing to ration.
    """

    retention_days: int = field(default=-1)
    ingest_interval_seconds: int = field(default=300)
    quota_limits: dict[str, int] = field(default_factory=dict)

    def quota_limit(self, resource: str) -> int:
        """Return the caller's limit for ``resource``; -1 (unlimited) if unset."""
        return self.quota_limits.get(resource, -1)

    def can(self, capability: str) -> bool:  # pylint: disable=unused-argument
        """Return whether the caller may use ``capability``.

        What a principal may use is the same class of fact as how much they may
        store, so it is resolved by the same lookup and carried on the same
        object rather than by a parallel permission system.

        **The answer here is always yes, and that is the finished answer.** This
        is a single-operator instance: there is no second principal to
        distinguish, so every capability name is permitted, including ones this
        codebase never defines. It is deliberately total — not a stub, not an
        unimplemented hook.

        The method exists because a deployment with more than one principal
        needs *somewhere* to answer differently, and that answer belongs on the
        auth context next to quotas and retention. Shared code therefore never
        passes a literal: callers that care resolve the *route* to a capability
        name through their own table and pass the result in.
        """
        return True


def check_quota(current: int, auth: AuthContext, resource: str) -> None:
    """Raise HTTP 403 if ``resource`` is at or over the caller's limit.

    Quota is a policy provider with a meaningful single-instance answer —
    unlimited — so enforcement lives here rather than at each call site, and
    the limits this instance carries are simply always -1.

    Takes the context and a resource *name* rather than a pre-read integer, so
    call sites no longer have to know a field called ``auth.max_taps`` exists.
    That indirection is the point: adding a limitable resource is now a change
    in the provider, not in this signature and every caller of it.
    """
    limit = auth.quota_limit(resource)
    if limit != -1 and current >= limit:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            error="quota_exceeded",
            detail=f"{resource} quota of {limit} reached",
        )


def retry_after_headers(key: str, *, fallback: int | None = None) -> dict[str, str]:
    """Build a `Retry-After` header from the remaining TTL of the throttle key.

    A 429 without `Retry-After` tells a client to back off and not for how long, so
    firmware either retries immediately — burning the budget again — or picks an
    arbitrary delay. Every rate-limited response carries it.

    Prefers the key's live TTL over the nominal interval: a device throttled two
    seconds into a five-minute window should be told 298, not 300. `fallback` covers
    Redis being unavailable or the key having no expiry; with neither, the header is
    omitted rather than guessed, since a wrong value is worse than none.
    """
    remaining = key_ttl(key)
    if remaining is None:
        remaining = fallback
    if remaining is None:
        return {}
    # A TTL of 0 means the key expires within this second, so 1 is the honest wait —
    # not the nominal interval, and not 0, which advertises "retry now" as the answer
    # to a request that was just refused.
    return {"Retry-After": str(max(1, int(remaining)))}


def enforce_request_rate_ceiling(
    key: str, *, limit: int = 60, window_secs: int = 60,
    detail: str = "Too many requests — device quota exceeded",
) -> None:
    """Raise HTTP 429 if more than `limit` requests have been seen under `key`
    within `window_secs`. Generic per-device hard rate ceiling — the caller is
    responsible for deriving a collision-safe, non-reversible `key` (e.g. a hash
    of a device token, never the plaintext token or a short prefix of it).

    Protects against a malfunctioning or compromised device that ignores 429s
    from an interval throttle and keeps hammering an endpoint.
    """
    count = increment_key(key, ttl=window_secs)
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers=retry_after_headers(key, fallback=window_secs),
        )


def _get_client_ip(request: Request) -> str:
    """Compatibility wrapper around the shared client-IP policy."""
    return get_client_ip(request)


def _bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
) -> Optional[str]:
    """Extract the raw bearer token, or None when the header is absent."""
    return credentials.credentials if credentials else None


def api_key_auth(request: Request, api_key: Optional[str] = Depends(_bearer_token)) -> AuthContext:
    """Validate API key and return an AuthContext for the request.

    Raises:
        HTTPException: If the API key is missing or invalid, or the client is blocked.
    """
    settings = get_settings()
    client_ip = _get_client_ip(request)
    block_key = f"auth:blocked:{client_ip}"
    fail_key = f"auth:failures:{client_ip}"

    # A blocked client is refused before its key is looked at, so a block cannot be
    # probed with further guesses.
    if exist_key(block_key):
        logger.warning("Blocked IP attempted access: %s", truncate_ip(client_ip))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed authentication attempts",
            headers=retry_after_headers(
                block_key, fallback=settings.auth_block_seconds
            ),
        )

    logger.info("Validating access token")
    if hmac.compare_digest(api_key or "", settings.api_key.get_secret_value()):
        delete_key(fail_key)
        return AuthContext()

    path = request.url.path
    token_present = "present" if api_key else "missing"

    failures = increment_key(fail_key, settings.auth_block_seconds)

    if failures >= settings.auth_max_failures:
        increment_key(block_key, settings.auth_block_seconds)
        system_log_security(
            f"IP {truncate_ip(client_ip)} blocked after {failures} failed auth attempts",
            level="WARNING",
        )
        logger.warning("IP blocked due to repeated auth failures: %s", truncate_ip(client_ip))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed authentication attempts",
            headers=retry_after_headers(
                block_key, fallback=settings.auth_block_seconds
            ),
        )

    system_log_security(
        f"Invalid token in request from {truncate_ip(client_ip)} on {path}"
        f" (token: {token_present})"
        f" — failure {failures}/{settings.auth_max_failures}",
        level="WARNING",
    )
    logger.error(
        "Api-key is not valid: client=%s path=%s token=%s failures=%d",
        truncate_ip(client_ip), path, token_present, failures,
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Access forbidden",
    )


def record_auth_failure(client_ip: str) -> None:
    """Increment the per-IP failure counter; block the IP if the threshold is crossed.

    Shared by the HTTP and WebSocket auth paths so both count toward the same limit.
    """
    settings = get_settings()
    block_key = f"auth:blocked:{client_ip}"
    fail_key = f"auth:failures:{client_ip}"
    failures = increment_key(fail_key, settings.auth_block_seconds)
    if failures >= settings.auth_max_failures:
        increment_key(block_key, settings.auth_block_seconds)
        delete_key(fail_key)
        system_log_security(
            f"IP {truncate_ip(client_ip)} blocked after {failures} failed auth attempts",
            level="WARNING",
        )
        logger.warning("IP blocked due to repeated auth failures: %s", truncate_ip(client_ip))


def ingest_auth(
    request: Request, throttle: ThrottleLimits = Depends(oss_throttle_provider)
) -> AuthContext:
    """Return an AuthContext for device ingest endpoints (IP rate-limited, no API key required)."""
    settings = get_settings()
    client_ip = _get_client_ip(request)
    block_key = f"ingest:blocked:{client_ip}"
    if exist_key(block_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
        )
    rate_key = f"ingest:rate:{client_ip}"
    count = increment_key(rate_key, 60)
    if count >= throttle.pre_auth_per_minute:
        increment_key(block_key, settings.auth_block_seconds)
        system_log_security(
            f"Ingest IP {truncate_ip(client_ip)} rate-limited after {count} requests/min",
            level="WARNING",
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
        )
    return AuthContext(ingest_interval_seconds=throttle.per_device_min_interval_seconds)


def get_retention_cutoff(auth: AuthContext = Depends(api_key_auth)) -> Optional[datetime]:
    """Return the oldest allowed datetime derived from the auth context.

    Returns None when retention_days is -1 (no cutoff applied).
    """
    if auth.retention_days == -1:
        return None
    return datetime.now(timezone.utc) - timedelta(days=auth.retention_days)
