# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""End-to-end test, against a real SQLite session, for the per-target
auto-disable safeguard (spec-jobs.md's "Per-target safeguard: auto-disable
after 3 consecutive failures").

`tests/test_forward_common.py`'s `TestApplyDeliveryOutcome` already proves the
counter/threshold logic in isolation against a mocked target object -- fast
and thorough, but it never exercises a real SQLAlchemy session, so it would
not have caught the kind of type-coercion or session-scoping bug
`tests/test_forward_uuid_regression.py` found elsewhere in this same feature
(every existing drain-job test mocks `create_session`/`db().get`). This test
drives three full `task_drain_gravity_forward_queue()` runs against a real
SQLite-backed `Integration` row -- only the Redis queue primitives and the
outbound HTTP dispatch are mocked -- and re-reads the row from a fresh
session after each run to prove the disable/reset actually persisted, not
just mutated an in-memory object."""
# pylint: disable=missing-function-docstring
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from core.db import create_session
from core.models.registry import resolve_model
from oss.jobs.gravity_forward import task_drain_gravity_forward_queue
from tests.conftest import truncate_database

Batch = resolve_model("Batch")
Device = resolve_model("Device")
GravityReading = resolve_model("GravityReading")
Integration = resolve_model("Integration")


def _make_item(**fields) -> bytes:
    return json.dumps({
        "enqueued_at": datetime.now(UTC).isoformat(),
        "attempts": 0,
        **fields,
    }).encode()


async def _drain_once(device_id_str: str, tenant_id_str: str, *, outcome: str) -> None:
    raw = _make_item(device_id=device_id_str, tenant_id=tenant_id_str)
    with patch("oss.jobs.gravity_forward.queue_len", return_value=1), \
         patch("oss.jobs.gravity_forward.queue_pop_to_processing", return_value=raw), \
         patch("oss.jobs.gravity_forward.deliver_custom",
               new_callable=AsyncMock, return_value=outcome), \
         patch("oss.jobs.gravity_forward.system_log_scheduler"), \
         patch("oss.jobs._forward_common.system_log_scheduler") as mock_safeguard_log:
        await task_drain_gravity_forward_queue()
    _drain_once.last_safeguard_log = mock_safeguard_log


@pytest.mark.asyncio
async def test_third_consecutive_failure_disables_target_against_real_session():
    """Three separate drain runs, each failing the same target, must disable it and
    reset its counter -- verified by re-reading the row from a fresh session each
    time, not by inspecting the in-memory object the drain loop mutated."""
    truncate_database()
    db = create_session()
    try:
        device = Device(name="Safeguard Device", device_type="gravitymon")
        db().add(device)
        db().commit()
        batch = Batch(name="Safeguard Batch", accept_ingest=True)
        db().add(batch)
        db().commit()
        reading = GravityReading(
            batch_id=batch.id, device_id=device.id, gravity=1.045, excluded=False,
        )
        db().add(reading)
        integration = Integration(
            name="Safeguard Target", measurement="gravity", type="custom_forward",
            enabled=True,
            config={"url": "http://8.8.8.8/hook", "method": "POST",
                    "template": "g=${gravity}", "headers": {}},
        )
        db().add(integration)
        db().commit()
        device_id_str, tenant_id_str = str(device.id), str(device.tenant_id)
        integration_id = integration.id
    finally:
        db.remove()

    def _reread():
        fresh = create_session()
        try:
            return fresh().get(Integration, integration_id)
        finally:
            fresh.remove()

    # Two failures: counter increments, target stays enabled, no auto-disable log.
    for expected_count in (1, 2):
        await _drain_once(device_id_str, tenant_id_str, outcome="failed")
        row = _reread()
        assert row.consecutive_failures == expected_count
        assert row.enabled is True
        _drain_once.last_safeguard_log.assert_not_called()

    # Third failure: disabled, counter reset to 0, WARNING logged once.
    await _drain_once(device_id_str, tenant_id_str, outcome="failed")
    row = _reread()
    assert row.consecutive_failures == 0
    assert row.enabled is False
    _drain_once.last_safeguard_log.assert_called_once()
    logged_message = _drain_once.last_safeguard_log.call_args[0][0]
    assert "Safeguard Target" in logged_message
    assert "auto-disabled" in logged_message


@pytest.mark.asyncio
async def test_delivered_outcome_resets_a_nonzero_counter_against_real_session():
    """A successful delivery resets consecutive_failures to 0, even after prior
    failures -- verified against a real session, same as the disable path above."""
    truncate_database()
    db = create_session()
    try:
        device = Device(name="Safeguard Device 2", device_type="gravitymon")
        db().add(device)
        db().commit()
        batch = Batch(name="Safeguard Batch 2", accept_ingest=True)
        db().add(batch)
        db().commit()
        reading = GravityReading(
            batch_id=batch.id, device_id=device.id, gravity=1.045, excluded=False,
        )
        db().add(reading)
        integration = Integration(
            name="Safeguard Target 2", measurement="gravity", type="custom_forward",
            enabled=True, consecutive_failures=2,
            config={"url": "http://8.8.8.8/hook", "method": "POST",
                    "template": "g=${gravity}", "headers": {}},
        )
        db().add(integration)
        db().commit()
        device_id_str, tenant_id_str = str(device.id), str(device.tenant_id)
        integration_id = integration.id
    finally:
        db.remove()

    await _drain_once(device_id_str, tenant_id_str, outcome="delivered")

    fresh = create_session()
    try:
        row = fresh().get(Integration, integration_id)
        assert row.consecutive_failures == 0
        assert row.enabled is True
    finally:
        fresh.remove()
