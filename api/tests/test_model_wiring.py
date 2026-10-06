# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

# pylint: disable=too-few-public-methods
"""Tests for Change 1-3: create_tables(), model registry guard, model wiring."""
import pytest

from core.models.registry import register_model, resolve_model

OSS_MODEL_NAMES = [
    "Batch",
    "Device",
    "GravityReading",
    "PourEvent",
    "Prediction",
    "PressureReading",
    "StorageVessel",
    "Tap",
    "TenantSettings",
]


# ---------------------------------------------------------------------------
# Change 1 — create_tables() is an explicit callable
# ---------------------------------------------------------------------------

def test_create_tables_is_callable():
    """create_tables export from core.db must be a callable."""
    from core.db import \
        create_tables  # pylint: disable=import-outside-toplevel
    assert callable(create_tables)


def test_create_tables_runs_without_error():
    """Calling create_tables on an existing schema is idempotent and safe."""
    from core.db import \
        create_tables  # pylint: disable=import-outside-toplevel

    # Idempotent: calling it again on an already-created schema is safe.
    create_tables()


# ---------------------------------------------------------------------------
# Change 2 — registry guard pattern
# ---------------------------------------------------------------------------

def test_registry_get_raises_for_unknown_name():
    """resolve_model() raises RuntimeError for a name that was never registered."""
    with pytest.raises(RuntimeError, match="not registered"):
        resolve_model("__NonExistentModel__")


def test_registry_register_and_get_round_trip():
    """Registered class is returned unchanged by resolve_model()."""
    class _Sentinel:
        pass

    register_model("__Sentinel__", _Sentinel)
    assert resolve_model("__Sentinel__") is _Sentinel


def test_guard_pattern_prefers_already_registered_class():
    """Simulate the try/except guard: if a name is already registered the
    except branch is skipped and the pre-registered class is returned."""
    class _PreRegistered:
        pass

    class _OssVersion:
        pass

    register_model("__GuardTest__", _PreRegistered)

    # This is what the model file now does:
    try:
        result = resolve_model("__GuardTest__")
    except RuntimeError:
        result = _OssVersion
        register_model("__GuardTest__", _OssVersion)

    assert result is _PreRegistered, "Guard must keep the pre-registered class"


def test_guard_pattern_falls_through_when_not_registered():
    """If the name is absent the except branch runs and registers the fallback class."""
    class _OssVersion:
        pass

    try:
        result = resolve_model("__GuardFallthrough__")
    except RuntimeError:
        result = _OssVersion
        register_model("__GuardFallthrough__", _OssVersion)

    assert result is _OssVersion
    assert resolve_model("__GuardFallthrough__") is _OssVersion


# ---------------------------------------------------------------------------
# Change 3 — all model names populated before create_tables()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", OSS_MODEL_NAMES)
def test_oss_model_registered(name):
    """Every model must be in the registry after main_oss imports load."""
    cls = resolve_model(name)
    assert cls is not None
    assert isinstance(cls, type)
