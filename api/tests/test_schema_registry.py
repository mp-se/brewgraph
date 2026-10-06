# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
"""The schema registry must resolve by precedence, never by import order.

Import order is invisible at the call site: a module added above a router's
schema lookup could otherwise swap that router's request and response models
with nothing in the diff to show it.
"""
import pytest
from pydantic import BaseModel

from core.schemas import registry
from core.schemas.registry import (BASE_PRIORITY, OVERRIDE_PRIORITY, get,
                                   register)


class _Base(BaseModel):
    pass


class _Override(BaseModel):
    pass


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Snapshot and restore the process-wide registry around each test."""
    store = getattr(registry, "_registry")
    priorities = getattr(registry, "_priorities")
    entries_before, priorities_before = dict(store), dict(priorities)
    yield
    store.clear()
    store.update(entries_before)
    priorities.clear()
    priorities.update(priorities_before)


def test_override_wins_when_registered_after_base():
    """The easy direction: a higher priority replaces a lower one."""
    register("_Probe", _Base, BASE_PRIORITY)
    register("_Probe", _Override, OVERRIDE_PRIORITY)
    assert get("_Probe") is _Override


def test_override_wins_when_registered_before_base():
    """The case that made resolution order-dependent: a late base import."""
    register("_Probe", _Override, OVERRIDE_PRIORITY)
    register("_Probe", _Base, BASE_PRIORITY)
    assert get("_Probe") is _Override


def test_equal_priority_keeps_last_write_wins():
    """Within one layer, re-importing a module still replaces its own entry."""
    register("_Probe", _Base, BASE_PRIORITY)
    register("_Probe", _Override, BASE_PRIORITY)
    assert get("_Probe") is _Override


def test_default_priority_is_base():
    """An unannotated register() call must not silently outrank an override."""
    register("_Probe", _Override, OVERRIDE_PRIORITY)
    register("_Probe", _Base)
    assert get("_Probe") is _Override


def test_higher_priority_still_replaces_itself():
    """Equal-priority last-write-wins applies at the override level too."""
    register("_Probe", _Base, OVERRIDE_PRIORITY)
    register("_Probe", _Override, OVERRIDE_PRIORITY)
    assert get("_Probe") is _Override


def test_register_still_rejects_non_classes():
    """The priority argument must not weaken the existing type guard."""
    with pytest.raises(TypeError):
        register("_Probe", object(), OVERRIDE_PRIORITY)


def test_unknown_name_raises():
    """An unregistered name still fails loudly rather than returning None."""
    with pytest.raises(RuntimeError):
        get("_NeverRegistered")
