# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Let a storage vessel hold the level a device reports, whatever its sign.

Revision ID: 007
Revises: 006
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

_TABLE = "storage_vessel"
_SIGN_CHECKS = {
    "ck_storage_vessel_total_volume_non_negative": "total_volume >= 0",
    "ck_storage_vessel_volume_remaining_non_negative": "volume_remaining >= 0",
}


def _present() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_check_constraints(_TABLE)} & set(_SIGN_CHECKS)


def upgrade() -> None:
    """Drop the non-negative volume checks that exist; the remaining <= total check stays."""
    present = _present()
    if present:
        with op.batch_alter_table(_TABLE) as batch:
            for name in sorted(present):
                batch.drop_constraint(name, type_="check")


def downgrade() -> None:
    """Re-add the non-negative volume checks; fails when a vessel holds a negative volume."""
    missing = set(_SIGN_CHECKS) - _present()
    if missing:
        with op.batch_alter_table(_TABLE) as batch:
            for name in sorted(missing):
                batch.create_check_constraint(name, _SIGN_CHECKS[name])
