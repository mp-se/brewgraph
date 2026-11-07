# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Release the batch, tap and contents of every vessel whose status is clean.

A clean vessel is empty and unassigned. Rows written before that held anywhere are
brought in line with it. The data changes; the schema does not.

Revision ID: 009
Revises: 008
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

_TABLE = "storage_vessel"


def upgrade() -> None:
    """Clear batch, tap and remaining figures on clean vessels; rows already clean are skipped."""
    if not sa.inspect(op.get_bind()).has_table(_TABLE):
        return
    op.execute(sa.text(
        "UPDATE storage_vessel SET batch_id = NULL, tap_id = NULL, volume_remaining = 0, "
        "bottles_remaining = 0, version = version + 1 "
        "WHERE status = 'clean' AND (batch_id IS NOT NULL OR tap_id IS NOT NULL "
        "OR volume_remaining <> 0 OR bottles_remaining IS NULL OR bottles_remaining <> 0)"
    ))


def downgrade() -> None:
    """Nothing to restore: the released links and figures are not kept anywhere."""
