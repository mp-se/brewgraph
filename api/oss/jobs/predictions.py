# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Background job: run ML fermentation predictions for all fermenting batches."""
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from core.db import create_session
from core.enums import BatchStatus, PredictionOutcome, PredictionType
from core.log import LogLevel, system_log
from core.ml.fermentation_completion_predictor import \
    FermentationCompletionPredictor
from core.models.registry import resolve_model

Prediction = resolve_model("Prediction")
_Batch = resolve_model("Batch")
_GravityReading = resolve_model("GravityReading")

logger = logging.getLogger(__name__)

# Module-level singleton — loaded once at scheduler start
_PREDICTOR: FermentationCompletionPredictor | None = None  # pylint: disable=invalid-name


def _get_predictor() -> FermentationCompletionPredictor:
    global _PREDICTOR  # pylint: disable=global-statement
    if _PREDICTOR is None:
        _PREDICTOR = FermentationCompletionPredictor()
    return _PREDICTOR


def _hours_left_to_outcome(hours_left: float | None) -> PredictionOutcome:
    if hours_left is None:
        return PredictionOutcome.FERMENTING
    if hours_left <= 0.5:
        return PredictionOutcome.COMPLETE
    if hours_left <= 2.0:
        return PredictionOutcome.DONE_SOON
    if hours_left <= 24.0:
        return PredictionOutcome.NEAR_DONE
    return PredictionOutcome.FERMENTING



async def task_update_predictions() -> None:
    """Run the ML model against all fermenting batches and persist predictions."""
    db = create_session()
    try:
        fermenting = list(db.scalars(
            select(_Batch).where(
                _Batch.accept_ingest,
                _Batch.status == BatchStatus.FERMENTING.value,
                _Batch.deleted_at.is_(None),
            )
        ).all())
        if not fermenting:
            return

        logger.info("task_update_predictions: running for %d batches", len(fermenting))

        for batch in fermenting:
            try:
                readings = list(db.scalars(
                    select(_GravityReading)
                    .where(_GravityReading.batch_id == batch.id)
                    .order_by(_GravityReading.created_at.asc())
                ).all())
                if len(readings) < 2:
                    continue

                usable_readings = [
                    reading for reading in readings
                    if reading.gravity is not None and not reading.excluded
                ]
                if len(usable_readings) < 2:
                    continue

                history = [
                    (reading.created_at, reading.gravity, reading.temperature)
                    for reading in usable_readings
                ]
                latest = usable_readings[-1]
                first = usable_readings[0]
                hours_elapsed = (
                    latest.created_at - first.created_at
                ).total_seconds() / 3600

                if batch.og is None or batch.fg is None:
                    logger.debug(
                        "Skipping prediction for batch %s: og=%s fg=%s",
                        batch.id, batch.og, batch.fg,
                    )
                    continue

                existing = db.scalars(
                    select(Prediction)
                    .where(
                        Prediction.batch_id == batch.id,
                        Prediction.prediction_type
                        == PredictionType.FERMENTATION_PROGRESS.value,
                        Prediction.deleted_at.is_(None),
                    )
                    .order_by(Prediction.created_at.desc())
                    .limit(1)
                ).first()
                source = {
                    "sourceReadingId": str(latest.id),
                    "sourceReadingAt": latest.created_at.isoformat(),
                }
                if (
                    existing is not None
                    and isinstance(existing.details, dict)
                    and existing.details.get("sourceReadingId") == source["sourceReadingId"]
                ):
                    continue

                predictor = _get_predictor()
                hours_left = predictor.predict(
                    history=history,
                    current_gravity=latest.gravity,
                    current_temp=latest.temperature or 20.0,
                    start_gravity=batch.og,
                    plateau_gravity=batch.fg,
                    hours_elapsed=hours_elapsed,
                )
                outcome = _hours_left_to_outcome(hours_left)
                if existing is None:
                    existing = Prediction(
                        batch_id=batch.id,
                        prediction_type=PredictionType.FERMENTATION_PROGRESS.value,
                    )
                    db.add(existing)
                existing.outcome = outcome.value
                existing.hours_left = hours_left
                existing.details = source
                existing.created_at = datetime.now(UTC)
                db.commit()
                logger.debug(
                    "Prediction for batch %s: %s, %.1fh left",
                    batch.id, outcome.value, hours_left or 0,
                )

            except Exception as exc:  # pylint: disable=broad-exception-caught
                db.rollback()
                logger.error("Prediction failed for batch %s: %s", batch.id, exc)
                system_log(
                    "prediction_model_error",
                    f"ML prediction failed for batch {batch.id}: {exc}",
                    level=LogLevel.ERROR,
                )

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("task_update_predictions failed: %s", exc)
        system_log("scheduler_task_failed", f"task_update_predictions: {exc}", level=LogLevel.ERROR)
    finally:
        db.remove()


# This job predicts fermentation progress only.
#
# Not battery or WiFi signal prediction (hours-until-cutoff, dBm-drop bucketing) —
# nothing in this project calls that. A helper that is defined and unit-tested but
# wired to no scheduler job passes CI while doing nothing — the kind of dead code
# that later gets mistaken for a working feature.
#
# The voltage→SoC conversion they used stays in oss/battery.py, which is a neutral
# utility: anything reading the `battery` column can want a state of charge.
#
# If battery or connectivity prediction is wanted here, wire it to the scheduler
# in the same change. Re-adding unreferenced helpers just recreates the situation.
