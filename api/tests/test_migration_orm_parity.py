# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Migration ↔ ORM parity.

Every other test builds its schema with ``Base.metadata.create_all``, so the whole suite runs
against a schema the migration never produced. That makes ORM↔migration drift *structurally*
undetectable: a column declared on a model but missing from the migration exists in every test
and is absent in production.

Nothing about that failure is loud. It produces no import error and no runtime error —
SQLAlchemy accepts ``setattr`` on an unmapped attribute without ever emitting an UPDATE, and a
model-declared index that the migration never creates simply means the query that is instant in
CI is a sequential scan on a real deployment.

This module builds a throwaway SQLite database with ``alembic upgrade head`` and diffs it against
the ORM metadata, so that class of defect fails a test instead of reaching a self-hoster.

**Scope, stated honestly:** SQLite only. PostgreSQL is the standard backend for a self-hosted
deployment, and the Postgres-specific branches of ``000`` are *not* exercised here. This test
catches structural drift, not dialect bugs.
"""
import os
import pathlib
import tempfile

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from core.models import Base

API_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Diffs that are expected and must not fail the test. Keep this list short and justified —
# every entry is a place where the migration and the ORM genuinely disagree on purpose.
#
# Alembic reports SQLite-side type and server-default differences that say nothing about real
# drift: SQLite has no native UUID/BOOLEAN/TIMESTAMP, and the migration sets server_default on
# columns the ORM defaults in Python instead. Only structural differences — a missing table, or
# a column or index on one side and not the other — indicate the defect class this test exists
# to catch.
_STRUCTURAL = {"add_table", "remove_table", "add_column", "remove_column",
               "add_index", "remove_index"}


def _diff_migration_against_orm(db_path: str) -> list:
    """Run `alembic upgrade head` into db_path and return structural diffs vs ORM metadata."""
    url = f"sqlite:///{db_path}"
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(cfg, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            diffs = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    structural = []
    for diff in diffs:
        # compare_metadata yields either a tuple ("add_column", schema, table, Column)
        # or a list of such tuples for multi-part changes.
        entries = diff if isinstance(diff, list) else [diff]
        for entry in entries:
            if entry and entry[0] in _STRUCTURAL:
                structural.append(entry)
    return structural


def _describe(entry) -> str:
    """Render one alembic diff tuple as a readable line."""
    kind = entry[0]
    if kind in ("add_table", "remove_table"):
        return f"{kind}: {entry[1].name}"
    if kind in ("add_column", "remove_column"):
        return f"{kind}: {entry[2]}.{entry[3].name}"
    if kind in ("add_index", "remove_index"):
        return f"{kind}: {getattr(entry[1], 'name', entry[1])}"
    return str(entry)


# Named explicitly so the fixture function does not shadow the parameter it is
# injected into — tests take `migration_diffs`, this builds it.
@pytest.fixture(scope="module", name="migration_diffs")
def fixture_migration_diffs():
    """Structural differences between `alembic upgrade head` and the ORM metadata."""
    with tempfile.TemporaryDirectory() as tmp:
        yield _diff_migration_against_orm(os.path.join(tmp, "parity.sqlite"))


def test_migration_matches_orm_metadata(migration_diffs):
    """The migration and the ORM must describe the same tables, columns and indexes.

    add_column    = the ORM has a column the migration never creates -> present in tests via
                    create_all, missing in production.
    remove_column = the migration creates a column no model maps -> written as NULL forever,
                    and invisible to anything that filters on it.
    add_index     = the ORM declares an index production never gets -> queries that are fast
                    in every test are sequential scans on a real deployment.
    remove_index  = the migration creates an index no model declares -> drift in the other
                    direction, and a hint that the model lost a declaration.
    """
    assert not migration_diffs, "Migration/ORM drift:\n  " + "\n  ".join(
        _describe(d) for d in migration_diffs
    )


def test_alembic_upgrade_head_actually_runs():
    """Guard the guard: a migration that cannot execute would make the parity test vacuous."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "runs.sqlite")
        _diff_migration_against_orm(db_path)
        assert os.path.exists(db_path), "alembic upgrade head produced no database"
