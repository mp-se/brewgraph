# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tenant extension point — return the active tenant id.

This app is single-tenant: every request resolves to the same constant id.
There is no lookup and no way for this to fail — a self-hosted instance is
always exactly one tenant.
"""
import uuid

# The RFC 4122 nil UUID. A UUID rather than a string because this value is written to
# the tenant_id column, which is Uuid — see docs/architecture.md. It cannot collide with
# a batch/device/etc. row id: those come from uuid4, which never produces the nil UUID.
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def oss_tenant_provider() -> uuid.UUID:
    """Return the constant single-tenant id."""
    return DEFAULT_TENANT_ID
