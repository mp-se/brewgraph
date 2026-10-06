# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Shared, sanitized projections for the anonymous public display."""
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.models.registry import resolve_model
from oss.schemas.public_display import (PublicBottleItem, PublicDisplayContextResponse,
                                        PublicLastPour, PublicServing, PublicTapItem)

Batch = resolve_model("Batch")
PourEvent = resolve_model("PourEvent")
PressureReading = resolve_model("PressureReading")
StorageVessel = resolve_model("StorageVessel")
Tap = resolve_model("Tap")
TempReading = resolve_model("TempReading")
TenantSettings = resolve_model("TenantSettings")


@dataclass(frozen=True)
class PublicDisplayContext:
    """Caller-owned display scope and presentation values.

    ``scope_id`` is an opaque cache namespace. Local installations keep it
    ``None``.
    """

    scope_id: object | None
    brewery_name: Optional[str]
    logo_url: Optional[str]
    theme: str
    primary_color: Optional[str]


@dataclass(frozen=True)
class _TapProjectionData:
    """Related public-safe rows preloaded for the complete tap array."""

    batches: dict
    temperatures: dict
    pressures: dict
    pours: dict


class PublicDisplayService:
    """Build public display documents without exposing ORM objects or identifiers."""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def oss_context(self) -> PublicDisplayContext:
        """Return the local installation's display presentation settings."""
        settings = self.db_session.scalars(
            select(TenantSettings).order_by(TenantSettings.updated_at.desc()).limit(1)
        ).first()
        if settings is None:
            return PublicDisplayContext(
                scope_id=None,
                brewery_name=get_settings().app_name,
                logo_url=None,
                theme="dark",
                primary_color=None,
            )
        return PublicDisplayContext(
            scope_id=None,
            brewery_name=settings.brewery_name,
            logo_url=settings.logo_url,
            theme=settings.theme,
            primary_color=settings.primary_color,
        )

    @staticmethod
    def display_context(context: PublicDisplayContext) -> PublicDisplayContextResponse:
        """Serialize only presentation fields that belong on an anonymous screen."""
        return PublicDisplayContextResponse(
            brewery_name=context.brewery_name,
            logo_url=context.logo_url,
            theme=context.theme,
            primary_color=context.primary_color,
        )

    def build_public_tap_list(self, context: PublicDisplayContext) -> list[PublicTapItem]:
        """Return every live tap, with an optional current keg snapshot per tap."""
        taps = list(
            self.db_session.scalars(
                select(Tap)
                .where(
                    Tap.deleted_at.is_(None),
                    *self._scope_conditions(Tap, context),
                )
                .order_by(Tap.tap_number.nullslast(), Tap.name)
            ).all()
        )
        vessels_by_tap = self._current_kegs_by_tap(
            (tap.id for tap in taps), context
        )
        batches = self._live_batches(
            (vessel.batch_id for vessel in vessels_by_tap.values()), context
        )
        vessel_ids = [
            vessel.id for vessel in vessels_by_tap.values() if vessel.batch_id in batches
        ]
        related = _TapProjectionData(
            batches=batches,
            temperatures=self._latest_temperatures(vessel_ids, context),
            pressures=self._latest_pressures(vessel_ids, context),
            pours=self._latest_pours(vessels_by_tap, context),
        )
        return [
            self._tap_item(
                tap,
                vessels_by_tap.get(tap.id),
                related,
            )
            for tap in taps
        ]

    @staticmethod
    def _tap_item(tap, vessel, related: _TapProjectionData) -> PublicTapItem:
        """Build one tap card while preserving an explicit empty serving state."""
        batch = related.batches.get(vessel.batch_id) if vessel is not None else None
        if vessel is None or batch is None:
            return PublicTapItem(tap_name=tap.name, serving=None)

        temperature = related.temperatures.get(vessel.id)
        pressure = related.pressures.get(vessel.id)
        pour = related.pours.get(vessel.id)
        serving = PublicServing(
            # StorageVessel records only the serving day, not a precise fill
            # instant. Midnight UTC preserves that known date without inventing
            # a device or operator timestamp.
            serving_since=datetime.combine(vessel.fill_date, time.min, tzinfo=UTC),
            total_volume=vessel.total_volume,
            volume_remaining=vessel.volume_remaining,
            volume_poured=max(0.0, vessel.total_volume - vessel.volume_remaining),
            temperature=temperature.temperature if temperature is not None else None,
            temperature_at=temperature.created_at if temperature is not None else None,
            pressure=pressure.pressure if pressure is not None else None,
            pressure_at=pressure.created_at if pressure is not None else None,
            last_pour=(
                PublicLastPour(
                    at=pour.created_at,
                    amount=pour.pour_amount,
                    volume_remaining=pour.volume_remaining,
                )
                if pour is not None
                else None
            ),
        )
        return PublicTapItem(
            tap_name=tap.name,
            beer_name=batch.name,
            style=batch.style,
            abv=batch.abv,
            ibu=batch.ibu,
            ebc=batch.ebc,
            serving=serving,
        )

    def build_public_bottle_list(self, context: PublicDisplayContext) -> list[PublicBottleItem]:
        """Return live, non-empty packaged bottle inventory with a live batch."""
        rows = self.db_session.execute(
            select(StorageVessel, Batch)
            .join(Batch, Batch.id == StorageVessel.batch_id)
            .where(
                StorageVessel.deleted_at.is_(None),
                StorageVessel.vessel_type == "bottles",
                StorageVessel.bottles_remaining.is_not(None),
                StorageVessel.bottles_remaining > 0,
                StorageVessel.bottle_count.is_not(None),
                StorageVessel.bottle_volume.is_not(None),
                Batch.deleted_at.is_(None),
                *self._scope_conditions(StorageVessel, context),
                *self._scope_conditions(Batch, context),
            )
            .order_by(StorageVessel.fill_date.desc(), StorageVessel.name)
        ).all()
        return [
            PublicBottleItem(
                beer_name=batch.name or vessel.name,
                style=batch.style,
                abv=batch.abv,
                ibu=batch.ibu,
                ebc=batch.ebc,
                bottle_volume=vessel.bottle_volume,
                bottles_remaining=vessel.bottles_remaining,
                total_bottle_count=vessel.bottle_count,
            )
            for vessel, batch in rows
        ]

    @staticmethod
    def _scope_conditions(model, context: PublicDisplayContext) -> tuple:
        """Return a generic scope filter when the embedding caller has one."""
        if context.scope_id is None:
            return ()
        return (model.tenant_id == context.scope_id,)

    def _current_kegs_by_tap(
        self, tap_ids: Iterable, context: PublicDisplayContext
    ) -> dict:
        tap_ids = list(tap_ids)
        if not tap_ids:
            return {}
        # StorageVesselService guarantees a single holder per tap.  Ordering
        # makes the projection deterministic even for a legacy database that
        # predates that invariant.
        vessels = self.db_session.scalars(
            select(StorageVessel)
            .where(
                StorageVessel.tap_id.in_(tap_ids),
                StorageVessel.deleted_at.is_(None),
                StorageVessel.vessel_type == "keg",
                *self._scope_conditions(StorageVessel, context),
            )
            .order_by(StorageVessel.updated_at.desc(), StorageVessel.id)
        ).all()
        result = {}
        for vessel in vessels:
            result.setdefault(vessel.tap_id, vessel)
        return result

    def _live_batches(self, batch_ids: Iterable, context: PublicDisplayContext) -> dict:
        batch_ids = [batch_id for batch_id in set(batch_ids) if batch_id is not None]
        if not batch_ids:
            return {}
        batches = self.db_session.scalars(
            select(Batch).where(
                Batch.id.in_(batch_ids),
                Batch.deleted_at.is_(None),
                *self._scope_conditions(Batch, context),
            )
        ).all()
        return {batch.id: batch for batch in batches}

    def _latest_temperatures(
        self, vessel_ids: Iterable, context: PublicDisplayContext
    ) -> dict:
        return self._latest_readings(TempReading, vessel_ids, context)

    def _latest_pressures(
        self, vessel_ids: Iterable, context: PublicDisplayContext
    ) -> dict:
        return self._latest_readings(PressureReading, vessel_ids, context)

    def _latest_readings(self, model, vessel_ids: Iterable, context: PublicDisplayContext) -> dict:
        vessel_ids = list(vessel_ids)
        if not vessel_ids:
            return {}
        rows = self.db_session.scalars(
            select(model)
            .where(
                model.vessel_id.in_(vessel_ids),
                model.deleted_at.is_(None),
                ~model.excluded,
                ~model.is_aggregate,
                *self._scope_conditions(model, context),
            )
            .order_by(model.created_at.desc(), model.id.desc())
        ).all()
        result = {}
        for row in rows:
            result.setdefault(row.vessel_id, row)
        return result

    def _latest_pours(self, vessels_by_tap: dict, context: PublicDisplayContext) -> dict:
        if not vessels_by_tap:
            return {}
        vessel_ids = [vessel.id for vessel in vessels_by_tap.values()]
        tap_by_vessel = {vessel.id: tap_id for tap_id, vessel in vessels_by_tap.items()}
        rows = self.db_session.scalars(
            select(PourEvent)
            .where(
                PourEvent.vessel_id.in_(vessel_ids),
                PourEvent.deleted_at.is_(None),
                ~PourEvent.excluded,
                *self._scope_conditions(PourEvent, context),
            )
            .order_by(PourEvent.created_at.desc(), PourEvent.id.desc())
        ).all()
        result = {}
        for row in rows:
            if row.tap_id == tap_by_vessel[row.vessel_id]:
                result.setdefault(row.vessel_id, row)
        return result
