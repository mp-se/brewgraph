# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Database session management and configuration."""
import logging
import sqlite3
from datetime import datetime
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import NullPool

from core.config import get_settings
from core.models import Base
from core.models import \
    platform as _platform  # SystemLog + IngestionLog (infrastructure)

logger = logging.getLogger(__name__)

db_url = get_settings().database_url.get_secret_value()

if db_url.startswith("sqlite:"):
    logger.info("Creating database engine for SQLite.")

    def adapt_datetime(dt):
        """Convert Python datetime to ISO8601 string for SQLite."""
        return dt.isoformat() if isinstance(dt, datetime) else dt

    sqlite3.register_adapter(datetime, adapt_datetime)

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=NullPool)
else:
    logger.info("Creating database engine for Postgres.")
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=20,
        pool_timeout=10,
    )


def create_tables() -> None:
    """Create tables for all registered ORM models (must be imported before calling)."""
    Base.metadata.create_all(bind=engine)


@lru_cache
def create_session() -> scoped_session:
    """Create and cache the scoped session factory."""
    logger.info("Creating database session.")
    Session = scoped_session(  # pylint: disable=invalid-name
        sessionmaker(autocommit=False, autoflush=False, bind=engine)
    )
    return Session


def get_session() -> Generator[scoped_session, None, None]:
    """FastAPI dependency: yield a session and clean up afterwards."""
    Session = create_session()  # pylint: disable=invalid-name
    try:
        yield Session
    finally:
        Session.remove()


# Alias for FastAPI Depends convention
get_db = get_session
