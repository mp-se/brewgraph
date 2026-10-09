# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Raw SQL built from an f-string must be reviewed before it is added.

SQLAlchemy's query builders parameterise values; a string passed to ``text()`` or ``op.execute()``
is sent as written. The sites below interpolate only hardcoded identifiers (table, column and enum
names taken from literal lists in the same file). A new f-string statement fails this test until
someone has checked that nothing user-controlled reaches it and added it here.
"""
import re
from pathlib import Path

API = Path(__file__).resolve().parents[1]
ROOTS = ("core", "oss", "migrations", "tests", "main_oss.py")
FSTRING_SQL = re.compile(r"""(?:text|execute)\(\s*f["']""")

REVIEWED = {
    # table/column names from literal lists; identifiers are quoted with the dialect's preparer
    "tests/conftest.py": 2,
    # enum type names from a literal tuple, in the frozen baseline migration
    "migrations/versions/000_initial_schema.py": 1,
}


def _sites():
    found = {}
    for root in ROOTS:
        base = API / root
        for path in ([base] if base.is_file() else base.rglob("*.py")):
            if ".venv" in path.parts or path.name == Path(__file__).name:
                continue
            count = len(FSTRING_SQL.findall(path.read_text(encoding="utf-8")))
            if count:
                found[path.relative_to(API).as_posix()] = count
    return found


def test_no_unreviewed_fstring_sql():
    """Every f-string passed to text()/execute() is a known, hardcoded-identifier site."""
    assert _sites() == REVIEWED
