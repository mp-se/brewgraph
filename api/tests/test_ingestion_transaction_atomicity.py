# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""IngestionService.ingest_gravity must not leave an orphan batch behind.

`find_or_create_batch` does not commit itself — it only `build()`s +
`flush()`s a staged batch and stages the device link, so a caller can fold it
into a larger atomic unit. `ingest_gravity`/`ingest_pressure` are that unit:
liveness (`Device.last_seen`) is stamped and committed independently and
first (best-effort, mirrors `stamp_tap_last_seen`), then batch-create +
device-link + reading-write are staged together and committed once. A
failure anywhere in that staged sequence rolls back the whole thing — no
orphan batch, no batch-with-no-reading — but the liveness stamp, already
durably committed before the staged sequence began, survives.

This test simulates a failure in the reading-write step (after a successful
batch-create+link stage) and asserts nothing from the staged sequence was
persisted, while the independently-committed liveness stamp was.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from core.db import create_session
from core.models.registry import resolve_model
from oss.schemas.device import DeviceCreate
from oss.services.device import DeviceService
from oss.services.ingestion import IngestionService
from tests.conftest import truncate_database

Batch = resolve_model("Batch")
GravityReading = resolve_model("GravityReading")


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate the database before each test."""
    truncate_database()


def _create_device(session):
    return DeviceService(session).create(DeviceCreate(name=f"dev-{uuid.uuid4().hex[:6]}"))


def test_ingest_gravity_leaves_no_orphan_batch_when_reading_write_fails():
    """A failure in the reading-write step rolls back the staged batch+link.

    The liveness stamp committed before the staged sequence started must
    survive the rollback — it is a separate, already-durable transaction.
    """
    session = create_session()
    device = _create_device(session)

    svc = IngestionService(session, MagicMock())
    with patch.object(svc, "write_gravity", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            svc.ingest_gravity(device, "gravitymon", {"gravity": 1.050})

    assert session.query(Batch).count() == 0

    fresh = create_session()
    persisted_device = DeviceService(fresh).get(device.id)
    assert persisted_device.batch_id is None
    assert persisted_device.last_seen is not None


def test_ingest_gravity_commits_batch_link_and_reading_together_on_success():
    """On the happy path, batch creation, device link, and reading write are one commit."""
    session = create_session()
    device = _create_device(session)

    svc = IngestionService(session, MagicMock())
    batch, reading = svc.ingest_gravity(device, "gravitymon", {"gravity": 1.050})

    fresh = create_session()
    persisted_device = DeviceService(fresh).get(device.id)
    assert persisted_device.batch_id == batch.id
    assert fresh.query(Batch).filter(Batch.id == batch.id).count() == 1
    assert fresh.query(GravityReading).filter(GravityReading.id == reading.id).count() == 1
