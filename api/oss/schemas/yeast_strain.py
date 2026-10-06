# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Yeast strain library Pydantic schemas.

This module gives the yeast-strain endpoint a `camelCase` response and an OpenAPI
schema, rather than serving the dataset's own snake_case keys straight from disk.
The dataset file itself is community-maintained, and its keys are an input format,
not a contract.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict

from oss.schemas._camel import to_camel


class YeastStrainRead(BaseModel):
    """One strain in the community yeast dataset."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        # Ignore rather than reject unknown keys: the dataset is maintained in a
        # separate repo (../yeast-data) and may add a field before this schema
        # knows about it. Dropping the field is better than 500-ing the endpoint.
        extra="ignore",
    )

    id: str
    product_id: Optional[str] = None
    name: str
    laboratory: Optional[str] = None
    type: Optional[str] = None
    form: Optional[str] = None
    attenuation_min: Optional[float] = None
    attenuation_max: Optional[float] = None
    flocculation: Optional[str] = None
    temp_min_c: Optional[float] = None
    temp_max_c: Optional[float] = None
    alcohol_tolerance: Optional[str] = None
    notes: Optional[str] = None
    best_for: Optional[str] = None
