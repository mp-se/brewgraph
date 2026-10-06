# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Machine-readable error codes for the normative error envelope.

Every error response carries `{error, message, requestId}`. A bare `HTTPException(status,
detail)` gets its `error` from `ERROR_CODES` by status, so the ~150 existing raise sites emit
the envelope without being touched. A raise site names a specific code only where a client needs
to distinguish two cases sharing one status (`quota_exceeded` vs `forbidden`, both 403) by
raising `ApiError` instead of `HTTPException`.
"""
from fastapi import HTTPException

# Status -> default machine-readable code. Do not add deployment-specific codes here — use
# `register_error` for those.
ERROR_CODES: dict[int, str] = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
}

# All known codes, base and registered, mapped to the status they're raised with. Seeded from
# ERROR_CODES so `register_error` can reject a new code that collides with a base one.
_KNOWN_CODES: dict[str, int] = {code: status for status, code in ERROR_CODES.items()}


class ApiError(HTTPException):
    """`HTTPException` carrying a machine-readable `error` code alongside `detail`.

    Raise this instead of `HTTPException` where two cases share one HTTP status and a client
    needs to tell them apart — e.g. `quota_exceeded` vs plain `forbidden`, both 403. Everything
    else keeps raising `HTTPException` and gets its code from `ERROR_CODES` by status; that is
    the whole point of the status-keyed default, see the module docstring.
    """

    def __init__(
        self,
        status_code: int,
        error: str,
        detail: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail=detail if detail is not None else error,
            headers=headers,
        )
        self.error = error


def register_error(code: str, status: int) -> None:
    """Register an additional error code for use with `ApiError`, extending `ERROR_CODES`.

    This is the extension point for a deployment that needs its own codes (a distinct 403 code
    for an access rule this module doesn't know about, for example) without this module having
    to know about every caller in advance. Registration is additive only:

    - Re-registering an already-known code under the *same* status is a no-op (idempotent —
      safe if the registering module is imported more than once).
    - Registering a code that collides with a *base* `ERROR_CODES` value, or re-registering a
      known code under a *different* status, raises `ValueError` rather than silently
      overwriting it — a code meaning two different things depending on import order is exactly
      the failure mode this function exists to prevent.
    """
    existing = _KNOWN_CODES.get(code)
    if existing is not None and existing != status:
        raise ValueError(
            f"error code {code!r} is already registered for status {existing}; "
            f"cannot re-register it for status {status}"
        )
    _KNOWN_CODES[code] = status
