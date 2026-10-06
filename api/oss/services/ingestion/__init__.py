# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Ingestion service — processes raw device payloads into the database."""
from ._chamber import _ChamberIngestionMixin
from ._core import _IngestionCoreMixin
from ._gravity import _GravityIngestionMixin
from ._pour import _PourIngestionMixin
from ._pressure import _PressureIngestionMixin
from ._utils import _safe_float

__all__ = ["IngestionService", "_safe_float"]


class IngestionService(
    _IngestionCoreMixin,
    _GravityIngestionMixin,
    _PressureIngestionMixin,
    _PourIngestionMixin,
    _ChamberIngestionMixin,
):
    """Orchestrates device lookup, batch lookup/creation, and reading persistence.

    Composed from use-case-scoped mixins (oss/services/ingestion/_*.py) rather than
    one large class body: `_core` holds construction, transaction helpers, device/batch
    resolution, and error logging — shared across every use case below; `_gravity`,
    `_pressure`, `_pour`, and `_chamber` each hold their own use case's read/write path.
    This is an internal reorganization of this class's body only — no public method name
    or signature changed, so a subclass overriding one of these methods and calling
    `super()` is unaffected.
    """
