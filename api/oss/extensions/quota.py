# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Quota extension point — given a resource name, return its numeric limit.

Resources: batches, devices, taps, vessels. ``-1`` means unlimited and is the
default answer for every resource — a self-hosted instance has one operator, so
there is nothing to limit.

This is the same contract ``AuthContext.quota_limit`` answers: the caller asks
for a resource by name and gets a number back, rather than a parallel
per-resource ``AuthContext.max_*`` field — one lookup, consulted from one
place.

The *check* deliberately does not live here. Deciding whether a limit is reached
needs a live count from the database, which is the service layer's business;
this provider only answers what the limit is.
"""
from typing import Callable

# The four things this application creates and a deployment might want to bound.
# The tuple is not a closed vocabulary: the provider answers -1 for any name,
# so a deployment that limits something else needs no change here.
QUOTA_RESOURCES = ("batches", "devices", "taps", "vessels")

UNLIMITED = -1


def oss_quota_provider() -> Callable[[str], int]:
    """Return a resource-name -> limit lookup. Default: unlimited for every resource."""
    def _limit(_resource: str) -> int:
        return UNLIMITED
    return _limit
