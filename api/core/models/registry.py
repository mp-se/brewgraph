# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Model registry — allows alternative builds to substitute ORM models before routers load."""
import inspect

_registry: dict = {}


def register_model(name: str, cls) -> None:
    """Register a model class under the given name."""
    if not inspect.isclass(cls):
        raise TypeError(f"register_model() expects a class, got {type(cls)!r} for '{name}'")
    _registry[name] = cls


def resolve_model(name: str):
    """Return the registered model class for the given name."""
    if name not in _registry:
        raise RuntimeError(
            f"Model '{name}' is not registered. "
            f"Ensure it is registered before importing services. "
            f"Registered models: {sorted(_registry)}"
        )
    return _registry[name]


def all_models() -> list:
    """Return every currently-registered model class, deduplicated.

    Used by generic maintenance jobs (e.g. oss/jobs/scheduler.py's
    soft-delete purge) that must act on "every model with property X"
    without hardcoding a model list that drifts as new soft-deletable
    models are added.
    """
    return list(dict.fromkeys(_registry.values()))
