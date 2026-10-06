# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Daily purge of soft-deleted rows past their configurable grace period.

One general job across every soft-deleted entity, hung off the same cutoff calculation
`oss/extensions/retention.py::oss_retention_provider` wraps for read-time filtering
(`core.middleware.auth.get_retention_cutoff`) — this job feeds it a purge-specific grace
period via a throwaway `AuthContext` rather than the per-request one `oss_retention_provider`
resolves from a caller's auth.

`oss_retention_provider`'s own answer stays `None` ("keep everything") for reads — this job
is the one place this app actually deletes data permanently, on a timer. This app has no
export/archive feature, so once a row crosses the grace window here it is unrecoverable.
The default (`Settings.soft_delete_purge_days`, env `SOFT_DELETE_PURGE_DAYS`) is **7 days**.
It was 1 while nothing could be undone through the API; now that `POST /restore` exists on
batches, notes, devices, taps, vessels and predictions, the window *is* the recovery story,
and 24 hours is short for a brewer who deletes the wrong keg on a Friday. Raise or lower it
to match your own tolerance. `SOFT_DELETE_PURGE_DAYS=-1` disables purging entirely (keep
every soft-deleted row forever), matching the "-1 = unlimited" convention used elsewhere in
this codebase.

Scope: every registered model with a `deleted_at` column
(`core.models.registry.all_models`) — not a hardcoded list, so a future
model that adopts soft delete is covered automatically. A row restored
(`deleted_at` cleared) before the grace window elapses is excluded by the
`deleted_at IS NOT NULL` filter and is never purged, regardless of how long
ago it was originally soft-deleted.
"""
import logging

from sqlalchemy.exc import SQLAlchemyError

from core.config import get_settings
from core.db import create_session
from core.middleware.auth import AuthContext, get_retention_cutoff
from core.models.registry import all_models

logger = logging.getLogger(__name__)

#: Rows a purged parent *owns* — deleted with it, whatever their own `deleted_at` says.
#: A child soft-deleted independently is purged on its own schedule; a child of a purged
#: parent has to go now, because a bulk DELETE bypasses the ORM's `delete-orphan` cascade
#: and the FK would otherwise block the parent (or orphan the child where FKs are off).
_OWNED: dict[str, tuple[tuple[str, str], ...]] = {
    "Batch": (
        ("GravityReading", "batch_id"),
        ("PressureReading", "batch_id"),
        ("TempReading", "batch_id"),
        ("PourEvent", "batch_id"),
        ("Prediction", "batch_id"),
        ("BatchNote", "batch_id"),
        ("BatchDryHop", "batch_id"),
        ("FermentationStep", "batch_id"),
    ),
    "StorageVessel": (
        ("PourEvent", "vessel_id"),
        ("TempReading", "vessel_id"),
        ("PressureReading", "vessel_id"),
        ("Prediction", "vessel_id"),
    ),
    "Device": (
        ("Prediction", "device_id"),
    ),
    "Tap": (
        ("Prediction", "tap_id"),
    ),
}

#: Rows that merely *reference* a purged parent and outlive it. Their FK is nulled first,
#: never deleted — a device is hardware, it survives the batch it was measuring.
_REFERENCES: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "Batch": (
        ("Device", ("batch_id", "batch_role")),
        ("StorageVessel", ("batch_id",)),
    ),
    "StorageVessel": (
        ("Device", ("vessel_id",)),
    ),
    "Tap": (
        ("StorageVessel", ("tap_id",)),
        # Attribution, not ownership -- the pour already survives the vessel's own
        # tap_id being cleared (drain-to-empty); a purged tap must not take the
        # pour's historical record with it.
        ("PourEvent", ("tap_id",)),
    ),
    # Readings and steps outlive the hardware that produced them: they are the batch's
    # record, and `device_id` is provenance. Losing the provenance is right when the
    # device is gone; losing the reading would not be.
    "Device": (
        ("GravityReading", ("device_id",)),
        ("PressureReading", ("device_id",)),
        ("TempReading", ("device_id",)),
        ("FermentationStep", ("device_id",)),
        ("Tap", ("device_id",)),
        ("Batch", ("gravity_device_id",)),
        ("Batch", ("pressure_device_id",)),
        ("Batch", ("temp_device_id",)),
    ),
}

#: Children before parents, so a parent's FK dependents are gone by the time it is deleted.
_PURGE_LAST = ("StorageVessel", "Tap", "Device", "Batch")


def _purge_order():
    """Registered models, dependants first and `_PURGE_LAST` in the order given."""
    models = {m.__name__: m for m in all_models()}
    tail = [models[n] for n in _PURGE_LAST if n in models]
    head = [m for n, m in models.items() if n not in _PURGE_LAST]
    return head + tail


def _release_references(session, parent_name: str, parent_ids: list) -> None:
    """Null out FKs on rows that reference the doomed parents but outlive them."""
    models = {m.__name__: m for m in all_models()}
    for child_name, columns in _REFERENCES.get(parent_name, ()):
        child = models.get(child_name)
        if child is None:
            continue
        fk = columns[0]
        session.query(child).filter(getattr(child, fk).in_(parent_ids)).update(
            {c: None for c in columns}, synchronize_session=False
        )


def _delete_owned(session, parent_name: str, parent_ids: list) -> int:
    """Delete rows owned by the doomed parents. Returns the number removed."""
    models = {m.__name__: m for m in all_models()}
    removed = 0
    for child_name, fk in _OWNED.get(parent_name, ()):
        child = models.get(child_name)
        if child is None:
            continue
        removed += (
            session.query(child)
            .filter(getattr(child, fk).in_(parent_ids))
            .delete(synchronize_session=False)
        )
    return removed


def soft_delete_purge(days: int | None = None) -> None:
    """Hard-delete every soft-deleted row older than the grace period.

    `days` defaults to `Settings.soft_delete_purge_days` when omitted (tests
    pass an explicit value). Logs a per-model count for anything it purges,
    since this is unrecoverable and should be auditable from the logs alone.
    """
    if days is None:
        days = get_settings().soft_delete_purge_days

    cutoff = get_retention_cutoff(AuthContext(retention_days=days))
    if cutoff is None:
        logger.info("Soft-delete purge disabled (soft_delete_purge_days=-1)")
        return

    session = create_session()
    try:
        total = 0
        for model in _purge_order():
            if not hasattr(model, "deleted_at"):
                continue

            doomed = [
                row_id for (row_id,) in session.query(model.id).filter(
                    model.deleted_at.isnot(None), model.deleted_at < cutoff
                )
            ]
            if not doomed:
                continue

            _release_references(session, model.__name__, doomed)
            total += _delete_owned(session, model.__name__, doomed)

            count = (
                session.query(model)
                .filter(model.id.in_(doomed))
                .delete(synchronize_session=False)
            )
            logger.info(
                "Purged %d soft-deleted %s rows older than %d days",
                count, model.__name__, days,
            )
            total += count
        session.commit()
        if total > 0:
            logger.info(
                "Hard-deleted %d soft-deleted records older than %d days (all models)",
                total, days,
            )
    except SQLAlchemyError as e:
        session.rollback()
        logger.error("Failed to hard-delete soft-deleted records: %s", e)
    finally:
        session.remove()
