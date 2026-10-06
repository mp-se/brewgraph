# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for core/models/__init__.py — Base ORM model helpers."""
import pytest

from core.db import create_session
from oss.schemas.batch import BatchCreate
from oss.services.batch import BatchService
from tests.conftest import truncate_database


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate the database before each test."""
    truncate_database()


class TestBaseModelHelpers:
    """Tests for Base ORM model helper methods."""

    def _batch(self):
        svc = BatchService(create_session())
        return svc.create(BatchCreate(name="BaseTest"))

    def test_table_name_returns_tablename(self):
        """table_name() returns the SQLAlchemy __tablename__ attribute."""
        b = self._batch()
        assert b.table_name() == "batch"

    def test_as_dict_returns_column_values(self):
        """as_dict() returns a dict of column names to their current values."""
        b = self._batch()
        d = b.as_dict()
        assert isinstance(d, dict)
        assert d["name"] == "BaseTest"
