# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""§18 — DB-level CheckConstraints on PressureReading/TempReading ownership.

`device_id` is attribution only and is never part of either constraint
(user-confirmed) — both constraints are pure batch_id/vessel_id checks.
Exercises the constraints directly at the ORM/DB layer (bypassing the
service-level normalization every real write path applies) so a future
regression in either normalization or the constraint itself is caught even
if a caller somehow bypasses the router-level field-clearing.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from core.db import create_session
from core.models.registry import resolve_model
from oss.schemas.batch import BatchCreate
from oss.schemas.device import DeviceCreate
from oss.schemas.storage_vessel import StorageVesselCreate
from oss.services.batch import BatchService
from oss.services.device import DeviceService
from oss.services.storage_vessel import StorageVesselService
from tests.conftest import truncate_database

PressureReading = resolve_model("PressureReading")
TempReading = resolve_model("TempReading")


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate the database before each test."""
    truncate_database()


def _batch_id(session):
    return BatchService(session).create(BatchCreate(name="Ctx Batch")).id


def _vessel_id(session, batch_id):
    return StorageVesselService(session).create(
        StorageVesselCreate(
            batch_id=batch_id, vessel_number=1, vessel_type="keg",
            name="Ctx Keg", total_volume=19.0, volume_remaining=19.0,
        )
    ).id


def _device_id(session):
    return DeviceService(session).create(DeviceCreate(name="Ctx Device")).id


class TestPressureReadingHasContext:
    """`ck_pressure_reading_has_context`: at least one of batch_id/vessel_id."""

    def test_neither_batch_nor_vessel_rejected(self):
        """Neither batch_id nor vessel_id set violates the constraint."""
        session = create_session()
        session.add(PressureReading(pressure=101.0))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_device_id_alone_does_not_satisfy_the_constraint(self):
        """`device_id` is attribution only — it cannot stand in for batch/vessel context."""
        session = create_session()
        device_id = _device_id(session)
        session.add(PressureReading(pressure=101.0, device_id=device_id))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_batch_only_accepted(self):
        """batch_id alone satisfies the constraint."""
        session = create_session()
        batch_id = _batch_id(session)
        session.add(PressureReading(pressure=101.0, batch_id=batch_id))
        session.commit()  # must not raise

    def test_vessel_only_accepted(self):
        """vessel_id alone satisfies the constraint."""
        session = create_session()
        batch_id = _batch_id(session)
        vessel_id = _vessel_id(session, batch_id)
        session.add(PressureReading(pressure=101.0, vessel_id=vessel_id))
        session.commit()  # must not raise

    def test_batch_and_vessel_together_is_allowed_by_this_constraint(self):
        """Documents current scope: `has_context` only requires *at least one* —
        it does not itself reject both being set. Ownership normalization
        (clearing the other field) is what keeps this from happening on every
        real write path; this constraint is the has-any-context floor, not
        the exclusivity guarantee."""
        session = create_session()
        batch_id = _batch_id(session)
        vessel_id = _vessel_id(session, batch_id)
        session.add(PressureReading(pressure=101.0, batch_id=batch_id, vessel_id=vessel_id))
        session.commit()  # must not raise — not this constraint's job


class TestTempReadingNoConflictingContext:
    """`ck_temp_reading_no_conflicting_context`: batch_id and vessel_id are exclusive."""

    def test_batch_and_vessel_together_rejected(self):
        """Both batch_id and vessel_id set violates the constraint."""
        session = create_session()
        batch_id = _batch_id(session)
        vessel_id = _vessel_id(session, batch_id)
        session.add(TempReading(temperature=18.5, batch_id=batch_id, vessel_id=vessel_id))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_device_id_alongside_both_still_rejected(self):
        """`device_id` does not exempt a row from the exclusivity check either."""
        session = create_session()
        batch_id = _batch_id(session)
        vessel_id = _vessel_id(session, batch_id)
        device_id = _device_id(session)
        session.add(TempReading(
            temperature=18.5, batch_id=batch_id, vessel_id=vessel_id, device_id=device_id,
        ))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_vessel_without_batch_accepted(self):
        """A vessel-only temp reading (no batch) is a documented valid case —
        e.g. a keg in a storage fridge with no active fermentation."""
        session = create_session()
        batch_id = _batch_id(session)
        vessel_id = _vessel_id(session, batch_id)
        session.add(TempReading(temperature=18.5, vessel_id=vessel_id))
        session.commit()  # must not raise

    def test_batch_without_vessel_accepted(self):
        """A batch-only temp reading (no vessel) is likewise valid."""
        session = create_session()
        batch_id = _batch_id(session)
        session.add(TempReading(temperature=18.5, batch_id=batch_id))
        session.commit()  # must not raise

    def test_neither_batch_nor_vessel_accepted(self):
        """Unlike PressureReading, TempReading has no has-context floor —
        `device_id`-only ambient readings are a valid shape (e.g. a bare
        temperature probe with no batch/vessel assignment yet)."""
        session = create_session()
        device_id = _device_id(session)
        session.add(TempReading(temperature=18.5, device_id=device_id))
        session.commit()  # must not raise
