# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Integration service."""
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, Optional

from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from core.cache import increment_key
from core.enums import IntegrationType
from core.models.registry import resolve_model
from core.utils import assert_outbound_url_safe
from oss.schemas.integration import (IntegrationCreate, IntegrationUpdate,
                                     unsupported_measurement)
from oss.services.base import BaseService
from oss.jobs import gravity_forward, pour_forward, pressure_forward, temp_forward
from oss.jobs._forward_common import deliver_custom, http_post

Integration = resolve_model("Integration")


def _assert_config_valid(integration_type: str, measurement: str, config: dict) -> None:
    """Reject a loopback/link-local destination URL, translating into a 422.

    Kept as a module function rather than inline in create()/update(): both call
    sites need the identical check, and it must run after IntegrationUpdate's
    partial config is merged onto the existing row's type, not before.
    """
    try:
        assert_outbound_url_safe(config["url"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    is_custom = integration_type == IntegrationType.CUSTOM_FORWARD.value
    has_template = bool(config.get("template"))
    if is_custom and not has_template:
        raise HTTPException(
            status_code=422, detail="config.template is required for type=custom_forward"
        )
    if not is_custom and has_template:
        raise HTTPException(
            status_code=422,
            detail=f"config.template is not accepted for type={integration_type}",
        )
    problem = unsupported_measurement(integration_type, measurement)
    if problem:
        raise HTTPException(status_code=422, detail=problem)


class IntegrationService(BaseService[Integration, IntegrationCreate, IntegrationUpdate]):
    """Service for managing account-level forwarding-integration targets."""

    def __init__(self, db_session: Session):
        """Initialise with a SQLAlchemy session."""
        super().__init__(Integration, db_session)

    def create(self, obj: IntegrationCreate) -> Integration:  # pylint: disable=arguments-renamed
        """Create a forwarding target after validating its destination URL.

        IntegrationBase's own model_validator already enforced the
        type/template relationship structurally; this is the IO-bearing half
        (a live DNS lookup) that a Pydantic validator should not do — see
        oss/schemas/integration.py.
        """
        config = obj.config.model_dump()
        _assert_config_valid(obj.type.value, obj.measurement.value, config)
        return super().create(obj)

    def update(self, item_id: Any, obj: IntegrationUpdate) -> Optional[Integration]:
        """Partial update. `type` is immutable, so re-validation always has a real type
        to check the merged config against, even when only `config` is being changed."""
        existing = self.get_active(item_id)
        if existing is None:
            return None
        if obj.config is not None:
            _assert_config_valid(existing.type, existing.measurement, obj.config.model_dump())
        if obj.enabled is True:
            existing.consecutive_failures = 0
            existing.disabled_reason = None
        elif obj.enabled is False:
            existing.disabled_reason = "manual"
        return super().update(item_id, obj)

    async def test(self, item_id: Any) -> Optional[dict]:
        """Send the fixed dummy reading (the payload preview's) without changing strikes/state."""
        integration = self.get(item_id)
        if integration is None:
            return None
        count = increment_key(f"integration_test:{integration.id}", ttl=3600)
        if count > TEST_SENDS_PER_HOUR:
            raise HTTPException(status_code=429, detail="Test-send rate limit exceeded")
        try:
            assert_outbound_url_safe(integration.config["url"])
            if integration.type == IntegrationType.CUSTOM_FORWARD.value:
                values = _dummy_template_values(integration.measurement, integration.name)
                outcome = await deliver_custom(
                    integration.config, values, uuid.UUID(int=0), "integration test"
                )
            else:
                payload = _dummy_built_in_payload(
                    integration.type, integration.measurement, integration.name
                )
                ok = await http_post(
                    integration.config["url"], payload, uuid.UUID(int=0), "integration test"
                )
                outcome = "delivered" if ok else "failed"
        except ValueError:
            outcome = "blocked"
        now = datetime.now(UTC)
        if outcome == "delivered":
            integration.last_success_at = now
            integration.last_failure_code = None
        else:
            integration.last_failure_at = now
            integration.last_failure_code = (
                "outbound_blocked" if outcome == "blocked" else "delivery_failed"
            )
        self.commit()
        return {"outcome": outcome}

    def delete(self, item_id: Any) -> bool:
        """Remove one target. Real delete, not soft — an integration is
        configuration, not brewing history; there is nothing to recover.
        Returns False if not found."""
        integration = self.get(item_id)
        if integration is None:
            return False
        self.db_session.delete(integration)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return True


# Test sends allowed per target per hour; enough to iterate on a template, small enough that the
# endpoint cannot be used to hammer a URL.
TEST_SENDS_PER_HOUR = 20

# The one fixed dummy reading per measurement that "Send test payload" sends. It MUST stay
# identical to DUMMY_READINGS in web/src/core/integrations/integrationPreview.ts (the payload
# preview), so test delivery sends exactly what the preview shows. The values are turned into
# a request by the same builders a real forward uses, fed with these stand-ins.
_DUMMY_TIMESTAMP = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
_DUMMY_BATCH_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_DUMMY_DEVICE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_DUMMY_DEVICE_NAME = "Fermenter 1"


def _dummy_device(name: str) -> SimpleNamespace:
    """The stand-in device. It carries the target's own name, so every target sends a name of
    its own and a receiver that limits per name (Brewfather) does not throttle one test with
    another's. A blank name falls back to `Fermenter 1`."""
    return SimpleNamespace(
        id=_DUMMY_DEVICE_ID, name=(name or "").strip() or _DUMMY_DEVICE_NAME, chip_id="a1b2c3",
    )


_DUMMY_TAP = SimpleNamespace(id=uuid.UUID("00000000-0000-0000-0000-000000000003"), name="Tap 1")
_DUMMY_READINGS = {
    "gravity": SimpleNamespace(
        gravity=1.042, temperature=20.5, angle=45.2, velocity=0.15, battery=3.98, rssi=-62,
        batch_id=_DUMMY_BATCH_ID, created_at=_DUMMY_TIMESTAMP,
    ),
    "pressure": SimpleNamespace(
        pressure=12.5, temperature=4.0, battery=3.98, rssi=-62,
        batch_id=_DUMMY_BATCH_ID, created_at=_DUMMY_TIMESTAMP,
    ),
    "temp": SimpleNamespace(
        temperature=18.5, temp_type="beer", battery=3.98, rssi=-62,
        batch_id=_DUMMY_BATCH_ID, created_at=_DUMMY_TIMESTAMP,
    ),
    "pour": SimpleNamespace(
        pour_amount=0.33, volume_remaining=12.4,
        vessel_id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
        batch_id=_DUMMY_BATCH_ID, created_at=_DUMMY_TIMESTAMP,
    ),
}


def _dummy_template_values(measurement: str, name: str) -> dict:
    """The ${key} values a real forward of this measurement would build from the dummy reading."""
    # pylint: disable=protected-access
    reading = _DUMMY_READINGS[measurement]
    if measurement == "pour":
        return pour_forward._template_values(_DUMMY_TAP, reading)
    builder = {
        "gravity": gravity_forward, "pressure": pressure_forward, "temp": temp_forward,
    }[measurement]
    return builder._template_values(_dummy_device(name), reading)


def _dummy_built_in_payload(integration_type: str, measurement: str, name: str) -> dict:
    """The ispindel_forward/brewfather_forward body, from the real builders."""
    # pylint: disable=protected-access
    reading = _DUMMY_READINGS[measurement]
    if integration_type == IntegrationType.ISPINDEL_FORWARD.value:
        return gravity_forward._ispindel_payload(_dummy_device(name), reading)
    builder = {
        "gravity": gravity_forward, "pressure": pressure_forward, "temp": temp_forward,
    }[measurement]
    return builder._brewfather_payload(_dummy_device(name), reading)
