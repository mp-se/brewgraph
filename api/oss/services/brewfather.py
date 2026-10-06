# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Brewfather API integration service."""
import json
import logging
from datetime import datetime
from json import JSONDecodeError
from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx
from starlette.exceptions import HTTPException

from core.config import get_settings

if TYPE_CHECKING:
    from core.models.platform import TenantSettings
logger = logging.getLogger(__name__)

MAX_RECORDS = 100


class BrewfatherService:
    """Interact with the Brewfather API on behalf of a user."""

    def __init__(self, settings: "TenantSettings"):
        self._settings = settings

    def _check_credentials(self) -> None:
        if not self._settings.brewfather_user_key or not self._settings.brewfather_api_key:
            raise HTTPException(
                status_code=424,
                detail="Brewfather keys are not defined, unable to fetch data.",
            )

    @property
    def _auth(self):
        cfg = get_settings()
        return (
            cfg.brewfather_user_key.get_secret_value(),
            cfg.brewfather_api_key.get_secret_value(),
        )

    @staticmethod
    def _batch_to_response(batch: dict) -> dict:
        """Transform a Brewfather batch payload into API response shape."""
        recipe = batch.get("recipe", {}) or {}
        style_obj = recipe.get("style", {}) or {}
        fermentation = recipe.get("fermentation", {}) or {}
        steps = fermentation.get("steps", []) or []

        name = recipe.get("name") or batch.get("name", "")
        brew_date = ""
        if batch.get("brewDate"):
            brew_date = datetime.fromtimestamp(batch["brewDate"] / 1000.0).strftime(
                "%Y-%m-%d"
            )

        fermentation_steps = [
            {
                "order": i,
                "date": "",
                "temp": step.get("stepTemp", 0),
                "days": step.get("stepTime", 0),
                "type": step.get("type", ""),
            }
            for i, step in enumerate(steps)
        ]

        return {
            "name": name,
            "brewDate": brew_date,
            "style": style_obj.get("name", ""),
            "brewer": batch.get("brewer", ""),
            "abv": recipe.get("abv", 0),
            "ebc": recipe.get("color", 0),
            "ibu": recipe.get("ibu", 0),
            "fg": recipe.get("fg", 0.0),
            "og": recipe.get("og", 0.0),
            "carbonation": recipe.get("carbonation", 0.0),
            "brewfatherId": batch.get("_id", ""),
            "fermentationSteps": json.dumps(fermentation_steps),
        }

    async def fetch_batch_list(self, status: str) -> list:
        """Fetch batch list from Brewfather API for a given status."""
        self._check_credentials()

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                url = "https://api.brewfather.app/v2/batches"
                recipe_fields = (
                    "recipe.abv,recipe.color,recipe.ibu,recipe.og,recipe.fg,recipe.carbonation"
                )
                include_fields = f"{recipe_fields},recipe.style.name,recipe.fermentation"
                params = {
                    "include": include_fields,
                    "complete": False,
                    "status": status,
                    "limit": MAX_RECORDS,
                }
                res = await client.get(url=url, params=params, auth=self._auth)
                batch_list = res.json()

                batches = []
                for batch in batch_list:
                    logger.info("Processing Brewfather batch #%s", batch.get("batchNo"))
                    batches.append(self._batch_to_response(batch))

        except JSONDecodeError as exc:
            logger.error("Unable to parse JSON response from Brewfather")
            raise HTTPException(
                status_code=400, detail="Unable to parse JSON from brewfather."
            ) from exc
        except httpx.ConnectError as exc:
            logger.error("Unable to connect to Brewfather")
            raise HTTPException(
                status_code=400, detail="Unable to connect to brewfather."
            ) from exc

        return batches

    async def fetch_batch(self, batch_id: str) -> dict:
        """Fetch a single batch from Brewfather by its batch ID."""
        self._check_credentials()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                url = f"https://api.brewfather.app/v2/batches/{quote(batch_id, safe='')}"
                res = await client.get(url=url, auth=self._auth)
                return res.json()
        except JSONDecodeError as exc:
            raise HTTPException(
                status_code=400, detail="Unable to parse JSON from brewfather."
            ) from exc
        except httpx.ConnectError as exc:
            raise HTTPException(
                status_code=400, detail="Unable to connect to brewfather."
            ) from exc
