# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Throttle extension point — return the rate limit(s) for the current caller.

Two independent layers exist conceptually: a pre-auth per-IP guard (resource
protection against a misbehaving device, not a security control — the
smallest self-hosted deployments have the least headroom) and a per-device
throttle enforcing sane reading intervals once a device/tap is resolved. This
provider returns fixed, permissive values for both — every caller gets the same
limits. ``core.middleware.auth.ingest_auth`` already enforces the pre-auth
guard at ``120`` requests/minute — this provider is the explicit contract
carrying that number, not a second implementation of it.

This provider is wired into ``core.middleware.auth.ingest_auth``, which takes
it as a FastAPI dependency and uses ``pre_auth_per_minute`` for the pre-auth
guard and ``per_device_min_interval_seconds`` to populate the returned
``AuthContext.ingest_interval_seconds``, which the router's per-device
``_check_throttle`` then reads.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ThrottleLimits:
    """Rate limits for one caller. Fixed, identical for every caller."""

    pre_auth_per_minute: int = 120
    per_device_min_interval_seconds: int = 0  # 0 = no enforced minimum interval


def oss_throttle_provider() -> ThrottleLimits:
    """Return the fixed throttle limits."""
    return ThrottleLimits()
