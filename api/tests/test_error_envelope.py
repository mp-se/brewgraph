# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""The normative `{error, message, requestId}` envelope applies to every error response, not
just validation errors. Covers the status->code default map, `ApiError`'s specific-code
override, that a 500 never leaks the real exception, and that `Retry-After` survives the
generic handler.
"""
from fastapi import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from core.errors import ApiError, ERROR_CODES, register_error
from core.middleware.auth import AuthContext, check_quota
from main_oss import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_handler,
)


def _request(request_id=None):
    """Build a minimal `Request` with `state.request_id` set the way `RequestIdMiddleware` does."""
    req = Request({"type": "http", "headers": [], "method": "GET", "path": "/"})
    req.state.request_id = request_id
    return req


async def test_bare_404_gets_default_not_found_code():
    """A plain `HTTPException(404, ...)` — the ~150 untouched raise sites — still emits the
    envelope, with `error` taken from `ERROR_CODES` rather than needing a code at the raise
    site."""
    exc = StarletteHTTPException(status_code=404, detail="Batch not found")
    resp = await http_exception_handler(_request("req-1"), exc)
    assert resp.status_code == 404
    body = resp.body.decode()
    assert '"error":"not_found"' in body or '"error": "not_found"' in body
    assert "Batch not found" in body
    assert "req-1" in body


async def test_api_error_overrides_the_default_code():
    """`ApiError`'s own `error` wins over the status-keyed default."""
    exc = ApiError(
        status_code=403, error="quota_exceeded", detail="batches quota of 1 reached"
    )
    resp = await http_exception_handler(_request("req-2"), exc)
    assert resp.status_code == 403
    body = resp.body.decode()
    assert "quota_exceeded" in body
    assert "batches quota of 1 reached" in body


async def test_retry_after_header_survives():
    """A 429 with `Retry-After` keeps it through the generic handler — a device that gets a 429
    with no `Retry-After` has no way to know how long to back off."""
    exc = HTTPException(
        status_code=429, detail="Too many requests", headers={"Retry-After": "42"}
    )
    resp = await http_exception_handler(_request(), exc)
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "42"


async def test_non_string_detail_falls_back_to_a_generic_message():
    """`detail` is not always a string (FastAPI's own validation-adjacent raises can pass a
    dict); the handler must not choke on it or leak the raw structure verbatim as `message`."""
    exc = StarletteHTTPException(status_code=400, detail={"reason": "bad"})
    resp = await http_exception_handler(_request(), exc)
    body = resp.body.decode()
    assert "reason" not in body


async def test_generic_500_never_leaks_the_real_exception():
    """The one case where `message` is NOT the raise site's text verbatim — an unhandled
    exception's own message must never reach the client."""
    exc = RuntimeError("leaked internal state: /etc/passwd, secret=xyz")
    resp = await unhandled_exception_handler(_request("req-3"), exc)
    assert resp.status_code == 500
    body = resp.body.decode()
    assert "leaked internal state" not in body
    assert "secret" not in body
    assert '"error":"internal_error"' in body or '"error": "internal_error"' in body
    assert (
        '"message":"Internal server error"' in body
        or '"message": "Internal server error"' in body
    )
    assert "req-3" in body


async def test_validation_error_uses_the_envelope():
    """The 422 handler predates this plan; it must match the same shape, not a bespoke one."""
    from fastapi.exceptions import (  # pylint: disable=import-outside-toplevel
        RequestValidationError,
    )

    exc = RequestValidationError(
        [{"loc": ("body", "name"), "msg": "field required", "type": "missing"}]
    )
    resp = await validation_handler(_request("req-4"), exc)
    assert resp.status_code == 422
    body = resp.body.decode()
    assert '"error":"validation_error"' in body or '"error": "validation_error"' in body
    assert "req-4" in body
    # The raw per-field error list is logged, not returned.
    assert "field required" not in body


def test_check_quota_raises_api_error_with_the_specific_code():
    """`check_quota` names `quota_exceeded` rather than falling back to plain `forbidden`,
    so a client can branch on the code without string-matching the message."""
    auth = AuthContext(quota_limits={"batches": 1})
    try:
        check_quota(1, auth, "batches")
    except ApiError as exc:
        assert exc.status_code == 403
        assert exc.error == "quota_exceeded"
        assert exc.detail == "batches quota of 1 reached"
    else:
        raise AssertionError("check_quota did not raise")


def test_register_error_accepts_a_new_code():
    """A code with no prior meaning registers cleanly."""
    register_error("_test_only_code", 418)


def test_register_error_is_idempotent_for_the_same_status():
    """Re-registering the same code under the same status is a no-op — safe if the
    registering module is imported more than once."""
    register_error("_test_only_idempotent", 418)
    register_error("_test_only_idempotent", 418)


def test_register_error_rejects_colliding_with_a_base_code():
    """Registering over a base `ERROR_CODES` value must not silently clobber it."""
    try:
        register_error("not_found", 418)
    except ValueError:
        pass
    else:
        raise AssertionError("register_error silently clobbered a base code")


def test_register_error_rejects_redefining_a_known_code_under_a_new_status():
    """A code meaning two different things depending on import order is exactly the failure
    mode `register_error` exists to prevent."""
    register_error("_test_only_stable", 418)
    try:
        register_error("_test_only_stable", 419)
    except ValueError:
        pass
    else:
        raise AssertionError("register_error silently changed a code's status")


def test_status_to_code_map_matches_the_spec_table():
    """Exact status->code table, not a subset."""
    assert ERROR_CODES == {
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        500: "internal_error",
    }
