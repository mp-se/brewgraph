# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tap service."""
import hashlib
from datetime import UTC, datetime
from typing import Any, List, Optional, Tuple

import sqlalchemy
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from core.models.registry import resolve_model
from core.utils import generate_token
from oss.schemas.tap import TapCreate, TapDashboardResponse, TapUpdate
from oss.services.base import BaseService

Batch = resolve_model("Batch")
StorageVessel = resolve_model("StorageVessel")
Tap = resolve_model("Tap")


class TapService(BaseService[Tap, TapCreate, TapUpdate]):
    """Service for managing tap fixtures and their dashboard projection."""

    def __init__(self, db_session: Session):
        """Initialise with a SQLAlchemy session."""
        super().__init__(Tap, db_session)

    def update(self, item_id: Any, obj: TapUpdate) -> Optional[Tap]:
        """Update a tap, snapshotting the throughput counter when last_cleaned_at is set.

        The snapshot has to live here rather than at the router: TapUpdate.last_cleaned_at
        is a plain writable field (oss/schemas/tap.py), so any caller reaching this
        service -- not just the PATCH route -- takes the snapshot with it. Hangs off
        the existing last_cleaned_at write path rather than adding a new trigger point.
        """
        tap = self.get_active(item_id)
        if tap is None:
            return None
        if "last_cleaned_at" in obj.model_dump(exclude_unset=True):
            tap.volume_at_last_clean = tap.total_volume_poured
        return super().update(item_id, obj)

    def list_page(self, page: int = 1, page_size: int = 50) -> Tuple[List[Tap], int]:
        """Offset-paginated tap list returning (items, total). Excludes soft-deleted taps."""
        stmt = select(Tap).where(Tap.deleted_at.is_(None)).order_by(Tap.created_at.desc())
        total: int = self.db_session.scalar(
            select(func.count()).select_from(stmt.subquery())  # pylint: disable=not-callable
        ) or 0
        offset = (page - 1) * page_size
        items = list(self.db_session.scalars(stmt.offset(offset).limit(page_size)).all())
        return items, total

    def create(self, obj: TapCreate) -> Tap:  # pylint: disable=arguments-renamed
        """Create a tap with a generated ingest token and token_hash.

        Token is server-generated and never client-supplied. Stage the token and
        lookup hash before committing so a failed write cannot leave behind a tap
        whose credential was never returned to the caller.
        """
        token = generate_token()
        tap = self.build(obj)
        tap.token = token
        tap.token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.commit()
        return tap

    def generate_token(self, tap_id) -> str:
        """Generate a new ingest token for a tap, store it, and return it.

        Same collision→409 translation as create() above, and the same reasoning
        for why it's needed despite being practically unreachable.
        """
        token = generate_token()
        tap = self.get(tap_id)
        if tap is None:
            raise ValueError(f"Tap {tap_id} not found")
        tap.token = token
        tap.token_hash = hashlib.sha256(token.encode()).hexdigest()
        try:
            self.db_session.commit()
        except sqlalchemy.exc.IntegrityError as e:
            self.db_session.rollback()
            raise HTTPException(status_code=409, detail="Conflict Error") from e
        except Exception as e:
            self.db_session.rollback()
            raise e
        return token

    def restore(self, tap_id) -> bool:
        """Clear `deleted_at`. False when not found or not currently deleted.

        Children soft-deleted in their own right stay deleted: this restores the
        tap, not everything that ever hung off it.
        """
        tap = self.get(tap_id)
        if tap is None or tap.deleted_at is None:
            return False
        tap.deleted_at = None
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return True

    def soft_delete(self, tap_id) -> bool:
        """Mark a tap as deleted; returns False if not found.

        Taps soft-delete like every other durable entity in this app — a tap that a
        keg is still assigned to must stay resolvable, and the brewer can undo via restore().
        """
        tap = self.get(tap_id)
        if tap is None:
            return False
        tap.deleted_at = datetime.now(UTC)
        try:
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e
        return True

    def find_by_token(self, token: str) -> Optional[Tap]:
        """Return the tap matching the given ingest token via SHA-256 hash index.

        Soft-deleted taps are excluded: a deleted tap must stop accepting pours.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return self.db_session.scalar(
            select(Tap).where(Tap.token_hash == token_hash, Tap.deleted_at.is_(None))
        )

    def find_active_vessel(self, tap_id) -> Optional[StorageVessel]:
        """Return the vessel currently assigned to a tap, or None."""
        return self.db_session.scalar(
            select(StorageVessel)
            .where(StorageVessel.tap_id == tap_id)
            .where(StorageVessel.deleted_at.is_(None))
        )

    def dashboard(self) -> List[TapDashboardResponse]:
        """Return all taps with their current vessel and batch info."""

        rows = (
            self.db_session.query(
                Tap, StorageVessel, Batch,
            )
            .filter(Tap.deleted_at.is_(None))
            .outerjoin(
                StorageVessel,
                (StorageVessel.tap_id == Tap.id) & (StorageVessel.deleted_at.is_(None)),
            )
            .outerjoin(Batch, Batch.id == StorageVessel.batch_id)
            .order_by(Tap.tap_number.nullslast(), Tap.name)
            .all()
        )

        result = []
        for tap, vessel, batch in rows:
            result.append(
                TapDashboardResponse(
                    id=tap.id,
                    name=tap.name,
                    tap_number=tap.tap_number,
                    location=tap.location,
                    notes=tap.notes,
                    created_at=tap.created_at,
                    updated_at=tap.updated_at,
                    vessel_id=vessel.id if vessel else None,
                    vessel_name=vessel.name if vessel else None,
                    vessel_type=vessel.vessel_type if vessel else None,
                    volume_remaining=vessel.volume_remaining if vessel else None,
                    batch_name=batch.name if batch else None,
                    batch_style=batch.style if batch else None,
                    batch_id=batch.id if batch else None,
                )
            )
        return result
