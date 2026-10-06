# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for oss/jobs/retention_purge.py — the daily soft-delete purge job."""
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

from core.db import create_session
from core.models.registry import resolve_model
from oss.jobs.retention_purge import soft_delete_purge
from oss.schemas.batch import BatchCreate
from oss.services.batch import Batch, BatchService
from tests.conftest import truncate_database


def _make_batch(deleted_at=None):
    session = create_session()
    batch = BatchService(session).create(BatchCreate(name="Purge Test"))
    if deleted_at is not None:
        batch.deleted_at = deleted_at
        session.commit()
    return batch.id


def test_soft_delete_purge_runs():
    """soft_delete_purge deletes soft-deleted records older than the threshold."""
    truncate_database()
    soft_delete_purge(days=0)


def test_soft_delete_purge_db_error_swallowed():
    """SQLAlchemyError in soft_delete_purge must not propagate."""
    with patch("oss.jobs.retention_purge.create_session") as mock_session_factory:
        mock_session = MagicMock()
        mock_session.query.side_effect = OperationalError("", {}, Exception())
        mock_session_factory.return_value = mock_session
        soft_delete_purge(days=30)  # must not raise

        mock_session.rollback.assert_called_once()
        mock_session.remove.assert_called_once()


def test_soft_delete_purge_keeps_rows_inside_grace_window():
    """A row soft-deleted within the grace period survives the purge."""
    truncate_database()
    recent = datetime.now(UTC) - timedelta(days=5)
    batch_id = _make_batch(deleted_at=recent)

    soft_delete_purge(days=30)

    session = create_session()
    assert session.get(Batch, batch_id) is not None


def test_soft_delete_purge_removes_rows_past_grace_window():
    """A row soft-deleted longer ago than the grace period is hard-deleted."""
    truncate_database()
    old = datetime.now(UTC) - timedelta(days=45)
    batch_id = _make_batch(deleted_at=old)

    soft_delete_purge(days=30)

    session = create_session()
    assert session.get(Batch, batch_id) is None


def test_soft_delete_purge_honours_configured_grace_period():
    """A row past a 10-day grace period is purged even though it survives 30."""
    truncate_database()
    fifteen_days_ago = datetime.now(UTC) - timedelta(days=15)
    batch_id = _make_batch(deleted_at=fifteen_days_ago)

    soft_delete_purge(days=10)

    session = create_session()
    assert session.get(Batch, batch_id) is None


def test_soft_delete_purge_never_purges_a_restored_row():
    """A row soft-deleted past the grace window, then restored (deleted_at
    cleared) before the purge runs, is never purged."""
    truncate_database()
    old = datetime.now(UTC) - timedelta(days=45)
    batch_id = _make_batch(deleted_at=old)

    session = create_session()
    BatchService(session).restore(batch_id)

    soft_delete_purge(days=30)

    session = create_session()
    restored = session.get(Batch, batch_id)
    assert restored is not None
    assert restored.deleted_at is None


def test_soft_delete_purge_disabled_when_days_is_negative_one():
    """days=-1 disables the purge entirely (get_retention_cutoff returns None)."""
    truncate_database()
    ancient = datetime.now(UTC) - timedelta(days=3650)
    batch_id = _make_batch(deleted_at=ancient)

    soft_delete_purge(days=-1)

    session = create_session()
    assert session.get(Batch, batch_id) is not None


def test_soft_delete_purge_uses_configured_default_when_days_omitted():
    """When called with no days argument, the configured
    Settings.soft_delete_purge_days is used as the grace period."""
    with patch("oss.jobs.retention_purge.get_settings") as mock_settings, \
         patch("oss.jobs.retention_purge.create_session") as mock_session_factory:
        mock_settings.return_value = MagicMock(soft_delete_purge_days=7)
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.delete.return_value = 0
        mock_session_factory.return_value = mock_session
        soft_delete_purge()
    mock_settings.assert_called_once()


