# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Upgrade and downgrade coverage for the clean-vessel data repair revision."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

API_ROOT = Path(__file__).resolve().parents[1]
TENANT = "0" * 32


def _run(database_url: str, action, revision: str) -> None:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        action(cfg, revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _insert_vessel(engine, vessel_id: str, status: str, **values) -> None:
    """Insert a keg; `values` may set batch, tap, remaining and bottles."""
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO storage_vessel (id, tenant_id, batch_id, tap_id, vessel_type, name, "
            "fill_date, total_volume, volume_remaining, bottles_remaining, status, "
            "serving_temp_alert_enabled, fill_count, version, created_at, updated_at) VALUES "
            "(:id, :tenant, :batch, :tap, 'keg', 'Keg', '2026-01-01', 19, :remaining, :bottles, "
            ":status, 0, 1, 1, '2026-01-01', '2026-01-01')"
        ), {"id": vessel_id, "tenant": TENANT, "status": status, "batch": None, "tap": None,
            "remaining": 0.0, "bottles": None, **values})


def _row(engine, vessel_id: str):
    with engine.connect() as connection:
        return connection.execute(text(
            "SELECT status, batch_id, tap_id, volume_remaining, bottles_remaining, version "
            "FROM storage_vessel WHERE id = :id"
        ), {"id": vessel_id}).one()


def test_upgrade_releases_clean_vessels_and_leaves_others(tmp_path):
    """A clean vessel loses batch, tap and contents; other statuses are untouched."""
    database_url = f"sqlite:///{tmp_path / 'clean-vessel.sqlite'}"
    engine = create_engine(database_url)
    try:
        _run(database_url, command.upgrade, "008")
        # SQLite does not enforce foreign keys here, so the parents need no rows.
        batch_id, tap_id = "b" * 32, "a" * 32
        _insert_vessel(
            engine, "1" * 32, "clean", batch=batch_id, tap=tap_id, remaining=7.5, bottles=3
        )
        _insert_vessel(engine, "2" * 32, "clean", remaining=0.0, bottles=0)
        _insert_vessel(engine, "3" * 32, "clean", remaining=-1.5)
        _insert_vessel(engine, "4" * 32, "serving", batch=batch_id, remaining=0.0)

        _run(database_url, command.upgrade, "head")

        assert _row(engine, "1" * 32) == ("clean", None, None, 0, 0, 2)
        assert _row(engine, "2" * 32) == ("clean", None, None, 0, 0, 1)
        assert _row(engine, "3" * 32) == ("clean", None, None, 0, 0, 2)
        assert _row(engine, "4" * 32) == ("serving", batch_id, None, 0, None, 1)
    finally:
        engine.dispose()


def test_upgrade_twice_changes_nothing_more_and_downgrade_is_harmless(tmp_path):
    """Re-running the data repair is a no-op, and the downgrade keeps the repaired rows."""
    database_url = f"sqlite:///{tmp_path / 'clean-vessel-repeat.sqlite'}"
    engine = create_engine(database_url)
    try:
        _run(database_url, command.upgrade, "008")
        _insert_vessel(engine, "5" * 32, "clean", remaining=4.0)

        _run(database_url, command.upgrade, "head")
        _run(database_url, command.downgrade, "008")
        _run(database_url, command.upgrade, "head")

        assert _row(engine, "5" * 32) == ("clean", None, None, 0, 0, 2)
    finally:
        engine.dispose()
