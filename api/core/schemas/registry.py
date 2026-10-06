# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
"""Schema registry — lets alternative builds substitute Pydantic schemas before routers load.

Registration is **precedence-ordered, not order-of-import-ordered**.  Each entry
carries a ``priority``; a registration only takes effect if its priority is at
least as high as the one already held for that name.  Builds that layer their
own schemas over the base set register at a higher priority and therefore win
regardless of which module happened to be imported first.

Without this, resolution depended on import order — and import order is
invisible at the call site, so adding one import above a router's schema lookup
could silently swap that router's request and response models.
"""
import inspect

BASE_PRIORITY = 0
"""Priority used by the schemas shipped in this package."""

OVERRIDE_PRIORITY = 100
"""Priority for a layer that deliberately supersedes the base schemas."""

_registry: dict = {}
_priorities: dict[str, int] = {}


def register(name: str, cls, priority: int = BASE_PRIORITY) -> None:
    """Register a schema class under the given name.

    A registration at a *lower* priority than the incumbent is ignored, so a
    late base-priority import cannot clobber a higher-priority override.  Equal
    priorities keep last-write-wins, which is what re-importing a module within
    one layer expects.
    """
    if not inspect.isclass(cls):
        raise TypeError(f"register() expects a class, got {type(cls)!r} for '{name}'")
    if name in _priorities and priority < _priorities[name]:
        return
    _registry[name] = cls
    _priorities[name] = priority


def get(name: str):
    """Return the registered schema class for the given name.

    Raises RuntimeError if the name has not been registered, which indicates
    the schema file was not imported before the router that needs it.
    """
    if name not in _registry:
        raise RuntimeError(
            f"Schema '{name}' is not registered. "
            f"Ensure the schema module is imported before any router that uses it. "
            f"Registered schemas: {sorted(_registry)}"
        )
    return _registry[name]
