# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Brewfather API integration endpoints for fetching batch data."""
import logging
import re
from datetime import datetime
from json import JSONDecodeError
from typing import List

import httpx
from fastapi import Depends
from fastapi.routing import APIRouter
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from core.config import get_settings
from core.schemas.errors import NOT_FOUND_RESPONSES
from oss.extensions.auth import oss_auth_provider as api_key_auth

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/brewfather", tags=["brewfather"], dependencies=[Depends(api_key_auth)]
)
_TIMEOUT = httpx.Timeout(15.0, connect=10.0, read=15.0)

MAX_RECORDS = 100


class BrewfatherFermentationStep(BaseModel):
    """A single temperature step in a Brewfather fermentation profile."""

    order: int
    date: str
    temp: float
    days: int
    type: str


class BrewfatherDryHop(BaseModel):
    """A single dry-hop addition parsed from a Brewfather recipe."""

    name: str
    amount: float
    trigger_hours_before: int


class BrewfatherBatch(BaseModel):
    """Brewfather batch summary returned by the integration endpoints."""

    name: str
    brewDate: str
    style: str
    brewer: str
    abv: float
    ebc: float
    ibu: float
    fg: float = 0.0
    og: float = 0.0
    carbonation: float
    volume: float
    yeast_name: str = ""
    yeast_product_id: str = ""
    brewfatherId: str
    fermentationSteps: List[BrewfatherFermentationStep] = []
    dryHops: List[BrewfatherDryHop] = []


def _dry_hop_trigger_hours_before(hop: dict) -> int:
    """Map a Brewfather hop's time/timeUnit to hours-before-completion.

    Brewfather expresses dry-hop timing as ``time`` + ``timeUnit`` (``days`` or
    ``hours``) counted back from the end of fermentation/dry-hopping. Unknown or
    missing units default to 24 hours rather than raising.
    """
    time_value = hop.get("time", 0) or 0
    time_unit = str(hop.get("timeUnit") or "").strip().lower()
    if time_unit == "days":
        return int(time_value * 24)
    if time_unit == "hours":
        return int(time_value)
    return 24


def _parse_dry_hops(recipe: dict) -> List["BrewfatherDryHop"]:
    """Extract dry-hop additions (``use`` containing "dry hop") from a recipe."""
    dry_hops = []
    for hop in recipe.get("hops", []) or []:
        use = str(hop.get("use") or "").strip().lower()
        if "dry hop" not in use:
            continue
        dry_hops.append(BrewfatherDryHop(
            name=hop.get("name", ""),
            amount=hop.get("amount", 0.0),
            trigger_hours_before=_dry_hop_trigger_hours_before(hop),
        ))
    return dry_hops


