# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Device gravity formula, formula unit and calibration points.

Revision ID: 001
Revises: 000
Create Date: 2026-10-08
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = "000"
branch_labels = None
depends_on = None

_COLUMNS = ("gravity_formula", "gravity_formula_unit", "gravity_calibration_data")


def _existing_columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns("device")}


def upgrade() -> None:
    """Add the three app-managed calibration columns to device.

    Databases created while these columns were still part of the initial schema already
    have them, so each column is added only when it is missing.
    """
    existing = _existing_columns()
    with op.batch_alter_table("device") as batch:
        if "gravity_formula" not in existing:
            batch.add_column(sa.Column("gravity_formula", sa.String(200), nullable=True))
        if "gravity_formula_unit" not in existing:
            batch.add_column(sa.Column("gravity_formula_unit", sa.String(5), nullable=True))
        if "gravity_calibration_data" not in existing:
            batch.add_column(
                sa.Column("gravity_calibration_data", sa.JSON(), nullable=False, server_default="[]")
            )


def downgrade() -> None:
    """Drop the calibration columns."""
    existing = _existing_columns()
    with op.batch_alter_table("device") as batch:
        for name in _COLUMNS:
            if name in existing:
                batch.drop_column(name)
