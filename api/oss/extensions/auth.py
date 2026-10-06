# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Auth extension point — resolve caller identity, or reject.

Default: a single shared API key, compared in constant time, with per-IP
failure blocking. That logic already lives in ``core.middleware.auth`` and is
exercised by every router today; this module does not duplicate it, it wraps
it as a dependency so the substitution point has the same shape as
tenant/quota/retention/throttle and is overridable in isolation.
"""
from fastapi import Depends

from core.middleware.auth import AuthContext, api_key_auth
from oss.extensions.quota import QUOTA_RESOURCES, oss_quota_provider


def oss_auth_provider(
    auth: AuthContext = Depends(api_key_auth),
    quota_limit=Depends(oss_quota_provider),
) -> AuthContext:
    """Resolve caller identity via the shared API key.

    Keeps the OSS shared-key authentication mechanism, while making the policy
    boundary used by every protected OSS router independently overridable.  The
    quota provider is folded into an otherwise-unlimited OSS context here, so an
    override applies to real create routes rather than only to a test app.
    """
    if auth.quota_limits:
        return auth
    return AuthContext(
        retention_days=auth.retention_days,
        ingest_interval_seconds=auth.ingest_interval_seconds,
        quota_limits={resource: quota_limit(resource) for resource in QUOTA_RESOURCES},
    )
