# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
"""Shared camelCase alias generator for Pydantic schemas."""
from core.utils import to_camel  # noqa: F401 — re-export from utils

__all__ = ("to_camel",)
