# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
"""Core schema utilities — camelCase alias generator and schema registry."""
from core.schemas.camel import to_camel
from core.schemas.registry import get, register

__all__ = ("to_camel", "register", "get")
