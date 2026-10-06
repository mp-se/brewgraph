# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for BatchService methods not covered by endpoint tests."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from core.db import create_session
from core.enums import DeviceBatchRole
from core.models.registry import resolve_model
from oss.schemas.batch import BatchCreate
from oss.schemas.device import DeviceCreate
from oss.services.batch import BatchService
from oss.services.device import DeviceService
from tests.conftest import truncate_database

Device = resolve_model("Device")


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate the database before each test."""
    truncate_database()


def _svc():
    return BatchService(create_session())


def _create(name="B", **kwargs) -> object:
    svc = _svc()
    return svc.create(BatchCreate(name=name, **kwargs))


def _create_device_assigned_to_batch(batch_id, role=DeviceBatchRole.GRAVITY) -> object:
    """Create a device and assign it to the given batch."""
    session = create_session()
    dev_svc = DeviceService(session)
    device = dev_svc.create(DeviceCreate(name=f"dev-{uuid.uuid4().hex[:6]}"))
    device.batch_id = batch_id
    device.batch_role = role
    session.commit()
    return device


class TestSearchAcceptingIngest:
    """Tests for BatchService.search_accepting_ingest."""

    def test_returns_accepting_only(self):
        """Only batches with accept_ingest=True are returned."""
        _create("Yes", accept_ingest=True)
        _create("No", accept_ingest=False)
        results = _svc().search_accepting_ingest()
        assert all(b.accept_ingest for b in results)
        assert any(b.name == "Yes" for b in results)

    def test_excludes_soft_deleted(self):
        """Soft-deleted batches are excluded from accepting-ingest results."""
        b = _create("Del", accept_ingest=True)
        svc = _svc()
        svc.soft_delete(b.id)
        assert all(r.id != b.id for r in svc.search_accepting_ingest())


class TestSearchDeviceIdAccepting:
    """Tests for BatchService.search_device_id_accepting."""

    def test_finds_gravity_device_match(self):
        """Returns batches that are linked to the given device and accept ingest."""
        batch = _create("GravBatch", accept_ingest=True)
        _create("NoBatch", accept_ingest=True)
        dev = _create_device_assigned_to_batch(batch.id)
        results = _svc().search_device_id_accepting(dev.id)
        assert len(results) == 1
        assert results[0].name == "GravBatch"

    def test_ignores_non_accepting(self):
        """Batches linked to the device but not accepting ingest are excluded."""
        batch = _create("Inactive", accept_ingest=False)
        dev = _create_device_assigned_to_batch(batch.id)
        assert _svc().search_device_id_accepting(dev.id) == []


class TestSearchBrewfatherId:
    """Tests for BatchService.search_brewfather_id."""

    def test_finds_by_brewfather_id(self):
        """Returns the batch matching the given Brewfather batch ID."""
        _create("BF", brewfather_batch_id="BF001")
        _create("Other")
        results = _svc().search_brewfather_id("BF001")
        assert len(results) == 1
        assert results[0].brewfather_batch_id == "BF001"

    def test_returns_empty_for_unknown_id(self):
        """Returns empty list when no batch has the given Brewfather ID."""
        assert _svc().search_brewfather_id("UNKNOWN") == []


class TestGetNamesByIds:
    """Tests for BatchService.get_names_by_ids."""

    def test_returns_name_map(self):
        """Returns a dict mapping each batch ID to its name."""
        b1 = _create("Alpha")
        b2 = _create("Beta")
        result = _svc().get_names_by_ids([b1.id, b2.id])
        assert result[b1.id] == "Alpha"
        assert result[b2.id] == "Beta"

    def test_empty_list_returns_empty_dict(self):
        """Returns an empty dict when given an empty list of IDs."""
        assert _svc().get_names_by_ids([]) == {}


class TestListFilteredPage:
    """Tests for BatchService.list_filtered_page."""

    def test_pagination_returns_correct_page(self):
        """First page of 3 returns 3 items from a total of 5."""
        for i in range(5):
            _create(f"Batch{i}")
        items, total = _svc().list_filtered_page(page=1, page_size=3)
        assert total == 5
        assert len(items) == 3

    def test_page_two_returns_remainder(self):
        """Second page of 3 returns the remaining 2 items from a total of 5."""
        for i in range(5):
            _create(f"P2Batch{i}")
        items, total = _svc().list_filtered_page(page=2, page_size=3)
        assert total == 5
        assert len(items) == 2

    def test_device_id_filter(self):
        """Only batches linked to the given device_id are returned."""
        linked = _create("Linked")
        _create("Unlinked")
        dev = _create_device_assigned_to_batch(linked.id)
        items, total = _svc().list_filtered_page(device_id=str(dev.id))
        assert total == 1
        assert items[0].name == "Linked"


class TestRetentionCutoffBranches:
    """Tests for retention_cutoff branches in list_filtered and list_filtered_page."""

    def test_list_filtered_with_retention_cutoff(self):
        """list_filtered with retention_cutoff excludes batches created before cutoff."""
        b = _create("CutoffBatch")
        cutoff = datetime.now(UTC) + timedelta(seconds=1)
        results = BatchService(create_session()).list_filtered(retention_cutoff=cutoff)
        assert all(r.id != b.id for r in results)

    def test_list_filtered_page_with_retention_cutoff(self):
        """list_filtered_page with retention_cutoff excludes batches before cutoff."""
        _create("PageCutoffBatch")
        cutoff = datetime.now(UTC) + timedelta(seconds=1)
        items, total = BatchService(create_session()).list_filtered_page(retention_cutoff=cutoff)
        assert total == 0
        assert not items


class TestBatchServiceMisc:
    """Miscellaneous BatchService method coverage."""

    def test_list_returns_all_non_deleted(self):
        """list() returns all batches that have not been soft-deleted."""
        _create("Keep1")
        _create("Keep2")
        deleted = _create("Gone")
        _svc().soft_delete(deleted.id)
        results = _svc().list()
        names = [b.name for b in results]
        assert "Keep1" in names
        assert "Keep2" in names
        assert "Gone" not in names

    def test_search_device_id_finds_linked_batch(self):
        """search_device_id returns batches linked to the given device id."""
        batch = _create("DevBatch")
        _create("Other")
        dev = _create_device_assigned_to_batch(batch.id)
        results = _svc().search_device_id(dev.id)
        assert len(results) == 1
        assert results[0].name == "DevBatch"

    def test_soft_delete_returns_false_for_unknown_id(self):
        """soft_delete returns False when the batch id does not exist."""
        result = _svc().soft_delete(uuid.uuid4())
        assert result is False

    def test_list_filtered_with_device_id(self):
        """list_filtered returns only batches linked to the given device_id."""
        linked = _create("FilterLinked")
        _create("FilterOther")
        dev = _create_device_assigned_to_batch(linked.id)
        results = _svc().list_filtered(device_id=str(dev.id))
        assert len(results) == 1
        assert results[0].name == "FilterLinked"
