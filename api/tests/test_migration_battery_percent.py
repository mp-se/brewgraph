# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Upgrade, idempotence and downgrade coverage for the battery percentage revision."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

API_ROOT = Path(__file__).resolve().parents[1]
TABLES = ("gravity_reading", "pressure_reading", "temp_reading")
COLUMN = "battery_percent"


def _config(database_url: str) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def _migrate(database_url: str, revision: str) -> None:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(_config(database_url), revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _column_names(engine, table: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table)}


def test_revision_upgrades_and_downgrades(tmp_path):
    """Upgrade adds nullable columns; downgrade removes them."""
    database_url = f"sqlite:///{tmp_path / 'battery-percent.sqlite'}"
    engine = create_engine(database_url)
    try:
        _migrate(database_url, "head")
        assert all(COLUMN in _column_names(engine, table) for table in TABLES)

        previous = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = database_url
        try:
            command.downgrade(_config(database_url), "002")
        finally:
            if previous is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous
        assert all(COLUMN not in _column_names(engine, table) for table in TABLES)
    finally:
        engine.dispose()


def test_revision_accepts_columns_already_present(tmp_path):
    """Upgrade is safe if an existing database already has the new columns."""
    database_url = f"sqlite:///{tmp_path / 'existing-battery-percent.sqlite'}"
    engine = create_engine(database_url)
    try:
        _migrate(database_url, "002")
        with engine.begin() as connection:
            for table in TABLES:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {COLUMN} FLOAT"))

        _migrate(database_url, "head")
        assert all(COLUMN in _column_names(engine, table) for table in TABLES)

        previous = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = database_url
        try:
            command.downgrade(_config(database_url), "002")
        finally:
            if previous is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous
        assert all(COLUMN not in _column_names(engine, table) for table in TABLES)
    finally:
        engine.dispose()
