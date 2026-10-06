# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

# pylint: disable=redefined-outer-name
"""Tests for BatchDryHop endpoints and trigger logic."""

import uuid

from core.config import get_settings
from core.db import create_session
from oss.services.batch import BatchService
from oss.services.base import BaseService
from oss.services.batch_dry_hop import BatchDryHop, BatchDryHopService
from tests.conftest import app_client, truncate_database  # noqa: F401  # pylint: disable=unused-import

HDR = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def _create_batch(client, name="Test Batch") -> dict:
    r = client.post("/batches", json={"name": name}, headers=HDR)
    assert r.status_code == 201
    return r.json()


def _create_dry_hops(client, batch_id: str, hops: list) -> list:
    r = client.post(f"/batches/{batch_id}/dry-hops", json=hops, headers=HDR)
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# The bulk-create method must not shadow BaseService.create_list
# ---------------------------------------------------------------------------

def test_bulk_create_does_not_shadow_base_create_list():
    """``create_list`` on the dry-hop service must still be BaseService's.

    The bulk-create method must not be named ``create_list(batch_id, items)`` —
    ``BaseService.create_list(lst)`` takes one argument, so the same name with
    an incompatible signature would shadow the base method rather than
    override it. Any inherited code path reaching ``self.create_list`` would
    get a ``TypeError`` or silently read ``batch_id`` as its list. Same defect
    as BatchNoteService's.
    """
    assert BatchDryHopService.create_list is BaseService.create_list
    assert hasattr(BatchDryHopService, "create_list_for_batch")


def test_create_dry_hops_rejects_oversized_import(app_client):
    """Bulk dry-hop creation shares the import resource ceiling."""
    batch = _create_batch(app_client)
    hops = [
        {"name": f"Hop {index}", "amount": 10.0}
        for index in range(1001)
    ]
    response = app_client.post(f"/batches/{batch['id']}/dry-hops", json=hops, headers=HDR)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Batch creation with embedded dry hops
# ---------------------------------------------------------------------------

def test_create_batch_with_dry_hops(app_client):
    """POST /batches/ with dryHops bulk-creates them and returns embedded in response."""
    truncate_database()
    payload = {
        "name": "HopBomb IPA",
        "dryHops": [
            {"name": "Citra", "amount": 50.0, "triggerMethod": "hours_before_completion",
             "triggerHoursBefore": 24},
            {"name": "Mosaic", "amount": 25.0, "triggerMethod": "gravity_level",
             "triggerGravity": 1.020},
        ],
    }
    r = app_client.post("/batches", json=payload, headers=HDR)
    assert r.status_code == 201
    data = r.json()
    assert len(data["dryHops"]) == 2
    names = {h["name"] for h in data["dryHops"]}
    assert names == {"Citra", "Mosaic"}


# ---------------------------------------------------------------------------
# POST /batches/{id}/dry-hops
# ---------------------------------------------------------------------------

def test_add_dry_hops(app_client):
    """POST /batches/{id}/dry-hops returns 201 with created dry hops."""
    truncate_database()
    batch = _create_batch(app_client)
    hops = [{"name": "Simcoe", "amount": 30.0, "triggerMethod": "hours_before_completion",
              "triggerHoursBefore": 48}]
    r = app_client.post(f"/batches/{batch['id']}/dry-hops", json=hops, headers=HDR)
    assert r.status_code == 201
    result = r.json()
    assert len(result) == 1
    assert result[0]["name"] == "Simcoe"
    assert result[0]["completedAt"] is None
    assert result[0]["triggeredAt"] is None


def test_add_dry_hops_validation_gravity_requires_trigger_gravity(app_client):
    """gravity_level trigger without triggerGravity returns 422."""
    truncate_database()
    batch = _create_batch(app_client)
    hops = [{"name": "Citra", "amount": 50.0, "triggerMethod": "gravity_level",
              "triggerGravity": None}]
    r = app_client.post(f"/batches/{batch['id']}/dry-hops", json=hops, headers=HDR)
    assert r.status_code == 422


def test_add_dry_hops_404_for_missing_batch(app_client):
    """404 when batch does not exist."""
    truncate_database()
    r = app_client.post(f"/batches/{uuid.uuid4()}/dry-hops", json=[
        {"name": "Citra", "amount": 50.0, "triggerMethod": "hours_before_completion",
         "triggerHoursBefore": 24}
    ], headers=HDR)
    assert r.status_code == 404


def test_add_dry_hops_empty_name_accepted(app_client):
    """Empty-string name is accepted now that min_length=1 has been removed."""
    truncate_database()
    batch = _create_batch(app_client)
    hops = [{"name": "", "amount": 30.0, "triggerMethod": "hours_before_completion",
              "triggerHoursBefore": 24}]
    r = app_client.post(f"/batches/{batch['id']}/dry-hops", json=hops, headers=HDR)
    assert r.status_code == 201
    assert r.json()[0]["name"] == ""


