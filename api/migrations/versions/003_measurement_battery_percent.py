# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Add a nullable battery percentage to sensor readings.

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

_TABLES = ("gravity_reading", "pressure_reading", "temp_reading")
_COLUMN = "battery_percent"


def upgrade() -> None:
    """Add the field to each readings table if it is not present."""
    inspector = sa.inspect(op.get_bind())
    for table in _TABLES:
        if _COLUMN not in {column["name"] for column in inspector.get_columns(table)}:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column(_COLUMN, sa.Float(), nullable=True))


def downgrade() -> None:
    """Remove the field from each readings table when present."""
    inspector = sa.inspect(op.get_bind())
    for table in _TABLES:
        if _COLUMN in {column["name"] for column in inspector.get_columns(table)}:
            with op.batch_alter_table(table) as batch:
                batch.drop_column(_COLUMN)
