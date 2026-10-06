# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""The boot-time drift check must see a stale database, and stay quiet on a fresh one.

A dev stack once returned 500 on the dashboard all morning with `column
prediction.tap_id does not exist`, because the database predated that day's
in-place migration edit. Nothing said so at startup, and tests could not: they
build from `create_all` every run.
"""
import sqlalchemy as sa

from core.schema_drift import find_drift, warn_on_drift


def _metadata_with_two_tables() -> sa.MetaData:
    meta = sa.MetaData()
    sa.Table(
        "drift_probe", meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(50)),
    )
    return meta


def test_no_drift_reported_when_the_database_matches():
    """The happy path must be silent, or the warning becomes noise people ignore."""
    engine = sa.create_engine("sqlite://")
    meta = _metadata_with_two_tables()
    meta.create_all(engine)
    try:
        assert find_drift(engine, meta) == []
    finally:
        engine.dispose()


def test_a_missing_column_is_reported():
    """The exact failure that cost a morning: the model has a column the database lacks."""
    engine = sa.create_engine("sqlite://")
    old = _metadata_with_two_tables()
    old.create_all(engine)

    new = _metadata_with_two_tables()
    new.tables["drift_probe"].append_column(sa.Column("tap_id", sa.String(36)))
    try:
        drift = find_drift(engine, new)
        assert drift == ["add_column: drift_probe.tap_id"], drift
    finally:
        engine.dispose()


def test_a_missing_table_is_reported():
    """A model registered after the database was built."""
    engine = sa.create_engine("sqlite://")
    sa.MetaData().create_all(engine)
    meta = _metadata_with_two_tables()
    try:
        assert find_drift(engine, meta) == ["add_table: drift_probe"]
    finally:
        engine.dispose()


def test_warn_on_drift_never_raises():
    """Startup must survive a broken comparison — a false positive cannot take the API down."""
    class _Exploding:
        def connect(self):
            raise RuntimeError("no database")

    assert warn_on_drift(_Exploding(), _metadata_with_two_tables()) == []
