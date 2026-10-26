# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Exercise JSON, UTC timestamps, and batched owner queries on SQLite."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select
from sqlalchemy.orm import Session, declarative_base

from core.models.types import JsonDocument, UtcDateTime
from oss.services._batched import count_by_owner, group_by_owner, latest_by_owner
from oss.services._downsample import downsample


def test_json_and_utc_round_trip():
    """Structured values and aware instants survive a SQLite round trip."""
    engine = create_engine("sqlite://")
    table = Table("sample", MetaData(), Column("id", Integer, primary_key=True),
                  Column("payload", JsonDocument), Column("recorded_at", UtcDateTime()))
    table.create(engine)
    instant = datetime(2026, 1, 1, 12, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(table.insert(), {"payload": {"items": [1, {"ok": True}]},
                                            "recorded_at": instant})
        row = connection.execute(select(table.c.payload, table.c.recorded_at)).one()
    assert row.payload == {"items": [1, {"ok": True}]}
    assert row.recorded_at == instant
    assert row.recorded_at.tzinfo is not None


def test_batched_owner_queries_and_downsampling():
    """Batched IN lists select the right owners and chart buckets preserve first rows."""
    base = declarative_base()

    class Reading(base):  # pylint: disable=too-few-public-methods
        """A minimal reading for the query helpers."""
        __tablename__ = "reading"
        id = Column(Integer, primary_key=True)
        owner_id = Column(Integer, nullable=False)
        created_at = Column(UtcDateTime(), nullable=False)
        value = Column(Integer, nullable=False)

    engine = create_engine("sqlite://")
    base.metadata.create_all(engine)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    with Session(engine) as session:
        session.add_all([Reading(owner_id=owner, created_at=start + timedelta(minutes=minute),
                                 value=minute)
                         for owner, minute in [(1, 0), (1, 30), (1, 60), (2, 0)]])
        session.commit()
        assert count_by_owner(session, Reading.owner_id, [1, 2, 3]) == {1: 3, 2: 1}
        assert latest_by_owner(session, Reading, Reading.owner_id, [1, 2])[1].value == 60
        grouped = group_by_owner(session, Reading, Reading.owner_id, [1, 2])
        assert {owner: len(rows) for owner, rows in grouped.items()} == {1: 3, 2: 1}
        rows = sorted(grouped[1], key=lambda row: row.created_at)
        assert [row.value for row in downsample(rows, lambda row: row.created_at,
                                                lambda row: row.value, "hourly")] == [0, 60]
