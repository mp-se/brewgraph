# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Migration 001 adds the device calibration columns, and tolerates databases that have them."""
import os
import pathlib

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

API_ROOT = pathlib.Path(__file__).resolve().parent.parent
COLUMNS = {"gravity_formula", "gravity_formula_unit", "gravity_calibration_data"}


def _config(url: str) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _device_columns(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {column["name"] for column in inspect(engine).get_columns("device")}
    finally:
        engine.dispose()


def _run(url: str, action, revision: str) -> None:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        action(_config(url), revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def test_upgrade_adds_and_downgrade_removes_the_columns(tmp_path):
    url = f"sqlite:///{tmp_path / 'gravity.db'}"
    _run(url, command.upgrade, "000")
    assert not COLUMNS & _device_columns(url)

    _run(url, command.upgrade, "001")
    assert COLUMNS <= _device_columns(url)

    _run(url, command.downgrade, "000")
    assert not COLUMNS & _device_columns(url)

    _run(url, command.upgrade, "head")
    assert COLUMNS <= _device_columns(url)


def test_upgrade_tolerates_columns_that_already_exist(tmp_path):
    """A database made while these columns were part of 000 upgrades without a duplicate-column error."""
    url = f"sqlite:///{tmp_path / 'preexisting.db'}"
    _run(url, command.upgrade, "000")
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE device ADD COLUMN gravity_formula VARCHAR(200)"))
            conn.execute(text("ALTER TABLE device ADD COLUMN gravity_formula_unit VARCHAR(5)"))
            conn.execute(text(
                "ALTER TABLE device ADD COLUMN gravity_calibration_data JSON NOT NULL DEFAULT '[]'"
            ))
    finally:
        engine.dispose()

    _run(url, command.upgrade, "001")
    assert COLUMNS <= _device_columns(url)
