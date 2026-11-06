# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Replace the free-form settings logo URL with a tap list logo chosen from a fixed set.

Revision ID: 008
Revises: 007
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

_TABLE = "tenant_settings"


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns(_TABLE)}


def upgrade() -> None:
    """Add tap_list_logo and drop logo_url, each only if not already done."""
    present = _columns()
    if "tap_list_logo" not in present:
        op.add_column(_TABLE, sa.Column("tap_list_logo", sa.String(length=20), nullable=True))
    if "logo_url" in present:
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column("logo_url")


def downgrade() -> None:
    """Restore logo_url (empty) and drop tap_list_logo, each only if needed."""
    present = _columns()
    if "logo_url" not in present:
        op.add_column(_TABLE, sa.Column("logo_url", sa.String(length=2048), nullable=True))
    if "tap_list_logo" in present:
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_column("tap_list_logo")
