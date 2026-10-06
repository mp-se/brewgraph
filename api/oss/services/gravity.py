# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

# pylint: disable=duplicate-code

"""Gravity service for managing fermentation gravity readings."""
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
from oss.schemas.gravity_reading import (GravityChartPoint,
                                          GravityReadingCreate,
                                          GravityReadingUpdate)
from oss.services._batched import count_by_owner, latest_by_owner
from oss.services._cursor import Cursor, apply_cursor_filter, cursor_order_by
from oss.services.base import BaseService

GravityReading = resolve_model("GravityReading")

logger = logging.getLogger(__name__)


class GravityService(BaseService[GravityReading, GravityReadingCreate, GravityReadingUpdate]):
    """Service for managing fermentation gravity readings and batch associations."""

    def __init__(self, db_session: Session):
        super().__init__(GravityReading, db_session)

    def create(self, obj: GravityReadingCreate) -> GravityReading:
        self._validate_batch_exists(obj.batch_id)
        return super().create(obj)

    def create_list(self, lst: List[GravityReadingCreate]) -> List[GravityReading]:
        logger.info("Adding %d gravity records for batch", len(lst))
        if len(lst) == 0:
            raise HTTPException(status_code=400, detail="No gravity readings in request.")
        self._validate_batch_exists(lst[0].batch_id)
        return super().create_list(lst)

    def update_for_batch(self, batch_id, reading_id, obj: GravityReadingUpdate):
        """Update a reading only when it belongs to the requested batch."""
        return self.update_for_owner(reading_id, "batch_id", batch_id, obj)

    def search_by_batch_id(
        self,
        batch_id: int,
        include_excluded: bool = False,
        retention_cutoff: Optional[datetime] = None,
    ) -> List[GravityReading]:
        """Return gravity readings for a batch.

        By default only non-excluded readings are returned.
        Pass include_excluded=True to return all readings.
        """
        query = select(self.model).where(self.model.batch_id == batch_id)
        if not include_excluded:
            query = query.where(~self.model.excluded)
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        query = query.order_by(self.model.created_at.asc())
        objs: List[GravityReading] = self.db_session.scalars(query).all()
        logger.info(
            "Fetched gravity for batchId=%d, records found %d", batch_id, len(objs)
        )
        return objs

    def search_by_batch_id_cursor(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        batch_id: UUID,
        limit: int = 500,
        cursor: Optional[Cursor] = None,
        include_excluded: bool = False,
        retention_cutoff: Optional[datetime] = None,
    ) -> Tuple[List[GravityReading], bool]:
        """Return up to limit readings after cursor ((created_at, id) ASC), plus has_more flag."""
        query = select(self.model).where(self.model.batch_id == batch_id)
        if not include_excluded:
            query = query.where(~self.model.excluded)
        query = apply_cursor_filter(query, self.model, cursor)
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        query = query.order_by(*cursor_order_by(self.model)).limit(limit + 1)
        rows: List[GravityReading] = bounded_chart_rows(self.db_session, query)
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def latest_for_device(self, device_id: UUID) -> Optional[GravityReading]:
        """Return the most recent gravity reading for a device across all batches."""
        return self.db_session.scalars(
            select(self.model)
            .where(self.model.device_id == device_id)
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

    def latest_global(self, limit: int = 5) -> List[GravityReading]:
        """Return the most recent gravity readings across all batches."""
        return list(
            self.db_session.scalars(
                select(self.model)
                .order_by(self.model.created_at.desc())
                .limit(limit)
            ).all()
        )

    def search_by_batch_id_last_24h(self, batch_id: int) -> List[GravityReading]:
        """Return gravity readings for a batch from the last 24 hours."""
        since = datetime.now(UTC) - timedelta(hours=25)
        objs: List[GravityReading] = self.db_session.scalars(
            select(self.model)
            .where(
                self.model.batch_id == batch_id,
                self.model.created_at >= since,
            )
            .order_by(self.model.created_at.asc())
        ).all()
        logger.info(
            "Fetched last 24h gravity for batchId=%d, records found %d", batch_id, len(objs)
        )
        return objs

    def count_for_batch(
        self,
        batch_id: UUID,
        retention_cutoff: Optional[datetime] = None,
    ) -> int:
        """Return count of non-excluded gravity readings for a batch."""
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
    ) -> Optional[GravityReading]:
        """Return the most recent non-excluded gravity reading for a batch."""
        query = (
            select(self.model)
            .where(self.model.batch_id == batch_id, ~self.model.excluded)
        )
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        return self.db_session.scalars(
            query.order_by(self.model.created_at.desc()).limit(1)
        ).first()

    def earliest_for_batch(
        self,
        batch_id: UUID,
        retention_cutoff: Optional[datetime] = None,
    ) -> Optional[GravityReading]:
        """Return the oldest non-excluded gravity reading for a batch."""
        query = (
            select(self.model)
            .where(self.model.batch_id == batch_id, ~self.model.excluded)
        )
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        return self.db_session.scalars(
            query.order_by(self.model.created_at.asc()).limit(1)
        ).first()

    def highest_for_batch(
        self,
        batch_id: UUID,
        retention_cutoff: Optional[datetime] = None,
    ) -> Optional[GravityReading]:
        """Return the reading with the highest gravity value for a batch (OG)."""
        query = (
            select(self.model)
            .where(self.model.batch_id == batch_id, ~self.model.excluded)
        )
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        return self.db_session.scalars(
            query.order_by(self.model.gravity.desc()).limit(1)
        ).first()

    def lowest_for_batch(
        self,
        batch_id: UUID,
        retention_cutoff: Optional[datetime] = None,
    ) -> Optional[GravityReading]:
        """Return the reading with the lowest gravity value for a batch (FG)."""
        query = (
            select(self.model)
            .where(self.model.batch_id == batch_id, ~self.model.excluded)
        )
        if retention_cutoff is not None:
            query = query.where(self.model.created_at >= retention_cutoff)
        return self.db_session.scalars(
            query.order_by(self.model.gravity.asc()).limit(1)
        ).first()

    def recent_for_device_with_battery(
        self, device_id: UUID, limit: int = 20
    ) -> List[GravityReading]:
        """Return the most recent readings for a device that have a non-null battery value."""
        return list(
            self.db_session.scalars(
                select(self.model)
                .where(
                    self.model.device_id == device_id,
                    self.model.battery.isnot(None),
                )
                .order_by(self.model.created_at.desc())
                .limit(limit)
            ).all()
        )

    def rssi_readings_for_device_batch(
        self, device_id: UUID, batch_id: UUID, limit: int, oldest_first: bool = True
    ) -> List[GravityReading]:
        """Return up to limit readings for a device+batch that have a non-null rssi value."""
        order = self.model.created_at.asc() if oldest_first else self.model.created_at.desc()
        return list(
            self.db_session.scalars(
                select(self.model)
                .where(
                    self.model.device_id == device_id,
                    self.model.batch_id == batch_id,
                    self.model.rssi.isnot(None),
                )
                .order_by(order)
                .limit(limit)
            ).all()
        )

    def chart_data(
        self,
        batch_id: int,
        resolution: str = "raw",
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[GravityChartPoint]:
        """Return minimal chart data for a batch.

        `resolution` selects the bucket granularity; the response is additionally
        capped by LTTB. See `oss/services/_downsample.py`.
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

        rows: List[GravityReading] = list(self.db_session.scalars(query).all())
        rows = downsample(
            rows, x=lambda r: r.created_at, y=lambda r: r.gravity, resolution=resolution
        )
        return [
            GravityChartPoint(
                t=r.created_at,
                g=r.gravity,
                v=r.velocity,
                temp=r.temperature,
            )
            for r in rows
        ]
