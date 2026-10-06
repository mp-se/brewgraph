# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Say loudly at boot when the live database does not match the ORM.

Pre-release, the initial migration is edited in place rather than added to. That
is the right rule while nothing is deployed, but it has a consequence nobody is
told about: **a database created before an edit is now wrong, with no upgrade
path and no warning.** Tests never see it, because they build from `create_all`
on every run.

It is not hypothetical. A dev stack returned 500 on the dashboard for a morning
with `column prediction.tap_id does not exist`, because the schema predated that
day's model change.

This runs the same comparison `test_migration_orm_parity` performs, at startup
instead of only in CI, and logs what is missing. It never modifies the database
and never blocks startup: a false positive must not be able to take the API down.
"""
import logging
from typing import List

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

logger = logging.getLogger(__name__)

#: A missing table or column is real drift. Type and server-default differences are
#: dialect noise — SQLite has no native UUID or BOOLEAN — and would cry wolf.
_STRUCTURAL = {"add_table", "remove_table", "add_column", "remove_column"}


def describe(entry) -> str:
    """Render one alembic diff tuple as a readable line."""
    kind = entry[0]
    if kind in ("add_table", "remove_table"):
        return f"{kind}: {entry[1].name}"
    if kind in ("add_column", "remove_column"):
        return f"{kind}: {entry[2]}.{entry[3].name}"
    return str(entry)


def find_drift(engine, metadata) -> List[str]:
    """Return readable descriptions of structural differences, empty when in sync."""
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        diffs = compare_metadata(context, metadata)

    structural: List[str] = []
    for diff in diffs:
        # compare_metadata yields a tuple, or a list of tuples for multi-part changes.
        for entry in diff if isinstance(diff, list) else [diff]:
            if entry and entry[0] in _STRUCTURAL:
                structural.append(describe(entry))
    return structural


def warn_on_drift(engine, metadata) -> List[str]:
    """Log any drift at ERROR and return it. Never raises — startup must survive."""
    try:
        drift = find_drift(engine, metadata)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Could not compare the database against the ORM: %s", exc)
        return []

    if drift:
        logger.error(
            "DATABASE SCHEMA DRIFT — the live database does not match the models. "
            "Pre-release the initial migration is edited in place, so a database "
            "created before that edit has no upgrade path: recreate it. Differences "
            "(%d): %s",
            len(drift),
            "; ".join(sorted(drift)),
        )
    return drift
