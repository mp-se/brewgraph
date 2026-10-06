# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Integration Pydantic schemas."""
import uuid
from datetime import datetime
from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.enums import IntegrationType, MeasurementType
from oss.schemas._camel import to_camel

# core.utils.assert_outbound_url_safe (loopback/link-local rejection) runs a live DNS
# lookup, which does not belong in a Pydantic validator -- schemas do structural
# validation, services do the IO-bearing kind. IntegrationService.create()/update()
# call it before persisting; see spec-design-patterns.md's layer contract.

# Which measurements each built-in type has a payload for. `custom_forward` is valid for all.
_BUILT_IN_MEASUREMENTS = {
    IntegrationType.ISPINDEL_FORWARD.value: (MeasurementType.GRAVITY.value,),
    IntegrationType.BREWFATHER_FORWARD.value: (
        MeasurementType.GRAVITY.value, MeasurementType.PRESSURE.value,
        MeasurementType.TEMP.value,
    ),
}


def unsupported_measurement(integration_type: str, measurement: str) -> Optional[str]:
    """The 422 message when a built-in type has no payload for the measurement, else None."""
    allowed = _BUILT_IN_MEASUREMENTS.get(integration_type)
    if allowed is None or measurement in allowed:
        return None
    listed = allowed[0] if len(allowed) == 1 else f"{', '.join(allowed[:-1])} or {allowed[-1]}"
    return f"type={integration_type} requires measurement={listed}"


class IntegrationConfig(BaseModel):
    """`Integration.config` — shape depends on `type`, but every type shares this envelope.

    `template` is required for `custom_forward` and rejected for the two built-in
    types, which define their own payload shape server-side (see
    `oss/jobs/gravity_forward.py`).
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    method: Literal["POST", "GET"] = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    template: Optional[str] = None


class IntegrationConfigResponse(IntegrationConfig):
    """Read-only projection of `IntegrationConfig` with header values redacted.

    Custom-forward `headers` commonly carry a bearer token or API key for the
    external target. `IntegrationConfig` itself must keep header values as
    plain strings for create/update — the API needs to send them verbatim to
    the forward target — but this subclass is used only on the read path,
    where the same field must never echo a configured secret back to the
    caller. Key names are preserved (so a caller can see which headers are
    set); each value is replaced with a fixed placeholder string.
    """

    @model_validator(mode="after")
    def _redact_header_values(self) -> "IntegrationConfigResponse":
        if self.headers:
            self.headers = dict.fromkeys(self.headers, "[redacted]")
        return self


class IntegrationBase(BaseModel):
    """Shared integration fields."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    name: str = Field(max_length=60)
    measurement: MeasurementType
    type: IntegrationType
    enabled: bool = True
    config: IntegrationConfig

    @model_validator(mode="after")
    def _validate_template_by_type(self) -> "IntegrationBase":
        """`template` is the whole point of `custom_forward` and meaningless for the
        two built-in types, which define their own payload shape server-side."""
        is_custom = self.type == IntegrationType.CUSTOM_FORWARD
        has_template = bool(self.config.template)
        if is_custom and not has_template:
            raise ValueError("config.template is required for type=custom_forward")
        if not is_custom and has_template:
            raise ValueError(f"config.template is not accepted for type={self.type.value}")
        return self

    @model_validator(mode="after")
    def _validate_type_fits_measurement(self) -> "IntegrationBase":
        """Reject a built-in type on a measurement it has no payload for."""
        problem = unsupported_measurement(self.type.value, self.measurement.value)
        if problem:
            raise ValueError(problem)
        return self


class IntegrationCreate(IntegrationBase):
    """Fields required to create an integration target."""


class IntegrationUpdate(BaseModel):
    """Partial-update payload for an integration target. `measurement` and `type` are
    both immutable — changing what/how a target forwards is a new target, not an edit
    of an existing one. Neither field exists on this schema at all (not merely ignored
    if present); `extra="forbid"` means a request body naming either is rejected `422`,
    not silently dropped."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    name: Optional[str] = Field(default=None, max_length=60)
    enabled: Optional[bool] = None
    config: Optional[IntegrationConfig] = None


class IntegrationResponse(IntegrationBase):
    """Full integration response including server-assigned fields."""

    config: IntegrationConfigResponse
    id: uuid.UUID
    consecutive_failures: int = 0
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_failure_code: Optional[str] = None
    disabled_reason: Optional[str] = None
    version: int = 1
    created_at: datetime
    updated_at: datetime


from oss.schemas.registry import \
    register  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

register("IntegrationCreate", IntegrationCreate)
register("IntegrationUpdate", IntegrationUpdate)
register("IntegrationResponse", IntegrationResponse)
