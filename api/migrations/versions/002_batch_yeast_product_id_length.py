# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Widen batch.yeast_product_id from 40 to 64 characters.

Yeast library product ids reach 42 characters, longer than the original column accepted.

Revision ID: 002
Revises: 001
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

_WIDE = 64
_NARROW = 40


def _current_length() -> int | None:
    columns = sa.inspect(op.get_bind()).get_columns("batch")
    column = next(c for c in columns if c["name"] == "yeast_product_id")
    return getattr(column["type"], "length", None)


def _alter(length: int) -> None:
    with op.batch_alter_table("batch") as batch:
        batch.alter_column(
            "yeast_product_id",
            existing_type=sa.String(),
            type_=sa.String(length),
            existing_nullable=True,
        )


def upgrade() -> None:
    """Widen the column unless it is already wide enough."""
    current = _current_length()
    if current is not None and current >= _WIDE:
        return
    _alter(_WIDE)


def downgrade() -> None:
    """Narrow the column back, truncating values that no longer fit."""
    current = _current_length()
    if current is not None and current <= _NARROW:
        return
    batch = sa.table("batch", sa.column("yeast_product_id", sa.String))
    op.execute(
        batch.update()
        .where(sa.func.length(batch.c.yeast_product_id) > _NARROW)
        .values(yeast_product_id=sa.func.substr(batch.c.yeast_product_id, 1, _NARROW))
    )
    _alter(_NARROW)
