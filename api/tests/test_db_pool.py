# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""PostgreSQL pool size is configurable via DB_POOL_SIZE / DB_MAX_OVERFLOW / DB_POOL_TIMEOUT."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import NullPool, QueuePool

from core.config import Settings
from core.db import create_postgres_engine, engine

API_DIR = Path(__file__).resolve().parent.parent
URL = "postgresql://u:p@localhost:5432/db"
POOL_VARS = ("DB_POOL_SIZE", "DB_MAX_OVERFLOW", "DB_POOL_TIMEOUT")


def _load_settings(**env):
    """Import Settings in a fresh interpreter with `env` set; return (exit code, output)."""
    clean = {k: v for k, v in os.environ.items() if k not in POOL_VARS}
    code = (f"import sys; sys.path.insert(0, {str(API_DIR)!r}); "
            "from core.config import Settings; s = Settings(); "
            "print(s.db_pool_size, s.db_max_overflow, s.db_pool_timeout)")
    proc = subprocess.run([sys.executable, "-c", code], cwd=API_DIR, check=False,
                          env={**clean, **env},
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr


def test_defaults_equal_previous_hard_coded_values():
    """With nothing set the pool is 20 + 20 overflow with a 10 s timeout."""
    code, out, _ = _load_settings()
    assert (code, out) == (0, "20 20 10")
    pool = create_postgres_engine(URL, Settings(db_pool_size=20, db_max_overflow=20,
                                                db_pool_timeout=10)).pool
    assert (pool.size(), getattr(pool, "_max_overflow"), pool.timeout()) == (20, 20, 10)


def test_environment_overrides_reach_the_pool():
    """DB_* variables are read into Settings and applied to the engine's pool."""
    code, out, _ = _load_settings(DB_POOL_SIZE="2", DB_MAX_OVERFLOW="1", DB_POOL_TIMEOUT="3")
    assert (code, out) == (0, "2 1 3")
    pool = create_postgres_engine(URL, Settings(db_pool_size=2, db_max_overflow=1,
                                                db_pool_timeout=3)).pool
    assert isinstance(pool, QueuePool)
    assert (pool.size(), getattr(pool, "_max_overflow"), pool.timeout()) == (2, 1, 3)
    assert getattr(pool, "_pre_ping") is True


def test_zero_overflow_is_allowed():
    """DB_MAX_OVERFLOW=0 (a hard cap at the pool size) is valid."""
    assert _load_settings(DB_MAX_OVERFLOW="0")[:2] == (0, "20 0 10")


@pytest.mark.parametrize("name,value", [
    ("DB_POOL_SIZE", "0"), ("DB_POOL_SIZE", "-3"), ("DB_POOL_SIZE", "many"),
    ("DB_MAX_OVERFLOW", "-1"), ("DB_MAX_OVERFLOW", "1.5"),
    ("DB_POOL_TIMEOUT", "0"), ("DB_POOL_TIMEOUT", "soon"),
])
def test_invalid_values_are_rejected_naming_the_variable(name, value):
    """A nonsensical value stops startup with an error that names the variable."""
    code, _, err = _load_settings(**{name: value})
    assert code != 0
    assert f"'{name}'" in err


@pytest.mark.skipif(engine.dialect.name != "sqlite", reason="the suite runs on PostgreSQL here")
def test_sqlite_engine_is_unchanged():
    """The SQLite test engine still uses NullPool."""
    assert isinstance(engine.pool, NullPool)
