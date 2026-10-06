# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Registries — sets of values a product contributes at import time.

Unlike the providers in ``oss/extensions/`` (a contract one implementation
replaces via ``app.dependency_overrides``), a registry is additive: each
product populates it with the entries it supports, and validation checks
membership in whatever is registered. This module registers only its own
entries here and never imports or names anything beyond that.
"""
