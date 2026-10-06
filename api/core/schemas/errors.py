# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""The error envelope, as a schema the OpenAPI document can describe.

Every 4xx and 5xx this app returns is `{error, message, requestId}` — the shape
the exception handlers in `main_oss.py` emit. Until this existed the document
declared those responses with empty content, so a generated client had nothing
to deserialise an error into and `requestId` was invisible to anyone reading
`/docs`, despite being the one field worth quoting in a bug report.

`ERROR_RESPONSES` is the ready-made `responses=` mapping for the common cases;
compose it with `error_responses(404, 409)` when an operation needs a subset.
"""
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Body returned with every 4xx and 5xx."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "not_found",
                "message": "Batch not found",
                "requestId": "94286f66-c124-44fc-9c4a-83648967f198",
            }
        }
    )

    error: str = Field(description="Stable machine-readable code, e.g. `not_found`.")
    message: str = Field(description="Human-readable summary. Not intended for parsing.")
    requestId: str = Field(  # noqa: N815  # wire contract is camelCase
        description="Correlates the response with the server log line for the same request.",
    )


_DESCRIPTIONS = {
    400: "Malformed request",
    401: "Missing or invalid credentials",
    403: "Not permitted",
    404: "Not found",
    409: "Conflict with current state",
    410: "No longer available",
    422: "Request failed validation",
    429: "Rate limited — see the Retry-After header",
    500: "Unexpected server error",
}


def error_responses(*codes: int) -> Dict[int, Dict[str, Any]]:
    """Return an OpenAPI ``responses`` mapping for the given status codes."""
    return {
        code: {"model": ErrorResponse, "description": _DESCRIPTIONS.get(code, "Error")}
        for code in codes
    }


#: The set every authenticated operation can return.
ERROR_RESPONSES = error_responses(401, 403, 422, 500)

#: Add to any operation addressing a single resource by id.
NOT_FOUND_RESPONSES = error_responses(404)
