# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""TempReading service — generic temperature ingest storage and aggregation."""
import logging
from datetime import UTC, datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models.registry import resolve_model
from oss.services._chart_window import bounded_chart_rows, bounded_chart_window
from oss.services._downsample import downsample
from oss.schemas.temp_reading import (TempChartPoint, TempReadingCreate,
                                      TempReadingUpdate)
from oss.services._batched import latest_by_owner
from oss.services._cursor import Cursor, apply_cursor_filter, cursor_order_by
from oss.services.base import BaseService

TempReading = resolve_model("TempReading")

logger = logging.getLogger(__name__)


class TempService(BaseService):
    """CRUD and aggregation for TempReading rows."""

    def __init__(self, db_session: Session):
        super().__init__(TempReading, db_session)

    def create(self, obj: TempReadingCreate) -> "TempReading":
        """Persist a new temperature reading."""
        return super().create(obj)

    def create_list(self, lst: List[TempReadingCreate]) -> List["TempReading"]:
        """Persist a batch of temperature readings in one transaction."""
        return super().create_list(lst)

    def latest_for_devices(self, device_ids):
        """Batched latest reading per device — for a batch's nominated temp_device_id."""
        return latest_by_owner(self.db_session, self.model, self.model.device_id, device_ids)

    def earliest_for_batches(self, batch_ids):
        """Batched earliest non-excluded measurement for each batch."""
        return latest_by_owner(
            self.db_session,
            self.model,
            self.model.batch_id,
            batch_ids,
            extra_where=[~self.model.excluded],
            newest_first=False,
        )

    def update(self, item_id, obj: TempReadingUpdate) -> Optional["TempReading"]:
        """Apply a partial update to a single reading."""
        return super().update(item_id, obj)

    def update_for_batch(self, batch_id, reading_id, obj: TempReadingUpdate):
        """Update a reading only when it belongs to the requested batch."""
        return self.update_for_owner(reading_id, "batch_id", batch_id, obj)

    def update_for_vessel(self, vessel_id, reading_id, obj: TempReadingUpdate):
        """Update a reading only when it belongs to the requested vessel."""
        return self.update_for_owner(reading_id, "vessel_id", vessel_id, obj)

    def search_by_batch_id_cursor(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        batch_id: UUID,
        limit: int = 500,
        cursor: Optional[Cursor] = None,
        include_excluded: bool = False,
        retention_cutoff: Optional[datetime] = None,
    ) -> Tuple[List["TempReading"], bool]:
        """Return up to limit readings after cursor ((created_at, id) ASC), plus has_more."""
        query = select(self.model).where(self.model.batch_id == batch_id)
        if not include_excluded:
            query = query.where(~self.model.excluded)
        query = apply_cursor_filter(query, self.model, cursor)
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        query = query.order_by(*cursor_order_by(self.model)).limit(limit + 1)
        rows = bounded_chart_rows(self.db_session, query)
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def chart_data(
        self,
        batch_id: UUID,
        resolution: str = "raw",
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[TempChartPoint]:
        """Return chart data for a batch, bucketed by `resolution` and LTTB-capped.

        Same contract as the gravity and pressure charts: a temperature series is
        the same kind of thing, so it takes the same parameters.
        """
        from_dt, to_dt = bounded_chart_window(from_dt, to_dt)
        query = select(self.model).where(
            self.model.batch_id == batch_id,
            ~self.model.excluded,
        )
        if from_dt is not None:
            query = query.where(self.model.created_at >= from_dt)
        if to_dt is not None:
            query = query.where(self.model.created_at <= to_dt)
        query = query.order_by(self.model.created_at.asc())

        rows = bounded_chart_rows(self.db_session, query)
        rows = downsample(
            rows, x=lambda r: r.created_at, y=lambda r: r.temperature, resolution=resolution
        )
        return [
            TempChartPoint(t=r.created_at, temp=r.temperature, temp_type=r.temp_type)
            for r in rows
        ]

    def latest_for_vessel(self, vessel_id: UUID) -> Optional["TempReading"]:
        """Return the most recent non-aggregate reading for a vessel, if any."""
        return self.db_session.scalars(
            select(self.model)
            .where(
                self.model.vessel_id == vessel_id,
                ~self.model.is_aggregate,
            )
            .order_by(self.model.created_at.desc())
            .limit(1)
        ).first()

    def latest_for_vessels(self, vessel_ids):
        """Batched `latest_for_vessel`."""
        return latest_by_owner(
            self.db_session, self.model, self.model.vessel_id, vessel_ids,
            extra_where=[~self.model.is_aggregate],
        )

    def list_for_batch(
        self,
        batch_id: UUID,
        hours: int = 72,
    ) -> List["TempReading"]:
        """Return readings for a batch within the last `hours`, oldest first."""
        from_dt = datetime.now(UTC) - timedelta(hours=hours)
        return list(self.db_session.scalars(
            select(self.model)
            .where(
                self.model.batch_id == batch_id,
                self.model.created_at >= from_dt,
            )
            .order_by(self.model.created_at.asc())
        ).all())

    def list_for_vessel(
        self,
        vessel_id: UUID,
        hours: int = 72,
        include_aggregates: bool = True,
    ) -> List["TempReading"]:
        """Return readings for a vessel within the last `hours`, oldest first."""
        from_dt = datetime.now(UTC) - timedelta(hours=hours)
        query = select(self.model).where(
            self.model.vessel_id == vessel_id,
            self.model.created_at >= from_dt,
        )
        if not include_aggregates:
            query = query.where(~self.model.is_aggregate)
        return list(self.db_session.scalars(query.order_by(self.model.created_at.asc())).all())

    def search_by_vessel_id_cursor(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        vessel_id: UUID,
        limit: int = 500,
        cursor: Optional[Cursor] = None,
        include_excluded: bool = False,
        retention_cutoff: Optional[datetime] = None,
    ) -> Tuple[List["TempReading"], bool]:
        """Return up to limit readings after cursor ((created_at, id) ASC), plus has_more."""
        query = select(self.model).where(self.model.vessel_id == vessel_id)
        if not include_excluded:
            query = query.where(~self.model.excluded)
        query = apply_cursor_filter(query, self.model, cursor)
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        query = query.order_by(*cursor_order_by(self.model)).limit(limit + 1)
        rows = list(self.db_session.scalars(query).all())
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def chart_data_for_vessel(
        self,
        vessel_id: UUID,
        resolution: str = "raw",
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[TempChartPoint]:
        """Return chart data for a vessel, same contract as the batch chart."""
        from_dt, to_dt = bounded_chart_window(from_dt, to_dt)
        query = select(self.model).where(
            self.model.vessel_id == vessel_id,
            ~self.model.excluded,
        )
        if from_dt is not None:
            query = query.where(self.model.created_at >= from_dt)
        if to_dt is not None:
            query = query.where(self.model.created_at <= to_dt)
        query = query.order_by(self.model.created_at.asc())

        rows = list(self.db_session.scalars(query).all())
        rows = downsample(
            rows, x=lambda r: r.created_at, y=lambda r: r.temperature, resolution=resolution
        )
        return [
            TempChartPoint(t=r.created_at, temp=r.temperature, temp_type=r.temp_type)
            for r in rows
        ]

    def raw_window(self, vessel_id: UUID, before: datetime) -> List["TempReading"]:
        """Return raw (non-aggregate) readings older than `before` for a vessel."""
        return list(self.db_session.scalars(
            select(self.model)
            .where(
                self.model.vessel_id == vessel_id,
                ~self.model.is_aggregate,
                self.model.created_at < before,
            )
            .order_by(self.model.created_at.asc())
        ).all())
