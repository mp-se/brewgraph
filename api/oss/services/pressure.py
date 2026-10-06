# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

# pylint: disable=duplicate-code

"""Pressure service for managing fermentation pressure readings."""
import logging
from datetime import UTC, datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.models.registry import resolve_model
from oss.services._chart_window import bounded_chart_rows, bounded_chart_window
from oss.services._downsample import downsample
from oss.schemas.pressure_reading import (PressureChartPoint,
                                           PressureReadingCreate,
                                           PressureReadingUpdate)
from oss.services._batched import count_by_owner, latest_by_owner
from oss.services._cursor import Cursor, apply_cursor_filter, cursor_order_by
from oss.services.base import BaseService

PressureReading = resolve_model("PressureReading")

logger = logging.getLogger(__name__)


class PressureService(
    BaseService[PressureReading, PressureReadingCreate, PressureReadingUpdate]
):
    """Service for managing fermentation pressure readings and batch associations."""

    def __init__(self, db_session: Session):
        super().__init__(PressureReading, db_session)

    def create(self, obj: PressureReadingCreate) -> PressureReading:
        if obj.batch_id is not None:
            self._validate_batch_exists(obj.batch_id)
        return super().create(obj)

    def create_list(self, lst: List[PressureReadingCreate]) -> List[PressureReading]:
        logger.info("Adding %d pressure records for batch", len(lst))
        if len(lst) == 0:
            raise HTTPException(status_code=400, detail="No pressure readings in request.")
        if lst[0].batch_id is not None:
            self._validate_batch_exists(lst[0].batch_id)
        return super().create_list(lst)

    def search_by_batch_id(
        self,
        batch_id: int,
        include_excluded: bool = False,
        retention_cutoff: Optional[datetime] = None,
    ) -> List[PressureReading]:
        """Return pressure readings for a batch."""
        query = select(self.model).where(self.model.batch_id == batch_id)
        if not include_excluded:
            query = query.where(~self.model.excluded)
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        query = query.order_by(self.model.created_at.asc())
        objs: List[PressureReading] = self.db_session.scalars(query).all()
        logger.info(
            "Fetched pressure for batchId=%d, records found %d", batch_id, len(objs)
        )
        return objs

    def search_by_batch_id_cursor(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        batch_id: UUID,
        limit: int = 500,
        cursor: Optional[Cursor] = None,
        include_excluded: bool = False,
        retention_cutoff: Optional[datetime] = None,
    ) -> Tuple[List[PressureReading], bool]:
        """Return up to limit readings after cursor ((created_at, id) ASC), plus has_more flag."""
        query = select(self.model).where(self.model.batch_id == batch_id)
        if not include_excluded:
            query = query.where(~self.model.excluded)
        query = apply_cursor_filter(query, self.model, cursor)
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        query = query.order_by(*cursor_order_by(self.model)).limit(limit + 1)
        rows: List[PressureReading] = bounded_chart_rows(self.db_session, query)
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def latest_for_device(self, device_id: UUID) -> Optional[PressureReading]:
        """Return the most recent pressure reading for a device across all batches."""
        return self.db_session.scalars(
            select(self.model)
            .where(self.model.device_id == device_id)
            .order_by(self.model.created_at.desc())
            .limit(1)
        ).first()

    def latest_global(self, limit: int = 5) -> List[PressureReading]:
        """Return the most recent pressure readings across all batches."""
        return list(
            self.db_session.scalars(
                select(self.model)
                .order_by(self.model.created_at.desc())
                .limit(limit)
            ).all()
        )

    def search_by_batch_id_last_24h(self, batch_id: int) -> List[PressureReading]:
        """Return pressure readings for a batch from the last 24 hours."""
        since = datetime.now(UTC) - timedelta(hours=25)
        objs: List[PressureReading] = self.db_session.scalars(
            select(self.model)
            .where(
                self.model.batch_id == batch_id,
                self.model.created_at >= since,
            )
            .order_by(self.model.created_at.asc())
        ).all()
        logger.info(
            "Fetched last 24h pressure for batchId=%d, records found %d", batch_id, len(objs)
        )
        return objs

    def count_for_batch(
        self,
        batch_id: UUID,
        retention_cutoff: Optional[datetime] = None,
    ) -> int:
        """Return count of non-excluded pressure readings for a batch."""
        query = select(func.count()).select_from(  # pylint: disable=not-callable
            select(self.model).where(
                self.model.batch_id == batch_id,
                ~self.model.excluded,
            ).subquery()
        )
        if retention_cutoff is not None:
            query = select(func.count()).select_from(  # pylint: disable=not-callable
                select(self.model).where(
                    self.model.batch_id == batch_id,
                    ~self.model.excluded,
                    self.model.created_at >= retention_cutoff,
                ).subquery()
            )
        return self.db_session.scalar(query) or 0

    def latest_for_batch(
        self,
        batch_id: UUID,
        retention_cutoff: Optional[datetime] = None,
    ) -> Optional[PressureReading]:
        """Return the most recent non-excluded pressure reading for a batch."""
        query = (
            select(self.model)
            .where(self.model.batch_id == batch_id, ~self.model.excluded)
        )
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        return self.db_session.scalars(
            query.order_by(self.model.created_at.desc()).limit(1)
        ).first()

    def highest_for_batch(
        self,
        batch_id: UUID,
        retention_cutoff: Optional[datetime] = None,
    ) -> Optional[PressureReading]:
        """Return the reading with the highest pressure value for a batch."""
        query = (
            select(self.model)
            .where(self.model.batch_id == batch_id, ~self.model.excluded)
        )
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        return self.db_session.scalars(
            query.order_by(self.model.pressure.desc()).limit(1)
        ).first()

    def lowest_for_batch(
        self,
        batch_id: UUID,
        retention_cutoff: Optional[datetime] = None,
    ) -> Optional[PressureReading]:
        """Return the reading with the lowest pressure value for a batch."""
        query = (
            select(self.model)
            .where(self.model.batch_id == batch_id, ~self.model.excluded)
        )
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        return self.db_session.scalars(
            query.order_by(self.model.pressure.asc()).limit(1)
        ).first()

    def chart_data(
        self,
        batch_id: int,
        resolution: str = "raw",
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[PressureChartPoint]:
        """Return minimal chart data for a batch, bucketed and LTTB-capped."""
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

        rows: List[PressureReading] = bounded_chart_rows(self.db_session, query)
        rows = downsample(
            rows, x=lambda r: r.created_at, y=lambda r: r.pressure, resolution=resolution
        )
        return [
            PressureChartPoint(
                t=r.created_at,
                p=r.pressure,
                temp=r.temperature,
            )
            for r in rows
        ]

    def latest_for_vessel(self, vessel_id: UUID) -> Optional[PressureReading]:
        """Return the most recent non-excluded reading for a vessel, if any."""
        return self.db_session.scalars(
            select(self.model)
            .where(self.model.vessel_id == vessel_id, ~self.model.excluded)
            .order_by(self.model.created_at.desc())
            .limit(1)
        ).first()

    def latest_for_devices(self, device_ids):
        """Batched `latest_for_device` — one query for the whole device list."""
        return latest_by_owner(self.db_session, self.model, self.model.device_id, device_ids)

    def latest_for_batches(self, batch_ids, retention_cutoff=None):
        """Batched `latest_for_batch`."""
        extra = [~self.model.excluded]
        if retention_cutoff is not None:
            extra.append(self.model.created_at >= retention_cutoff)
        return latest_by_owner(
            self.db_session, self.model, self.model.batch_id, batch_ids, extra_where=extra
        )

    def earliest_for_batches(self, batch_ids, retention_cutoff=None):
        """Batched `earliest_for_batch`."""
        extra = [~self.model.excluded]
        if retention_cutoff is not None:
            extra.append(self.model.created_at >= retention_cutoff)
        return latest_by_owner(
            self.db_session, self.model, self.model.batch_id, batch_ids,
            extra_where=extra, newest_first=False,
        )

    def count_for_batches(self, batch_ids, retention_cutoff=None):
        """Batched `count_for_batch`. Batches with no readings are absent, not zero."""
        extra = [~self.model.excluded]
        if retention_cutoff is not None:
            extra.append(self.model.created_at >= retention_cutoff)
        return count_by_owner(
            self.db_session, self.model.batch_id, batch_ids, extra_where=extra
        )

    def latest_for_vessels(self, vessel_ids):
        """Batched `latest_for_vessel`."""
        return latest_by_owner(
            self.db_session, self.model, self.model.vessel_id, vessel_ids,
            extra_where=[~self.model.excluded],
        )

    def search_by_vessel_id_cursor(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        vessel_id: UUID,
        limit: int = 500,
        cursor: Optional[Cursor] = None,
        include_excluded: bool = False,
        retention_cutoff: Optional[datetime] = None,
    ) -> Tuple[List[PressureReading], bool]:
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

    def chart_data_by_vessel(
        self,
        vessel_id: int,
        resolution: str = "raw",
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[PressureChartPoint]:
        """Return vessel pressure chart data, bucketed and LTTB-capped."""
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

        rows: List[PressureReading] = list(self.db_session.scalars(query).all())
        rows = downsample(
            rows, x=lambda r: r.created_at, y=lambda r: r.pressure, resolution=resolution
        )
        return [
            PressureChartPoint(t=r.created_at, p=r.pressure, temp=r.temperature)
            for r in rows
        ]
