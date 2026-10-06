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
table on session start). CI always sets DATABASE_URL explicitly (see
`.github/workflows/ci.yaml`), so this default is local-only and never
overrides an explicit setting.
"""
import os

DEFAULT_TEST_DATABASE_URL = "sqlite:///./test_brewgraph.sqlite"

os.environ.setdefault("DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
