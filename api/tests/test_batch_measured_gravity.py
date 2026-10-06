# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for og_measured/fg_measured snapshot-at-packaging behaviour on Batch."""
import uuid
from datetime import datetime, timedelta, timezone

from core.config import get_settings
from core.db import get_session
from oss.schemas.gravity_reading import GravityReadingCreate
from oss.services.gravity import GravityService
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH_DATA = {
    "name": "Measured Gravity Batch",
    "acceptIngest": True,
    "og": 1.055,
    "fg": 1.010,
}


def test_init():
    """Reset database state before suite."""
    truncate_database()


def _create_batch(app_client, overrides=None):
    data = {**BATCH_DATA, **(overrides or {})}
    r = app_client.post("/batches", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


def _add_reading(batch_id, gravity, days_ago, excluded=False):
    now = datetime.now(timezone.utc)
    db = next(get_session())
    svc = GravityService(db)
    svc.create(GravityReadingCreate(
        batch_id=uuid.UUID(batch_id),
        gravity=gravity,
        excluded=excluded,
        created_at=now - timedelta(days=days_ago),
    ))


def _package(app_client, batch_id, extra=None):
    payload = {"status": "packaged", **(extra or {})}
    r = app_client.patch(f"/batches/{batch_id}", json=payload, headers=headers)
    assert r.status_code == 200
    return r.json()


def test_packaging_snapshots_first_and_last_reading(app_client):
    """Transitioning to packaged snapshots og_measured from first, fg_measured from last."""
    test_init()
    batch = _create_batch(app_client)
    batch_id = batch["id"]

    _add_reading(batch_id, 1.056, days_ago=5)
    _add_reading(batch_id, 1.030, days_ago=3)
    _add_reading(batch_id, 1.012, days_ago=0)

    updated = _package(app_client, batch_id)
    assert updated["ogMeasured"] == 1.056
    assert updated["fgMeasured"] == 1.012


def test_packaging_without_readings_leaves_fields_null(app_client):
    """Packaging a batch with no gravity readings leaves og_measured/fg_measured NULL."""
    test_init()
    batch = _create_batch(app_client)
    batch_id = batch["id"]

    updated = _package(app_client, batch_id)
    assert updated["ogMeasured"] is None
    assert updated["fgMeasured"] is None


def test_packaging_does_not_overwrite_existing_values(app_client):
    """Re-triggering packaging never clobbers a manual correction already in place."""
    test_init()
    batch = _create_batch(app_client)
    batch_id = batch["id"]

    _add_reading(batch_id, 1.056, days_ago=5)
    _add_reading(batch_id, 1.012, days_ago=0)

    # Manually set values before packaging.
    r = app_client.patch(
        f"/batches/{batch_id}",
        json={"ogMeasured": 1.050, "fgMeasured": 1.008},
        headers=headers,
    )
    assert r.status_code == 200

    updated = _package(app_client, batch_id)
    assert updated["ogMeasured"] == 1.050
    assert updated["fgMeasured"] == 1.008


def test_packaging_skips_excluded_readings(app_client):
    """Excluded readings are skipped when finding first/last reading."""
    test_init()
    batch = _create_batch(app_client)
    batch_id = batch["id"]

    _add_reading(batch_id, 1.070, days_ago=6, excluded=True)   # excluded, would be "first"
    _add_reading(batch_id, 1.056, days_ago=5)                  # actual first non-excluded
    _add_reading(batch_id, 1.012, days_ago=1)                  # actual last non-excluded
    _add_reading(batch_id, 1.001, days_ago=0, excluded=True)   # excluded, would be "last"

    updated = _package(app_client, batch_id)
    assert updated["ogMeasured"] == 1.056
    assert updated["fgMeasured"] == 1.012


def test_create_ignores_measured_gravity_fields(app_client):
    """og_measured/fg_measured are not accepted on batch creation."""
    test_init()
    batch = _create_batch(app_client, {"ogMeasured": 1.099, "fgMeasured": 1.099})
    assert batch["ogMeasured"] is None
    assert batch["fgMeasured"] is None


def test_update_endpoint_accepts_measured_gravity_directly(app_client):
    """og_measured/fg_measured are settable via the update endpoint (user editing)."""
    test_init()
    batch = _create_batch(app_client)
    batch_id = batch["id"]

    r = app_client.patch(
        f"/batches/{batch_id}",
        json={"ogMeasured": 1.052, "fgMeasured": 1.009},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ogMeasured"] == 1.052
    assert data["fgMeasured"] == 1.009
