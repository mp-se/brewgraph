# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
"""Tap liveness: `Tap.last_seen` is stamped on every pour ingest, best-effort."""
# pylint: disable=missing-function-docstring,protected-access
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from oss.services.ingestion import IngestionService


def _make_svc(db=None):
    settings = MagicMock()
    settings.unit_type = "metric"
    return IngestionService(db or MagicMock(), settings)


def _mock_tap(**overrides):
    tap = MagicMock()
    tap.id = uuid.uuid4()
    tap.last_seen = overrides.get("last_seen")
    return tap


def _mock_vessel(**overrides):
    v = MagicMock()
    v.id = uuid.uuid4()
    v.volume_remaining = overrides.get("volume_remaining", 5000.0)
    v.total_volume = overrides.get("total_volume", 5000.0)
    return v


def _assert_stamped_recently(tap, before: datetime):
    assert tap.last_seen is not None
    assert tap.last_seen.tzinfo is not None, "last_seen must be timezone-aware"
    assert tap.last_seen.utcoffset() == timedelta(0), "last_seen must be UTC"
    now = datetime.now(UTC)
    assert before <= tap.last_seen <= now + timedelta(seconds=5)


def test_tap_last_seen_starts_none():
    tap = _mock_tap()
    assert tap.last_seen is None


def test_stamp_tap_last_seen_stamps_and_commits():
    """`stamp_tap_last_seen` alone stamps `tap.last_seen`, independent of any pour."""
    svc = _make_svc()
    tap = _mock_tap()
    before = datetime.now(UTC)

    svc.stamp_tap_last_seen(tap)

    _assert_stamped_recently(tap, before)


def test_pour_stamp_survives_no_active_vessel_failure():
    """Liveness is stamped (via `stamp_tap_last_seen`) and durably committed on its
    own, before `write_pour` is ever called — mirroring the router's call order.
    A tap with no active vessel still leaves the stamp even though the pour
    attribution itself raises."""
    svc = _make_svc()
    tap = _mock_tap()
    svc.find_active_vessel_for_tap = MagicMock(return_value=None)
    before = datetime.now(UTC)

    svc.stamp_tap_last_seen(tap)
    with pytest.raises(ValueError):
        svc.write_pour(tap, {"volume": 100.0})

    _assert_stamped_recently(tap, before)


def test_write_pour_does_not_touch_last_seen():
    """`write_pour` itself must not stamp liveness — that is `stamp_tap_last_seen`'s
    job now, called separately by the router before `write_pour`. A `write_pour`
    call on its own must leave `last_seen` exactly as it found it."""
    svc = _make_svc()
    tap = _mock_tap(last_seen=None)
    vessel = _mock_vessel(volume_remaining=5000.0)
    svc.find_active_vessel_for_tap = MagicMock(return_value=vessel)

    svc.write_pour(tap, {"volume": 4900.0, "maxVolume": 5000.0, "pour": 100.0})

    assert tap.last_seen is None


def test_stamp_tap_last_seen_is_best_effort_and_never_raises():
    """A commit failure while stamping liveness must not propagate — `stamp_tap_last_seen`
    is documented best-effort, so it swallows and logs instead of raising."""
    db = MagicMock()
    db.commit.side_effect = RuntimeError("boom")
    svc = _make_svc(db)
    tap = _mock_tap()

    svc.stamp_tap_last_seen(tap)  # must not raise

    assert tap.last_seen is not None
    db.rollback.assert_called_once()
