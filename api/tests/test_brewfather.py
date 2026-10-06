# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

# pylint: disable=duplicate-code

"""Tests for Brewfather service integration."""
from json import JSONDecodeError
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import SecretStr
from starlette.exceptions import HTTPException

from oss.services.brewfather import BrewfatherService


def _mock_settings(user_key="user", api_key="key"):
    s = MagicMock()
    s.brewfather_user_key = SecretStr(user_key)
    s.brewfather_api_key = SecretStr(api_key)
    return s


@pytest.mark.asyncio
async def test_fetch_batch_list_missing_user_key():
    """Raises 424 when user key is missing."""
    with patch("oss.services.brewfather.get_settings") as mock_cfg:
        mock_cfg.return_value = MagicMock(
            brewfather_user_key=SecretStr(""),
            brewfather_api_key=SecretStr("key"),
        )
        svc = BrewfatherService(_mock_settings(user_key=""))
        with pytest.raises(HTTPException) as exc_info:
            await svc.fetch_batch_list("Fermenting")
        assert exc_info.value.status_code == 424


@pytest.mark.asyncio
async def test_fetch_batch_list_missing_api_key():
    """Raises 424 when API key is missing."""
    with patch("oss.services.brewfather.get_settings") as mock_cfg:
        mock_cfg.return_value = MagicMock(
            brewfather_user_key=SecretStr("user"),
            brewfather_api_key=SecretStr(""),
        )
        svc = BrewfatherService(_mock_settings(api_key=""))
        with pytest.raises(HTTPException) as exc_info:
            await svc.fetch_batch_list("Planning")
        assert exc_info.value.status_code == 424


@pytest.mark.asyncio
async def test_fetch_batch_list_connect_error():
    """Raises 400 when unable to connect."""
    with patch("oss.services.brewfather.get_settings") as mock_cfg, \
         patch("oss.services.brewfather.httpx.AsyncClient") as mock_client_class:
        mock_cfg.return_value = MagicMock(
            brewfather_user_key=SecretStr("user"),
            brewfather_api_key=SecretStr("key"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("conn failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        svc = BrewfatherService(_mock_settings())
        with pytest.raises(HTTPException) as exc_info:
            await svc.fetch_batch_list("Fermenting")
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_fetch_batch_list_success():
    """Returns parsed batch list on success."""
    fake_batch = {
        "_id": "abc123",
        "batchNo": 42,
        "name": "My Lager",
        "brewer": "Magnus",
        "brewDate": 1700000000000,
        "status": "Fermenting",
        "recipe": {
            "abv": 5.5,
            "color": 20.0,
            "ibu": 35.0,
            "og": 1.055,
            "fg": 1.012,
            "carbonation": 2.4,
            "style": {"name": "Pilsner"},
            "fermentation": {
                "steps": [
                    {"stepTemp": 12, "stepTime": 14, "type": "Primary"},
                ]
            },
        },
    }

    with patch("oss.services.brewfather.get_settings") as mock_cfg, \
         patch("oss.services.brewfather.httpx.AsyncClient") as mock_client_class:
        mock_cfg.return_value = MagicMock(
            brewfather_user_key=SecretStr("user"),
            brewfather_api_key=SecretStr("key"),
        )
        mock_response = MagicMock()
        mock_response.json.return_value = [fake_batch]

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        svc = BrewfatherService(_mock_settings())
        result = await svc.fetch_batch_list("Fermenting")

    assert len(result) == 1
    batch = result[0]
    assert batch["brewfatherId"] == "abc123"
    assert batch["abv"] == 5.5
    assert batch["style"] == "Pilsner"
    assert batch["brewer"] == "Magnus"
    assert batch["carbonation"] == 2.4


@pytest.mark.asyncio
async def test_fetch_batch_list_json_decode_error():
    """Raises 400 when Brewfather returns unparseable JSON."""
    with patch("oss.services.brewfather.get_settings") as mock_cfg, \
         patch("oss.services.brewfather.httpx.AsyncClient") as mock_client_class:
        mock_cfg.return_value = MagicMock(
            brewfather_user_key=SecretStr("user"),
            brewfather_api_key=SecretStr("key"),
        )
        mock_response = MagicMock()
        mock_response.json.side_effect = JSONDecodeError("", "", 0)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        svc = BrewfatherService(_mock_settings())
        with pytest.raises(HTTPException) as exc_info:
            await svc.fetch_batch_list("Fermenting")
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_fetch_batch_json_decode_error():
    """fetch_batch raises 400 on JSON decode failure."""
    with patch("oss.services.brewfather.get_settings") as mock_cfg, \
         patch("oss.services.brewfather.httpx.AsyncClient") as mock_client_class:
        mock_cfg.return_value = MagicMock(
            brewfather_user_key=SecretStr("user"),
            brewfather_api_key=SecretStr("key"),
        )
        mock_response = MagicMock()
        mock_response.json.side_effect = JSONDecodeError("", "", 0)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        svc = BrewfatherService(_mock_settings())
        with pytest.raises(HTTPException) as exc_info:
            await svc.fetch_batch("batch123")
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_fetch_batch_connect_error():
    """fetch_batch raises 400 on connection failure."""
    with patch("oss.services.brewfather.get_settings") as mock_cfg, \
         patch("oss.services.brewfather.httpx.AsyncClient") as mock_client_class:
        mock_cfg.return_value = MagicMock(
            brewfather_user_key=SecretStr("user"),
            brewfather_api_key=SecretStr("key"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("no route"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        svc = BrewfatherService(_mock_settings())
        with pytest.raises(HTTPException) as exc_info:
            await svc.fetch_batch("batch456")
        assert exc_info.value.status_code == 400
