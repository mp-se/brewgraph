# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Device service for managing brewery device configurations and operations."""
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import List, Optional, Tuple

import sqlalchemy
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from core.enums import DeviceColor, DeviceStatus
from core.models.registry import resolve_model
from oss.schemas.device import (DeviceCreate, DeviceStatusResponse,
                                 DeviceUpdate)
from oss.services.base import BaseService

_ACTIVE_HOURS = 4

Device = resolve_model("Device")

logger = logging.getLogger(__name__)


class DeviceService(BaseService[Device, DeviceCreate, DeviceUpdate]):
    """Service for managing brewery device configurations and operations."""

    def __init__(self, db_session: Session):
        super().__init__(Device, db_session)

    def list(self) -> List[Device]:
        """Return all non-deleted devices."""
        objs: List[Device] = self.db_session.scalars(
            select(self.model).where(self.model.deleted_at.is_(None))
        ).all()
        return objs

    def list_page(self, page: int = 1, page_size: int = 50) -> Tuple[List[Device], int]:
        """Offset-paginated device list returning (items, total)."""
        stmt = select(Device).where(Device.deleted_at.is_(None))
        total: int = self.db_session.scalar(
            select(func.count()).select_from(stmt.subquery())  # pylint: disable=not-callable
        ) or 0
        offset = (page - 1) * page_size
        items = list(self.db_session.scalars(stmt.offset(offset).limit(page_size)).all())
        return items, total

    def search_chip_id(self, chip_id: str) -> List[Device]:
        """Search devices by chip ID (excluding soft-deleted)."""
        objs: List[Device] = self.db_session.scalars(
            select(self.model).where(
                self.model.chip_id == chip_id,
                self.model.deleted_at.is_(None),
            )
        ).all()
        logger.info("Fetched device based on chipId=%s, records found %d", chip_id, len(objs))
        return objs
    def search_device_identifier(self, device_id: str, device_type: str) -> List[Device]:
        """Search one device type by its exact configured BLE identifier."""
        objs: List[Device] = self.db_session.scalars(
            select(self.model).where(
                self.model.chip_id == device_id,
                self.model.device_type == device_type,
                self.model.deleted_at.is_(None),
            )
        ).all()
        logger.info(
            "Fetched %s device based on transmitted ID=%s, records found %d",
            device_type,
            device_id,
            len(objs),
        )
        return objs

    def search_device_type(self, device_type: str) -> List[Device]:
        """Search devices by device_type (excluding soft-deleted)."""
        objs: List[Device] = self.db_session.scalars(
            select(self.model).where(
                self.model.device_type == device_type,
                self.model.deleted_at.is_(None),
            )
        ).all()
        logger.info(
            "Fetched devices with device_type=%s, records found %d", device_type, len(objs)
        )
        return objs

    def search_device_color(self, device_color: DeviceColor | str) -> List[Device]:
        """Search non-deleted devices by their preset physical color."""
        objs: List[Device] = self.db_session.scalars(
            select(self.model).where(
                self.model.device_color == device_color,
                self.model.deleted_at.is_(None),
            )
        ).all()
        logger.info(
            "Fetched device based on device_color=%s, records found %d", device_color, len(objs)
        )
        return objs

    def find_by_token(self, token: str) -> Optional[Device]:
        """Find device by token string (exact match)."""
        obj: Optional[Device] = self.db_session.scalars(
            select(self.model).where(
                self.model.token == token,
                self.model.deleted_at.is_(None),
            )
        ).first()
        return obj

    def generate_token(self, device_id: int) -> str:
        """Generate a 32-char random alphanumeric token, store it, and return it.

        `device.token` has a DB-level unique index — a collision surfaces here as a
        409, the same translation BaseService.create()/commit() already apply to
        every other unique-constraint conflict. Practically unreachable at 24 bytes
        of entropy, but an unhandled IntegrityError would otherwise fall through as
        an unwrapped 500.
        """
        token = secrets.token_urlsafe(24)
        device = self.get(device_id)
        if device is None:
            raise ValueError(f"Device {device_id} not found")
        device.token = token
        try:
            self.db_session.commit()
        except sqlalchemy.exc.IntegrityError as e:
            self.db_session.rollback()
            raise HTTPException(status_code=409, detail="Conflict Error") from e
        except Exception as e:
            self.db_session.rollback()
            raise e
        return token

    def status_for_all(self) -> List[DeviceStatusResponse]:
        """Return computed connectivity status for every non-deleted device."""
        now = datetime.now(UTC)
        results = []
        for device in self.list():
            # Device.last_seen is the durable connectivity signal.  Reading rows
            # describe measurements and may intentionally be dropped when no valid
            # attribution context exists.
            last_seen = device.last_seen
            if last_seen is None:
                status = DeviceStatus.NEVER_SEEN
            else:
                age = now - last_seen
                status = (
                    DeviceStatus.ACTIVE if age <= timedelta(hours=_ACTIVE_HOURS)
                    else DeviceStatus.DISCONNECTED
                )
            results.append(
                DeviceStatusResponse(device_id=device.id, status=status, last_seen_at=last_seen)
            )
        return results

    def restore(self, device_id) -> bool:
        """Clear `deleted_at`. False when not found or not currently deleted.

        Children soft-deleted in their own right stay deleted: this restores the
        device, not everything that ever hung off it.
        """
        device = self.get(device_id)
        if device is None or device.deleted_at is None:
            return False
        device.deleted_at = None
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return True

    def soft_delete(self, device_id: int) -> bool:
        """Soft-delete a device by setting deleted_at."""
        device = self.get(device_id)
        if device is None:
            return False
        device.deleted_at = datetime.now(UTC)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return True