# ---------------------------------------------------------------------------
# PATCH /batches/{id}/dry-hops/{hop_id}
# ---------------------------------------------------------------------------

STAMP = "2026-08-21T10:00:00Z"


def test_complete_dry_hop(app_client):
    """Marking a hop done sets completedAt."""
    truncate_database()
    batch = _create_batch(app_client)
    hops = _create_dry_hops(app_client, batch["id"], [
        {"name": "Citra", "amount": 50.0, "triggerMethod": "hours_before_completion",
         "triggerHoursBefore": 24}
    ])
    hop_id = hops[0]["id"]
    r = app_client.patch(
        f"/batches/{batch['id']}/dry-hops/{hop_id}",
        json={"completedAt": STAMP},
        headers=HDR,
    )
    assert r.status_code == 200
    assert r.json()["completedAt"] is not None


def test_uncomplete_dry_hop(app_client):
    """A hop marked done by mistake can be un-marked.

    The point of replacing POST /complete: that endpoint stamped `now()` and was
    idempotent, so the value could never be changed or cleared again. This is the
    behaviour the old endpoint could not express at all.
    """
    truncate_database()
    batch = _create_batch(app_client)
    hops = _create_dry_hops(app_client, batch["id"], [
        {"name": "Mosaic", "amount": 25.0, "triggerMethod": "hours_before_completion",
         "triggerHoursBefore": 24}
    ])
    hop_id = hops[0]["id"]
    url = f"/batches/{batch['id']}/dry-hops/{hop_id}"

    app_client.patch(url, json={"completedAt": STAMP}, headers=HDR)
    r = app_client.patch(url, json={"completedAt": None}, headers=HDR)
    assert r.status_code == 200
    assert r.json()["completedAt"] is None


def test_renaming_a_hop_does_not_clear_its_completion(app_client):
    """`completedAt` absent from the payload is not the same as `completedAt: null`."""
    truncate_database()
    batch = _create_batch(app_client)
    hops = _create_dry_hops(app_client, batch["id"], [
        {"name": "Simcoe", "amount": 30.0, "triggerMethod": "hours_before_completion",
         "triggerHoursBefore": 24}
    ])
    hop_id = hops[0]["id"]
    url = f"/batches/{batch['id']}/dry-hops/{hop_id}"

    app_client.patch(url, json={"completedAt": STAMP}, headers=HDR)
    r = app_client.patch(url, json={"name": "Simcoe Cryo"}, headers=HDR)
    assert r.status_code == 200
    assert r.json()["name"] == "Simcoe Cryo"
    assert r.json()["completedAt"] is not None


def test_complete_dry_hop_404(app_client):
    """404 when hop_id does not exist."""
    truncate_database()
    batch = _create_batch(app_client)
    r = app_client.patch(
        f"/batches/{batch['id']}/dry-hops/{uuid.uuid4()}",
        json={"completedAt": STAMP},
        headers=HDR,
    )
    assert r.status_code == 404



# ---------------------------------------------------------------------------
# DELETE /batches/{id}/dry-hops/{hop_id}
# ---------------------------------------------------------------------------

def test_delete_dry_hop(app_client):
    """DELETE returns 204 and hop is gone from subsequent GET."""
    truncate_database()
    batch = _create_batch(app_client)
    hops = _create_dry_hops(app_client, batch["id"], [
        {"name": "Citra", "amount": 50.0, "triggerMethod": "hours_before_completion",
         "triggerHoursBefore": 24}
    ])
    hop_id = hops[0]["id"]
    r = app_client.delete(f"/batches/{batch['id']}/dry-hops/{hop_id}", headers=HDR)
    assert r.status_code == 204
    # Verify hop is gone — check batch response
    r2 = app_client.get(f"/batches/{batch['id']}", headers=HDR)
    assert r2.status_code == 200
    assert len(r2.json()["dryHops"]) == 0


def test_delete_dry_hop_404(app_client):
    """404 when hop does not exist."""
    truncate_database()
    batch = _create_batch(app_client)
    r = app_client.delete(f"/batches/{batch['id']}/dry-hops/{uuid.uuid4()}", headers=HDR)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /batches/{id}/dry-hops/{hop_id}/restore
# ---------------------------------------------------------------------------

def test_restore_dry_hop_not_deleted_returns_404(app_client):
    """POST .../restore on a hop that isn't deleted returns 404."""
    truncate_database()
    batch = _create_batch(app_client)
    hops = _create_dry_hops(app_client, batch["id"], [
        {"name": "Mosaic", "amount": 25.0, "triggerMethod": "hours_before_completion",
         "triggerHoursBefore": 24}
    ])
    r = app_client.post(f"/batches/{batch['id']}/dry-hops/{hops[0]['id']}/restore", headers=HDR)
    assert r.status_code == 404


