# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Add the second PressureMon sensor column to a pressure reading.

Revision ID: 005
Revises: 004
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

_TABLE = "pressure_reading"
_COLUMN = "pressure2"


def _has_column() -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(c["name"] == _COLUMN for c in inspector.get_columns(_TABLE))


def upgrade() -> None:
    """Add the nullable column if it is not already there."""
    if not _has_column():
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.Float(), nullable=True))


def downgrade() -> None:
    """Drop the column if present."""
    if _has_column():
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column(_COLUMN)
