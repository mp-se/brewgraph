# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Yeast strain library endpoint — serves the static community dataset."""
import json
import logging
from pathlib import Path
from typing import Any

from fastapi.routing import APIRouter

from oss.schemas.yeast_strain import YeastStrainRead

logger = logging.getLogger(__name__)
# No auth dependency since this is a static public dataset
router = APIRouter(prefix="/api/yeast-strains", tags=["yeast"])

_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "yeast_strains.json"


def _load_strains() -> list[YeastStrainRead]:
    """Read the static dataset from disk, returning an empty list if missing.

    Validated into schema objects once at import rather than per request: the
    dataset is static for the process's lifetime, so the conversion cost is paid
    at startup instead of on every call.
    """
    if not _DATA_PATH.exists():
        logger.warning(
            "yeast_strains.json not found at %s — endpoint will return empty list",
            _DATA_PATH,
        )
        return []
    with open(_DATA_PATH, encoding="utf-8") as f:
        raw: list[dict[str, Any]] = json.load(f)
    strains = [YeastStrainRead.model_validate(s) for s in raw]
    logger.info("Loaded %d yeast strains from %s", len(strains), _DATA_PATH)
    return strains


_strains: list[YeastStrainRead] = _load_strains()


@router.get("", response_model=list[YeastStrainRead])
async def list_yeast_strains():
    """Return all yeast strains in the community dataset."""
    return _strains
