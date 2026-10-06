# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Regression test for a real bug found via live end-to-end verification while
building the pressure/pour/temp forwarding jobs (2026-09-07): a queue item's
device_id/tap_id/tenant_id round-trip through JSON as plain strings, and
SQLAlchemy's `Uuid(as_uuid=True)` column type raises
`AttributeError: 'str' object has no attribute 'hex'` on SQLite (and any
other dialect with no native UUID storage) when a plain string is bound for
that column, rather than a real `uuid.UUID`.

Every existing test for the four drain jobs mocks `create_session`/`db().get`
directly, so none of them exercised the real SQLAlchemy type-coercion path —
this bug was invisible to the full mocked test suite and was only caught by
running a live `uvicorn main_oss:app` + real Redis + real SQLite and actually
draining a queued item. This test proves the fix (`oss.jobs._forward_common.
as_uuid`) by exercising the real DB session, with only the Redis queue
primitives and the outbound HTTP dispatch mocked — no live Redis or network
call required to run it."""
# pylint: disable=missing-function-docstring
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from core.db import create_session
from core.models.registry import resolve_model
from oss.jobs.gravity_forward import task_drain_gravity_forward_queue
from oss.jobs.pour_forward import task_drain_pour_forward_queue
from oss.jobs.pressure_forward import task_drain_pressure_forward_queue
from tests.conftest import truncate_database

Batch = resolve_model("Batch")
Device = resolve_model("Device")
GravityReading = resolve_model("GravityReading")
PressureReading = resolve_model("PressureReading")
Tap = resolve_model("Tap")
StorageVessel = resolve_model("StorageVessel")
PourEvent = resolve_model("PourEvent")
Integration = resolve_model("Integration")


def _make_item(**fields) -> bytes:
    return json.dumps({
        "enqueued_at": datetime.now(UTC).isoformat(),
        "attempts": 0,
        **fields,
    }).encode()


@pytest.mark.asyncio
async def test_gravity_drain_resolves_plain_string_ids_against_real_session():
    """The original file's shape: a plain-string device_id/tenant_id from the
    queue must resolve correctly against a real SQLAlchemy session."""
    truncate_database()
    db = create_session()
    try:
        device = Device(name="Regression Device", device_type="gravitymon")
        db().add(device)
        db().commit()
        batch = Batch(name="Regression Batch", accept_ingest=True)
        db().add(batch)
        db().commit()
        reading = GravityReading(
            batch_id=batch.id, device_id=device.id, gravity=1.045, excluded=False,
        )
        db().add(reading)
        integration = Integration(
            name="Regression Target", measurement="gravity", type="custom_forward",
            enabled=True,
            config={"url": "http://8.8.8.8/hook", "method": "POST",
                    "template": "g=${gravity}", "headers": {}},
        )
        db().add(integration)
        db().commit()
        device_id_str, tenant_id_str = str(device.id), str(device.tenant_id)
    finally:
        db.remove()

    raw = _make_item(device_id=device_id_str, tenant_id=tenant_id_str)
    with patch("oss.jobs.gravity_forward.queue_len", return_value=1), \
         patch("oss.jobs.gravity_forward.queue_pop_to_processing", return_value=raw), \
         patch("oss.jobs.gravity_forward.deliver_custom",
               new_callable=AsyncMock, return_value="delivered") as mock_deliver, \
         patch("oss.jobs.gravity_forward.system_log_scheduler"):
        await task_drain_gravity_forward_queue()

    mock_deliver.assert_awaited_once()


@pytest.mark.asyncio
async def test_pressure_drain_resolves_plain_string_ids_against_real_session():
    """Same regression, for the pressure_forward.py sibling."""
    truncate_database()
    db = create_session()
    try:
        device = Device(name="Regression PM", device_type="pressuremon")
        db().add(device)
        db().commit()
        # PressureReading requires batch_id or vessel_id -- give it a vessel.
        vessel = StorageVessel(
            name="Regression Vessel", vessel_type="keg", status="clean",
            fill_date=datetime.now(UTC).date(), total_volume=19.0, volume_remaining=19.0,
        )
        db().add(vessel)
        db().commit()
        reading = PressureReading(
            device_id=device.id, vessel_id=vessel.id, pressure=12.5, excluded=False,
        )
        db().add(reading)
        integration = Integration(
            name="Regression Pressure Target", measurement="pressure",
            type="custom_forward", enabled=True,
            config={"url": "http://8.8.8.8/hook", "method": "POST",
                    "template": "p=${pressure}", "headers": {}},
        )
        db().add(integration)
        db().commit()
        device_id_str, tenant_id_str = str(device.id), str(device.tenant_id)
    finally:
        db.remove()

    raw = _make_item(device_id=device_id_str, tenant_id=tenant_id_str)
    with patch("oss.jobs.pressure_forward.queue_len", return_value=1), \
         patch("oss.jobs.pressure_forward.queue_pop_to_processing", return_value=raw), \
         patch("oss.jobs.pressure_forward.deliver_custom",
               new_callable=AsyncMock, return_value=True) as mock_deliver, \
         patch("oss.jobs.pressure_forward.system_log_scheduler"):
        await task_drain_pressure_forward_queue()

    mock_deliver.assert_awaited_once()


@pytest.mark.asyncio
async def test_pour_drain_resolves_plain_string_ids_against_real_session():
    """Same regression, for the tap-keyed pour_forward.py sibling."""
    truncate_database()
    db = create_session()
    try:
        vessel = StorageVessel(
            name="Regression Keg", vessel_type="keg", status="serving",
            fill_date=datetime.now(UTC).date(), total_volume=19.0, volume_remaining=19.0,
        )
        db().add(vessel)
        db().commit()
        tap = Tap(name="Regression Tap")
        db().add(tap)
        db().commit()
        pour = PourEvent(
            vessel_id=vessel.id, tap_id=tap.id, pour_amount=0.33, volume_remaining=12.4,
        )
        db().add(pour)
        integration = Integration(
            name="Regression Pour Target", measurement="pour", type="custom_forward",
            enabled=True,
            config={"url": "http://8.8.8.8/hook", "method": "POST",
                    "template": "a=${pourAmount}", "headers": {}},
        )
        db().add(integration)
        db().commit()
        tap_id_str, tenant_id_str = str(tap.id), str(tap.tenant_id)
    finally:
        db.remove()

    raw = _make_item(tap_id=tap_id_str, tenant_id=tenant_id_str)
    with patch("oss.jobs.pour_forward.queue_len", return_value=1), \
         patch("oss.jobs.pour_forward.queue_pop_to_processing", return_value=raw), \
         patch("oss.jobs.pour_forward.deliver_custom",
               new_callable=AsyncMock, return_value=True) as mock_deliver, \
         patch("oss.jobs.pour_forward.system_log_scheduler"):
        await task_drain_pour_forward_queue()

    mock_deliver.assert_awaited_once()