async def _fetch_batch_list(status: str) -> List[BrewfatherBatch]:  # pylint: disable=too-many-locals
    """Fetch batches from Brewfather API for a given status."""
    settings = get_settings()
    user_key = settings.brewfather_user_key.get_secret_value()
    api_key = settings.brewfather_api_key.get_secret_value()
    if not user_key or not api_key:
        raise HTTPException(
            status_code=424,
            detail="Brewfather keys are not defined, unable to fetch data.",
        )

    batches: List[BrewfatherBatch] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            recipe_fields = (
                "recipe.abv,recipe.color,recipe.ibu,recipe.og,recipe.fg,"
                "recipe.carbonation,recipe.batchSize,recipe.yeast"
            )
            include_fields = (
                f"{recipe_fields},recipe.style.name,recipe.fermentation,recipe.hops"
            )
            res = await client.get(
                url="https://api.brewfather.app/v2/batches",
                params={
                    "include": include_fields,
                    "complete": False,
                    "status": status,
                    "limit": MAX_RECORDS,
                },
                auth=(user_key, api_key),
            )
            batch_list = res.json()

        for batch in batch_list:
            recipe = batch.get("recipe", {})
            name = recipe.get("name") or batch.get("name", "")
            style = recipe.get("style", {}).get("name", "") if "style" in recipe else ""
            abv = recipe.get("abv", 0)
            ebc = recipe.get("color", 0)
            ibu = recipe.get("ibu", 0)
            og = recipe.get("og", 0.0)
            fg = recipe.get("fg", 0.0)
            carbonation = recipe.get("carbonation", 0.0)
            volume = recipe.get("batchSize", 0.0)
            yeast_raw = recipe.get("yeast", [])
            yeast_list = yeast_raw if isinstance(yeast_raw, list) else []
            yeast_name = yeast_list[0].get("name", "") if yeast_list else ""
            yeast_product_id = yeast_list[0].get("productId", "") if yeast_list else ""

            steps = []
            fermentation = recipe.get("fermentation", {})
            for i, step in enumerate(fermentation.get("steps", [])):
                steps.append(BrewfatherFermentationStep(
                    order=i,
                    date="",
                    temp=step.get("stepTemp", 0),
                    days=step.get("stepTime", 0),
                    type=step.get("type", ""),
                ))

            dry_hops = _parse_dry_hops(recipe)

            batches.append(BrewfatherBatch(
                name=name,
                brewDate=datetime.fromtimestamp(batch["brewDate"] / 1000.0).strftime("%Y-%m-%d"),
                style=style,
                brewer=batch.get("brewer", ""),
                abv=abv,
                ebc=ebc,
                ibu=ibu,
                og=og,
                fg=fg,
                carbonation=carbonation,
                volume=volume,
                yeast_name=yeast_name,
                yeast_product_id=yeast_product_id,
                brewfatherId=batch["_id"],
                fermentationSteps=steps,
                dryHops=dry_hops,
            ))

    except JSONDecodeError as exc:
        logger.error("Unable to parse JSON response from Brewfather")
        raise HTTPException(
            status_code=400, detail="Unable to parse JSON from Brewfather."
        ) from exc
    except httpx.TimeoutException as exc:
        logger.error("Brewfather request timed out: %s", type(exc).__name__)
        raise HTTPException(
            status_code=504, detail="Brewfather request timed out."
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Unable to connect to Brewfather: %s", type(exc).__name__)
        raise HTTPException(
            status_code=400, detail="Unable to connect to Brewfather."
        ) from exc

    return batches


@router.get(
    "/batch",
    response_model=List[BrewfatherBatch],
    dependencies=[Depends(api_key_auth)],
)
async def list_brewfather_batches(
    planning: bool = False,
    brewing: bool = False,
    fermenting: bool = False,
    completed: bool = False,
    archived: bool = False,
) -> List[BrewfatherBatch]:
    """Fetch batches from Brewfather filtered by status flags."""
    logger.info(
        "Endpoint GET /api/brewfather/batch/ planning=%s brewing=%s "
        "fermenting=%s completed=%s archived=%s",
        planning, brewing, fermenting, completed, archived,
    )
    batches: List[BrewfatherBatch] = []
    for flag, status in [
        (planning, "Planning"),
        (brewing, "Brewing"),
        (fermenting, "Fermenting"),
        (completed, "Completed"),
        (archived, "Archived"),
    ]:
        if flag:
            batches += await _fetch_batch_list(status)
    return batches


@router.get(
    "/batch/{batch_id}",
    # Deliberately untyped: this returns Brewfather's payload verbatim, not our
    # `BrewfatherBatch` — that model is the *converted* shape the list endpoint emits.
    # Typing it here fails validation on the first field (`brewDate` arrives as an
    # epoch integer), and pinning a schema to a third-party body we do not control
    # would be a claim we cannot keep.
    responses=NOT_FOUND_RESPONSES,
    dependencies=[Depends(api_key_auth)],
)
async def get_brewfather_batch(batch_id: str):
    """Fetch a single batch from Brewfather by its ID."""
    logger.info("Endpoint GET /api/brewfather/batch/%s", batch_id)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", batch_id):
        raise HTTPException(status_code=400, detail="Invalid batch ID")
    settings = get_settings()
    user_key = settings.brewfather_user_key.get_secret_value()
    api_key = settings.brewfather_api_key.get_secret_value()
    if not user_key or not api_key:
        raise HTTPException(
            status_code=424,
            detail="Brewfather keys are not defined, unable to fetch data.",
        )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.get(
                url=f"https://api.brewfather.app/v2/batches/{batch_id}",
                auth=(user_key, api_key),
            )
            return res.json()
    except JSONDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="Unable to parse JSON from Brewfather."
        ) from exc
    except httpx.TimeoutException as exc:
        logger.error("Brewfather request timed out: %s", type(exc).__name__)
        raise HTTPException(
            status_code=504, detail="Brewfather request timed out."
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Unable to connect to Brewfather: %s", type(exc).__name__)
        raise HTTPException(
            status_code=400, detail="Unable to connect to Brewfather."
        ) from exc
