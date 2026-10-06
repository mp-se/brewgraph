# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Retention extension point — return the cutoff before which data is purged.

Default: ``None`` — keep everything. That logic already lives in
``core.middleware.auth.get_retention_cutoff``; this module wraps it as a
dependency with the same shape as the other extension points.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends

from core.middleware.auth import AuthContext
from oss.extensions.auth import oss_auth_provider


def oss_retention_provider(
    auth: AuthContext = Depends(oss_auth_provider),
) -> Optional[datetime]:
    """Return the retention cutoff for the current caller (None = keep everything)."""
    if auth.retention_days == -1:
        return None
    return datetime.now(timezone.utc) - timedelta(days=auth.retention_days)
