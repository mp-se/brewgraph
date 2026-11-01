# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Upgrade and downgrade coverage for the nullable gravity revision."""
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


def _gravity_nullable(engine) -> bool:
    columns = inspect(engine).get_columns("gravity_reading")
    return next(c["nullable"] for c in columns if c["name"] == "gravity")


def test_revision_upgrades_and_downgrades(tmp_path):
    """Upgrade makes gravity nullable, a second upgrade is harmless, downgrade restores it."""
    database_url = f"sqlite:///{tmp_path / 'gravity-nullable.sqlite'}"
    engine = create_engine(database_url)
    try:
        _run(database_url, command.upgrade, "003")
        assert not _gravity_nullable(engine)

        _run(database_url, command.upgrade, "head")
        assert _gravity_nullable(engine)

        _run(database_url, command.downgrade, "003")
        assert not _gravity_nullable(engine)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM gravity_reading")).scalar() == 0
    finally:
        engine.dispose()
