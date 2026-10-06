# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""The envelope every JSON column carries.

A JSON column with no agreed shape is a schema that exists but is written down
nowhere. The payload inside stays opaque — that is the point of using JSON —
but the wrapper around it is a contract:

    {"v": 1, "kind": "device-config", "capturedAt": "...", "source": "...", "data": {...}}

Rules that keep it usable as it changes:

* **Readers ignore unknown keys**, at every level. A consumer that rejects an
  unrecognised field turns every future addition into a breaking change.
* **Writers never remove or repurpose a key within a version.** Adding is free;
  changing what something means requires bumping ``v``.
* **``data`` is an object, never a bare scalar or list**, so keys can be added
  later without a version bump.
* **``data`` is documented as observed, not enforced.** A device config is
  whatever the firmware returned; a prediction payload is whatever that
  prediction type emits. Neither is validated per type.
* **Anything needing filtering, indexing or a constraint leaves ``data`` and
  becomes a column.** Without that rule the payload becomes a junk drawer.

``capturedAt`` is when the payload was produced, which is deliberately not the
row's ``created_at``: a config fetched on Monday can be stored on Tuesday.
"""
import json
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from core.config import get_settings
from core.schemas.camel import to_camel

#: Current envelope version. Bumped only for a breaking change to the envelope
#: itself — never for anything inside ``data``.
ENVELOPE_VERSION = 1


def max_envelope_bytes() -> int:
    """Configured cap on a stored envelope (`MAX_ENVELOPE_BYTES`, default 16 KiB).

    Read through the settings object rather than frozen at import, so an operator can
    raise it for a device whose firmware returns an unusually large config without
    editing code.
    """
    return get_settings().max_envelope_bytes


class JsonEnvelope(BaseModel):
    """Wrapper stored in every JSON column."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    v: int = ENVELOPE_VERSION
    kind: str
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


def build_envelope(
    kind: str,
    data: Optional[Dict[str, Any]] = None,
    source: Optional[str] = None,
    captured_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Return a JSON-serialisable envelope ready to store in a JSON column."""
    envelope = JsonEnvelope(
        kind=kind,
        data=data or {},
        source=source,
        captured_at=captured_at or datetime.now(UTC),
    )
    return envelope.model_dump(mode="json", by_alias=True)


def envelope_data(value: Any) -> Dict[str, Any]:
    """Return the payload from a stored envelope, tolerating what came before it.

    Accepts a bare dict that is not an envelope and returns it unchanged, so a
    reader does not have to know whether a given row was written before the
    envelope existed.
    """
    if not isinstance(value, dict):
        return {}
    if "data" in value and "kind" in value:
        payload = value.get("data")
        return payload if isinstance(payload, dict) else {}
    return value


def envelope_too_large(value: Any) -> bool:
    """True when a serialised envelope exceeds the configured cap."""
    return len(json.dumps(value, default=str).encode()) > max_envelope_bytes()


def reject_if_too_large(value: Any, field: str) -> Any:
    """Return `value`, or raise a 422 `ApiError` when it exceeds the configured cap.

    Truncating would store a payload that looks valid and is not, so this refuses the
    write instead. Callers pass the field name so the message names what to shrink.
    """
    if envelope_too_large(value):
        from core.errors import ApiError  # pylint: disable=import-outside-toplevel

        raise ApiError(
            status_code=422,
            error="payload_too_large",
            detail=(
                f"{field} exceeds the maximum stored size of {max_envelope_bytes()} bytes"
            ),
        )
    return value
