# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Shared ingestion core: construction, transaction helpers, device/batch
resolution, and error logging.

Not itself a use-case: `resolve_device`/`find_or_create_batch` are used by both
the gravity and pressure use cases, and the commit helpers plus
`log_ingestion_error` are used by all four (gravity, pressure, chamber, pour).
Splitting these into a use-case module would just duplicate the same
self._db/self._device_svc plumbing across two homes instead of one.
"""
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

from core.enums import BatchStatus, DeviceBatchRole, IngestionSource
from core.models.platform import IngestionLog
from core.utils import truncate_ip
from oss.schemas.batch import BatchCreate
from oss.services.batch import BatchService
from oss.services.device import DeviceService
from oss.services.gravity import GravityService
from oss.services.pour_event import PourEventService
from oss.services.pressure import PressureService
from oss.services.storage_vessel import StorageVesselService
from oss.services.tap import TapService
from oss.services.temp_reading import TempService

from ._utils import Batch, Device

if TYPE_CHECKING:
    from core.models.platform import TenantSettings

logger = logging.getLogger(__name__)


class _IngestionCoreMixin:  # pylint: disable=too-many-instance-attributes
    """Construction, transaction helpers, device/batch resolution, and error logging."""

    def __init__(self, db: Session, settings: "TenantSettings"):
        self._db = db
        self._settings = settings
        self._device_svc = DeviceService(db)
        self._batch_svc = BatchService(db)
        self._gravity_svc = GravityService(db)
        self._pressure_svc = PressureService(db)
        self._tap_svc = TapService(db)
        self._pour_svc = PourEventService(db)
        self._temp_svc = TempService(db)
        self._vessel_svc = StorageVesselService(db)

    def _commit_or_raise(self) -> None:
        """Commit the session, rolling back and re-raising on failure.

        Shared by the top-level workflow methods that must fail the request
        (and undo any staged writes) if their final commit fails.
        """
        try:
            self._db.commit()
        except Exception as e:
            self._db.rollback()
            raise e

    def _commit_or_log(self, message: str, *args, level: int = logging.WARNING) -> None:
        """Commit the session; on failure, roll back and log instead of raising.

        For best-effort follow-on writes (liveness stamps, advisory triggers) where a
        write failure must not fail the request that produced it. `message` is a
        %-style logging format string; `args` are its positional placeholders before
        the caught exception, which is always appended last.
        """
        try:
            self._db.commit()
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._db.rollback()
            logger.log(level, message, *args, e)

    def resolve_device(
        self,
        token: Optional[str],
        device_id: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> Optional[Device]:
        """Resolve ingest identity by token, then a trusted-LAN device ID.

        A valid token always wins. The fallback deliberately accepts only the exact
        ``ID`` value supplied by the router, is limited to the device types below,
        and requires one unique type-scoped match. This compatibility path is not
        authentication: deployments exposed beyond a trusted LAN should use tokens.

        ``chamber_controller`` is included in the set, making the same trade every
        other member already makes — a broadcast carries a chip ID and its readings
        and nothing else — since excluding it would be inconsistency rather than a
        stricter stance: a chamber is no more sensitive than a hydrometer, and both
        are equally readable by anyone in radio range.
        """
        if token:
            device = self._device_svc.find_by_token(token)
            if device:
                return device
        allowed = {"ispindel", "gravitymon", "pressuremon", "chamber_controller"}
        if not device_id or device_type not in allowed:
            return None
        devices = self._device_svc.search_device_identifier(device_id, device_type)
        if len(devices) == 1:
            return devices[0]
        return None

    def find_or_create_batch(self, device: Device, device_type: str) -> Batch:
        """Find fermenting batch for device, auto-creating if none exists.

        An archived batch is rejected the same way a soft-deleted one already is:
        both are done fermenting and must not keep accumulating readings (see
        `BaseService._validate_batch_exists`, which every manual/bulk write path
        already enforces this through). There is no client here to show an error
        to — this runs from an unattended device poll — so the assigned batch is
        treated as if it were unset and falls through to auto-creating a fresh one
        below, exactly like a device with no `batch_id` at all.
        """
        if device.batch_id is not None:
            batch = self._batch_svc.get(device.batch_id)
            if (
                batch
                and batch.accept_ingest
                and batch.deleted_at is None
                and batch.status != BatchStatus.ARCHIVED.value
            ):
                return batch

        logger.info("Auto-creating batch for device id=%s", device.id)
        is_pressure = device_type == "pressuremon"
        create_data = BatchCreate(
            name=device.name or f"Batch for {device.id}",
            description="Automatically created",
            brew_date=datetime.today().date(),
            accept_ingest=True,
        )
        # Stage (not create/commit) the batch: it and the device-link fields below
        # must land in a single transaction, or a failure between the two leaves an
        # auto-created batch with no device pointing at it — an orphan indistinguishable
        # from real data. `Batch.id`'s uuid4 default is applied by the ORM at flush
        # time, not on instantiation, so flush (stage, no commit) to populate it
        # before reading it below.
        batch = self._batch_svc.build(create_data)
        self._db.flush()
        device.batch_id = batch.id
        device.batch_role = (
            DeviceBatchRole.PRESSURE if is_pressure else DeviceBatchRole.GRAVITY
        )
        device.vessel_id = None
        logger.info("Auto-created batch id=%s for device id=%s", batch.id, device.id)
        return batch

    def stamp_device_last_seen(self, device: Device) -> None:
        """Best-effort durable liveness, independent of reading attribution."""
        device.last_seen = datetime.now(UTC)
        self._commit_or_log("Failed to stamp device liveness: %s", level=logging.ERROR)

    @staticmethod
    def _resolve_ingestion_source(device_type: str) -> IngestionSource:
        """Map a raw ``device_type`` string to its ``IngestionSource`` category.

        ``source_type`` is ``nullable=False`` with no default, so every call must
        resolve to a real member. The mapping covers every ``device_type`` string
        the routers actually pass; an unrecognised one (only reachable from a test
        double, never from real traffic) falls back to ``GRAVITY`` rather than
        raising, since a wrong-but-non-null category beats crashing the audit log.
        """
        mapping = {
            "ispindel": IngestionSource.GRAVITY,
            "gravitymon": IngestionSource.GRAVITY,
            "pressuremon": IngestionSource.PRESSURE,
            "kegmon": IngestionSource.POUR,
            "chamber": IngestionSource.CHAMBER,
            "chamber_controller": IngestionSource.CHAMBER,
        }
        return mapping.get(device_type, IngestionSource.GRAVITY)

    def log_ingestion_error(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        ip: str,
        device_type: str,
        reason: str,
        error_detail: str | None = None,
        payload: dict | None = None,
        device: Optional[Device] = None,
    ) -> None:
        """Write a failed ingestion attempt to IngestionLog.

        ``device`` is optional and only ever passed for a drop where a ``Device`` was
        actually resolved before the failure — an unresolved-token drop has no device to
        attribute it to, and correctly passes none. When given, its
        ``failed_ingest_counter`` is incremented in the same commit as the log row: a log
        row without the counter update, or vice versa, would itself be a drift bug.
        """
        try:
            safe_payload: Optional[dict] = None
            if payload is not None:
                safe_payload = {k: ("***" if k == "token" else v) for k, v in payload.items()}
            raw_payload = json.dumps(safe_payload) if safe_payload is not None else None
            entry = IngestionLog(
                source_type=self._resolve_ingestion_source(device_type).value,
                device_type=device_type[:12],
                ip_address=truncate_ip(ip),
                reason=reason,
                error_detail=error_detail,
                payload=raw_payload[:4096] if raw_payload else None,
            )
            self._db.add(entry)
            if device is not None:
                device.failed_ingest_counter += 1
            self._db.commit()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to write ingestion log: %s", exc)
            self._db.rollback()
