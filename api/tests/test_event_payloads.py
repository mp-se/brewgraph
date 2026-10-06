# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Contract tests for SSE event payloads.

Every event on the SSE stream is {method, table, source, id}, where `table`
is the affected *entity* ("batch", "vessel", …), `source` says why it changed
("gravity", "pressure", "temperature", …), and `id` is that entity's ID.

This entity-shaped contract is pinned here so it cannot silently regress into
a coarser one that tells clients only "something changed somewhere" and
forces a full reload.
"""
import uuid
from unittest.mock import patch

from core.config import get_settings
from oss.extensions.tenant import DEFAULT_TENANT_ID
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def _create_batch(app_client) -> str:
    r = app_client.post("/batches", json={"name": "Event Payload Batch"}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _create_vessel(app_client, batch_id: str) -> str:
    r = app_client.post("/vessels", json={
        "batchId": batch_id,
        "vesselNumber": 1,
        "vesselType": "keg",
        "name": "Keg 1",
        "fillDate": "2026-05-01",
        "totalVolume": 19.0,
        "volumeRemaining": 19.0,
        "status": "filled",
    }, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def test_manual_batch_gravity_emits_batch_gravity_event(app_client):
    """POST /batches/{id}/gravity emits batch/gravity carrying the batch ID."""
    truncate_database()
    batch_id = _create_batch(app_client)

    with patch("oss.routers.batch_readings.notify_clients") as mock_notify:
        r = app_client.post(f"/batches/{batch_id}/gravity",
                            json={"gravity": 1.050, "temperature": 20.0}, headers=headers)
    assert r.status_code == 201
    mock_notify.assert_called_once_with("batch", "create", uuid.UUID(batch_id),
                                        DEFAULT_TENANT_ID, source="gravity")


def test_manual_batch_pressure_emits_batch_pressure_event(app_client):
    """POST /batches/{id}/pressure emits batch/pressure carrying the batch ID."""
    truncate_database()
    batch_id = _create_batch(app_client)

    with patch("oss.routers.batch_readings.notify_clients") as mock_notify:
        r = app_client.post(f"/batches/{batch_id}/pressure",
                            json={"pressure": 1.2, "temperature": 20.0}, headers=headers)
    assert r.status_code == 201
    mock_notify.assert_called_once_with("batch", "create", uuid.UUID(batch_id),
                                        DEFAULT_TENANT_ID, source="pressure")


def test_manual_vessel_pressure_emits_vessel_pressure_event(app_client):
    """POST /vessels/{id}/pressure emits vessel/pressure carrying the vessel ID."""
    truncate_database()
    vessel_id = _create_vessel(app_client, _create_batch(app_client))

    with patch("oss.routers.vessel_readings.notify_clients") as mock_notify:
        r = app_client.post(f"/vessels/{vessel_id}/pressure",
                            json={"pressure": 1.2, "temperature": 20.0}, headers=headers)
    assert r.status_code == 201
    mock_notify.assert_called_once_with("vessel", "create", uuid.UUID(vessel_id),
                                        DEFAULT_TENANT_ID, source="pressure")


def test_manual_vessel_temp_emits_vessel_temperature_event(app_client):
    """POST /vessels/{id}/temp emits vessel/temperature carrying the vessel ID."""
    truncate_database()
    vessel_id = _create_vessel(app_client, _create_batch(app_client))

    with patch("oss.routers.vessel_readings.notify_clients") as mock_notify:
        r = app_client.post(f"/vessels/{vessel_id}/temp",
                            json={"temperature": 18.5}, headers=headers)
    assert r.status_code == 201
    mock_notify.assert_called_once_with("vessel", "create", uuid.UUID(vessel_id),
                                        DEFAULT_TENANT_ID, source="temperature")


def test_no_endpoint_emits_a_dashboard_event():
    """No emitter may use the ID-less table/source "dashboard" placeholder.

    This is a source-level sweep rather than a per-endpoint test: the old shape
    appeared at eight call sites across three routers, and a ninth could be added
    without any existing test noticing.
    """
    from pathlib import Path  # pylint: disable=import-outside-toplevel

    oss_dir = Path(__file__).resolve().parent.parent / "oss"
    offenders = [
        str(p.relative_to(oss_dir))
        for p in oss_dir.rglob("*.py")
        if 'source="dashboard"' in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f'dashboard-shaped events still emitted in: {offenders}'