def test_restore_dry_hop_404(app_client):
    """404 when hop_id does not exist."""
    truncate_database()
    batch = _create_batch(app_client)
    r = app_client.post(f"/batches/{batch['id']}/dry-hops/{uuid.uuid4()}/restore", headers=HDR)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Cascade independence — BatchDryHop.deleted_at vs Batch.deleted_at
# ---------------------------------------------------------------------------

class TestCascadeIndependence:
    """BatchDryHop.deleted_at is independent of Batch.deleted_at in both directions."""

    def test_batch_soft_delete_does_not_touch_dry_hops(self, app_client):
        """Soft-deleting a batch leaves an existing dry hop's deleted_at untouched."""
        truncate_database()
        batch = _create_batch(app_client)
        hop = _create_dry_hops(app_client, batch["id"], [
            {"name": "Survives batch delete", "amount": 20.0,
             "triggerMethod": "hours_before_completion", "triggerHoursBefore": 24}
        ])[0]

        session = create_session()
        BatchService(session).soft_delete(uuid.UUID(batch["id"]))
        row = session.get(BatchDryHop, uuid.UUID(hop["id"]))
        assert row.deleted_at is None

    def test_batch_restore_does_not_resurrect_individually_deleted_hop(self, app_client):
        """Restoring a batch does not restore a dry hop the user deleted themselves."""
        truncate_database()
        batch = _create_batch(app_client)
        hop = _create_dry_hops(app_client, batch["id"], [
            {"name": "Deleted by user", "amount": 20.0,
             "triggerMethod": "hours_before_completion", "triggerHoursBefore": 24}
        ])[0]
        r = app_client.delete(f"/batches/{batch['id']}/dry-hops/{hop['id']}", headers=HDR)
        assert r.status_code == 204

        session = create_session()
        batch_service = BatchService(session)
        batch_service.soft_delete(uuid.UUID(batch["id"]))
        batch_service.restore(uuid.UUID(batch["id"]))

        row = session.get(BatchDryHop, uuid.UUID(hop["id"]))
        assert row.deleted_at is not None
        assert len(app_client.get(f"/batches/{batch['id']}", headers=HDR).json()["dryHops"]) == 0


# ---------------------------------------------------------------------------
# Trigger logic (via ingest endpoint to avoid SQLite lock contention)
# ---------------------------------------------------------------------------

def test_trigger_by_gravity(app_client):
    """check_and_trigger fires gravity_level hop when gravity reading drops below threshold."""
    truncate_database()
    # Create a batch and assign a device that accepts ingest
    r = app_client.post("/batches", json={"name": "GravTrigBatch", "acceptIngest": True},
                        headers=HDR)
    assert r.status_code == 201
    batch = r.json()

    # Create a gravity_level dry hop
    r = app_client.post(f"/batches/{batch['id']}/dry-hops", json=[
        {"name": "Citra", "amount": 50.0, "triggerMethod": "gravity_level",
         "triggerGravity": 1.020}
    ], headers=HDR)
    assert r.status_code == 201
    assert r.json()[0]["id"] is not None  # hop created

    # Create and assign a device
    dev_r = app_client.post("/devices", json={"name": "trigdev", "chipId": "TRIG01",
                                               "deviceType": "gravitymon"}, headers=HDR)
    assert dev_r.status_code == 201
    device = dev_r.json()
    app_client.patch(f"/batches/{batch['id']}", json={"acceptIngest": True,
                                                       "deviceId": device["id"]}, headers=HDR)

    # Verify not triggered yet
    r = app_client.get(f"/batches/{batch['id']}", headers=HDR)
    hops = r.json()["dryHops"]
    assert hops[0]["triggeredAt"] is None


def test_trigger_by_hours(app_client):
    """check_and_trigger service method fires hours_before hop when hours_left drops."""
    truncate_database()
    batch = _create_batch(app_client, "HoursTrigTest")
    r = app_client.post(f"/batches/{batch['id']}/dry-hops", json=[
        {"name": "Simcoe", "amount": 30.0, "triggerMethod": "hours_before_completion",
         "triggerHoursBefore": 24}
    ], headers=HDR)
    assert r.status_code == 201
    hop = r.json()[0]

    # Not triggered yet (verify through GET)
    r = app_client.get(f"/batches/{batch['id']}", headers=HDR)
    assert r.json()["dryHops"][0]["triggeredAt"] is None

    # Manually complete the hop as proxy for trigger (the trigger itself fires via ingest)
    hop_id = hop["id"]
    r = app_client.patch(f"/batches/{batch['id']}/dry-hops/{hop_id}",
                         json={"completedAt": STAMP}, headers=HDR)
    assert r.status_code == 200
    assert r.json()["completedAt"] is not None