def test_purge_clears_device_link_before_deleting_the_batch():
    """A device on a purged batch survives, unassigned.

    A device is hardware: it outlives the beer it was measuring. Its FK must be
    released before the batch row goes, or the delete fails wherever foreign keys
    are enforced.
    """
    truncate_database()
    session = create_session()
    device_model = resolve_model("Device")
    old = datetime.now(UTC) - timedelta(days=45)
    batch_id = _make_batch(deleted_at=old)

    device = device_model(name="Pill", batch_id=batch_id, batch_role="primary")
    session.add(device)
    session.commit()
    device_id = device.id

    soft_delete_purge(days=30)

    session = create_session()
    assert session.get(Batch, batch_id) is None
    survivor = session.get(device_model, device_id)
    assert survivor is not None
    assert survivor.batch_id is None
    assert survivor.batch_role is None


def test_purge_removes_readings_owned_by_the_batch():
    """Readings go with their batch even though they were never soft-deleted themselves."""
    truncate_database()
    session = create_session()
    gravity_model = resolve_model("GravityReading")
    old = datetime.now(UTC) - timedelta(days=45)
    batch_id = _make_batch(deleted_at=old)

    session.add(gravity_model(batch_id=batch_id, gravity=1.050, temperature=20.0))
    session.commit()

    soft_delete_purge(days=30)

    session = create_session()
    assert session.get(Batch, batch_id) is None
    remaining = session.query(gravity_model).filter(
        gravity_model.batch_id == batch_id
    ).count()
    assert remaining == 0


def test_every_fk_into_a_purgeable_parent_is_classified():
    """No FK path is left unhandled when its parent is purged.

    A bulk DELETE bypasses the ORM cascade, so every child column pointing at a
    soft-deletable parent must be either owned (deleted with it) or a reference
    (nulled first). Adding an FK to the model layer fails this until it is
    classified in one map or the other.
    """
    import main_oss  # noqa: F401  # pylint: disable=import-outside-toplevel,unused-import
    from sqlalchemy import inspect  # pylint: disable=import-outside-toplevel

    from core.models.registry import \
        all_models  # pylint: disable=import-outside-toplevel
    from oss.jobs.retention_purge import (  # pylint: disable=import-outside-toplevel
        _OWNED, _REFERENCES)

    # Other tests register stand-ins in the shared registry; only real mapped
    # classes have a __tablename__.
    models = {m.__name__: m for m in all_models() if hasattr(m, "__tablename__")}
    by_table = {m.__tablename__: n for n, m in models.items()}

    unhandled = []
    for child_name, child in models.items():
        for column in inspect(child).columns:
            for fk in column.foreign_keys:
                parent = by_table.get(fk.column.table.name)
                if parent is None or not hasattr(models[parent], "deleted_at"):
                    continue
                owned = set(_OWNED.get(parent, ()))
                refs = {(c, cols[0]) for c, cols in _REFERENCES.get(parent, ())}
                if (child_name, column.name) not in owned | refs:
                    unhandled.append(f"{parent} <- {child_name}.{column.name}")

    assert not unhandled, (
        "FK paths unhandled when the parent is purged — classify each in _OWNED "
        f"or _REFERENCES: {sorted(unhandled)}"
    )


def test_purge_clears_device_provenance_from_readings():
    """A purged device leaves its readings intact, with `device_id` cleared."""
    truncate_database()
    session = create_session()
    device_model = resolve_model("Device")
    gravity_model = resolve_model("GravityReading")
    old = datetime.now(UTC) - timedelta(days=45)

    batch_id = _make_batch()
    device = device_model(name="Doomed", deleted_at=old)
    session.add(device)
    session.commit()
    device_id = device.id

    reading = gravity_model(
        batch_id=batch_id, device_id=device_id, gravity=1.020, temperature=19.0
    )
    session.add(reading)
    session.commit()
    reading_id = reading.id

    soft_delete_purge(days=30)

    session = create_session()
    assert session.get(device_model, device_id) is None
    survivor = session.get(gravity_model, reading_id)
    assert survivor is not None
    assert survivor.device_id is None
