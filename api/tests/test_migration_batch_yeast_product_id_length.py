# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Migration 002 widens batch.yeast_product_id, and tolerates databases that already have it."""
import os
import pathlib

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

API_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(url: str, action, revision: str) -> None:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        action(cfg, revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _length(url: str) -> int:
    engine = create_engine(url)
    try:
        columns = inspect(engine).get_columns("batch")
        return next(c for c in columns if c["name"] == "yeast_product_id")["type"].length
    finally:
        engine.dispose()


def test_upgrade_widens_and_downgrade_narrows(tmp_path):
    """Upgrade takes the column from 40 to 64 and downgrade restores 40."""
    url = f"sqlite:///{tmp_path / 'yeast.db'}"
    _run(url, command.upgrade, "001")
    assert _length(url) == 40

    _run(url, command.upgrade, "002")
    assert _length(url) == 64

    _run(url, command.downgrade, "001")
    assert _length(url) == 40

    _run(url, command.upgrade, "head")
    assert _length(url) == 64


def test_upgrade_is_a_no_op_when_already_wide(tmp_path):
    """Running the upgrade twice leaves the column at 64."""
    url = f"sqlite:///{tmp_path / 'wide.db'}"
    _run(url, command.upgrade, "head")
    _run(url, command.downgrade, "001")
    _run(url, command.upgrade, "002")
    _run(url, command.upgrade, "002")
    assert _length(url) == 64
