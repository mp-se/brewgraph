# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""ORM model registry."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarative class for SQLAlchemy ORM models."""

    def table_name(self) -> str:
        """Return SQL table name for this model instance."""
        return str(getattr(self, "__tablename__", self.__class__.__name__.lower()))

    def as_dict(self) -> dict:
        """Return a serializable dict for mapped columns."""
        return {
            col.name: getattr(self, col.name)
            for col in self.__table__.columns
        }

__all__ = [
    "Base",
]
