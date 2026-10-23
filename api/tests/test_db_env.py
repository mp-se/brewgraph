# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Isolate the test database from the dev database.

`core.db` reads DATABASE_URL at import time, so this module must be imported
before `core.db` (see `tests/conftest.py`, which imports it first). If
DATABASE_URL is unset, both `make run` and a bare `pytest` invocation would
otherwise resolve to the same sqlite:///./brewgraph.sqlite file, letting a
test run silently wipe dev data (`conftest.recreate_tables()` drops every
table on session start). The SQLite CI job and local runs use the isolated
default. With pytest-xdist, each worker uses a separate file. Explicit
DATABASE_URL values are refused for xdist so workers cannot drop or truncate
each other's tables.
"""
import os

DEFAULT_TEST_DATABASE_URL = "sqlite:///./test_brewgraph.sqlite"

worker_id = os.environ.get("PYTEST_XDIST_WORKER")
if worker_id:
    configured_url = os.environ.get("DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    if configured_url != DEFAULT_TEST_DATABASE_URL:
        raise RuntimeError("pytest-xdist requires the default isolated SQLite test database")
    os.environ["DATABASE_URL"] = f"sqlite:///./test_brewgraph_{worker_id}.sqlite"
else:
    os.environ.setdefault("DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
