# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Allow a pressure reading without a pressure value.

Revision ID: 006
Revises: 005
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

_TABLE = "pressure_reading"
_COLUMN = "pressure"


def _is_nullable() -> bool:
    inspector = sa.inspect(op.get_bind())
    return next(c["nullable"] for c in inspector.get_columns(_TABLE) if c["name"] == _COLUMN)


def upgrade() -> None:
    """Make the column nullable if it is not already."""
    if not _is_nullable():
        with op.batch_alter_table(_TABLE) as batch:
            batch.alter_column(_COLUMN, existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    """Make the column required again; readings without a pressure cannot be kept."""
    if _is_nullable():
        readings = sa.table(_TABLE, sa.column(_COLUMN, sa.Float()))
        op.execute(sa.delete(readings).where(readings.c.pressure.is_(None)))
        with op.batch_alter_table(_TABLE) as batch:
            batch.alter_column(_COLUMN, existing_type=sa.Float(), nullable=False)
