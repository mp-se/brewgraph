# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Upgrade and downgrade coverage for the storage vessel volume sign revision."""
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

API_ROOT = Path(__file__).resolve().parents[1]
SIGN_CHECKS = {
    "ck_storage_vessel_total_volume_non_negative",
    "ck_storage_vessel_volume_remaining_non_negative",
}
KEPT_CHECK = "ck_storage_vessel_volume_remaining_le_total"


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


def _checks(engine) -> set[str]:
    return {c["name"] for c in inspect(engine).get_check_constraints("storage_vessel")}


def _insert_vessel(engine, total: float, remaining: float) -> None:
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO storage_vessel (id, tenant_id, vessel_type, name, fill_date, "
            "total_volume, volume_remaining, status, serving_temp_alert_enabled, fill_count, "
            "version, created_at, updated_at) VALUES "
            "(:id, :tenant, 'keg', 'Keg', '2026-01-01', :total, :remaining, 'filled', 0, 1, 1, "
            "'2026-01-01', '2026-01-01')"
        ), {"id": os.urandom(16).hex(), "tenant": "0" * 32, "total": total, "remaining": remaining})


def test_upgrade_downgrade_upgrade_round_trip(tmp_path):
    """Upgrade drops the sign checks, downgrade restores them, upgrade drops them again."""
    database_url = f"sqlite:///{tmp_path / 'vessel-sign.sqlite'}"
    engine = create_engine(database_url)
    try:
        _run(database_url, command.upgrade, "006")
        assert SIGN_CHECKS <= _checks(engine)

        _run(database_url, command.upgrade, "head")
        assert not SIGN_CHECKS & _checks(engine)
        assert KEPT_CHECK in _checks(engine)
        _insert_vessel(engine, total=10.0, remaining=-2.0)

        with pytest.raises(IntegrityError):
            _insert_vessel(engine, total=1.0, remaining=2.0)

        with engine.begin() as connection:
            connection.execute(text("DELETE FROM storage_vessel"))
        _run(database_url, command.downgrade, "006")
        assert SIGN_CHECKS <= _checks(engine)
        with pytest.raises(IntegrityError):
            _insert_vessel(engine, total=10.0, remaining=-2.0)

        _run(database_url, command.upgrade, "head")
        assert not SIGN_CHECKS & _checks(engine)
    finally:
        engine.dispose()


def test_downgrade_fails_while_a_negative_volume_is_stored(tmp_path):
    """The restored check cannot hold a vessel that reports a negative level."""
    database_url = f"sqlite:///{tmp_path / 'vessel-negative.sqlite'}"
    engine = create_engine(database_url)
    try:
        _run(database_url, command.upgrade, "head")
        _insert_vessel(engine, total=10.0, remaining=-2.0)
        with pytest.raises(IntegrityError):
            _run(database_url, command.downgrade, "006")
    finally:
        engine.dispose()
