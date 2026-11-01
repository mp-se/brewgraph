# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Upgrade and downgrade coverage for the nullable pressure revision."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

API_ROOT = Path(__file__).resolve().parents[1]


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


def _pressure_nullable(engine) -> bool:
    columns = inspect(engine).get_columns("pressure_reading")
    return next(c["nullable"] for c in columns if c["name"] == "pressure")


def test_revision_upgrades_and_downgrades(tmp_path):
    """Upgrade makes pressure nullable, a second upgrade is harmless, downgrade restores it."""
    database_url = f"sqlite:///{tmp_path / 'pressure-nullable.sqlite'}"
    engine = create_engine(database_url)
    try:
        _run(database_url, command.upgrade, "005")
        assert not _pressure_nullable(engine)

        _run(database_url, command.upgrade, "head")
        assert _pressure_nullable(engine)

        _run(database_url, command.downgrade, "005")
        assert not _pressure_nullable(engine)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM pressure_reading")).scalar() == 0
    finally:
        engine.dispose()
