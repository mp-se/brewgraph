# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for core/routers/brewfather.py — Brewfather API proxy endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from pydantic import SecretStr

from core.config import get_settings

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

_NO_KEY_SETTINGS = {
    "brewfather_user_key": SecretStr(""),
    "brewfather_api_key": SecretStr(""),
}


def _mock_settings(user_key="user", api_key="key"):
    s = MagicMock()
    s.brewfather_user_key = SecretStr(user_key)
    s.brewfather_api_key = SecretStr(api_key)
    return s


def _fake_batch():
    return {
        "_id": "abc123",
        "name": "Test Lager",
        "brewer": "Magnus",
        "brewDate": 1700000000000,
        "recipe": {
            "name": "Test Lager",
            "abv": 5.0,
            "color": 10.0,
            "ibu": 25.0,
            "og": 1.050,
            "fg": 1.010,
            "carbonation": 2.3,
            "style": {"name": "Pilsner"},
            "fermentation": {"steps": [{"stepTemp": 12, "stepTime": 14, "type": "Primary"}]},
        },
    }


def _fake_batch_with_hops(hops):
    batch = _fake_batch()
    batch["recipe"]["hops"] = hops
    return batch


def _async_client_mock(response_data, side_effect=None):
    mock_response = MagicMock()
    mock_response.json.return_value = response_data

    mock_client = AsyncMock()
    if side_effect:
        mock_client.get = AsyncMock(side_effect=side_effect)
    else:
        mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


# ---------------------------------------------------------------------------
# GET /brewfather/batch/
# ---------------------------------------------------------------------------

def test_list_no_flags_returns_empty(app_client):
    """GET with no status flags returns empty list without calling Brewfather."""
    r = app_client.get("/brewfather/batch", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


def test_list_missing_api_keys_returns_424(app_client):
    """GET returns 424 when Brewfather keys are not configured."""
    with patch("oss.routers.brewfather.get_settings") as mock_cfg:
        mock_cfg.return_value = MagicMock(
            brewfather_user_key=SecretStr(""),
            brewfather_api_key=SecretStr("key"),
        )
        r = app_client.get("/brewfather/batch/?fermenting=true", headers=headers)
    assert r.status_code == 424


def test_list_connect_error_returns_400(app_client):
    """GET returns 400 when Brewfather is unreachable."""
    with patch("oss.routers.brewfather.get_settings") as mock_cfg, \
         patch("oss.routers.brewfather.httpx.AsyncClient") as mock_cls:
        mock_cfg.return_value = _mock_settings()
        mock_cls.return_value = _async_client_mock(None, side_effect=httpx.ConnectError(""))
        r = app_client.get("/brewfather/batch/?fermenting=true", headers=headers)
    assert r.status_code == 400


def test_list_success_returns_batches(app_client):
    """GET returns parsed batch list on success."""
    with patch("oss.routers.brewfather.get_settings") as mock_cfg, \
         patch("oss.routers.brewfather.httpx.AsyncClient") as mock_cls:
        mock_cfg.return_value = _mock_settings()
        mock_cls.return_value = _async_client_mock([_fake_batch()])
        r = app_client.get("/brewfather/batch/?fermenting=true", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["brewfatherId"] == "abc123"
    assert data[0]["style"] == "Pilsner"


def test_list_multiple_flags_aggregates(app_client):
    """Setting multiple flags fetches from multiple statuses and combines results."""
    with patch("oss.routers.brewfather.get_settings") as mock_cfg, \
         patch("oss.routers.brewfather.httpx.AsyncClient") as mock_cls:
        mock_cfg.return_value = _mock_settings()
        mock_cls.return_value = _async_client_mock([_fake_batch()])
        r = app_client.get(
            "/brewfather/batch/?fermenting=true&completed=true", headers=headers
        )
    assert r.status_code == 200
    assert len(r.json()) == 2  # one per status flag


# ---------------------------------------------------------------------------
# Dry-hop parsing in GET /brewfather/batch/
# ---------------------------------------------------------------------------

def test_list_dry_hop_days_converted_to_hours(app_client):
    """A dry-hop entry with timeUnit=days is converted to hours (time * 24)."""
    hops = [{"name": "Galaxy", "use": "Dry Hop", "time": 4, "timeUnit": "days", "amount": 60}]
    with patch("oss.routers.brewfather.get_settings") as mock_cfg, \
         patch("oss.routers.brewfather.httpx.AsyncClient") as mock_cls:
        mock_cfg.return_value = _mock_settings()
        mock_cls.return_value = _async_client_mock([_fake_batch_with_hops(hops)])
        r = app_client.get("/brewfather/batch/?fermenting=true", headers=headers)
    assert r.status_code == 200
    dry_hops = r.json()[0]["dryHops"]
    assert len(dry_hops) == 1
    assert dry_hops[0]["name"] == "Galaxy"
    assert dry_hops[0]["amount"] == 60
    assert dry_hops[0]["trigger_hours_before"] == 96


def test_list_dry_hop_hours_passthrough(app_client):
    """A dry-hop entry with timeUnit=hours is passed through unchanged."""
    hops = [{"name": "Citra", "use": "Dry Hop", "time": 48, "timeUnit": "hours", "amount": 30}]
    with patch("oss.routers.brewfather.get_settings") as mock_cfg, \
         patch("oss.routers.brewfather.httpx.AsyncClient") as mock_cls:
        mock_cfg.return_value = _mock_settings()
        mock_cls.return_value = _async_client_mock([_fake_batch_with_hops(hops)])
        r = app_client.get("/brewfather/batch/?fermenting=true", headers=headers)
    dry_hops = r.json()[0]["dryHops"]
    assert dry_hops[0]["trigger_hours_before"] == 48


def test_list_dry_hop_missing_time_unit_defaults_to_24(app_client):
    """A dry-hop entry with a missing/unrecognized timeUnit defaults to 24 hours."""
    hops = [{"name": "Mosaic", "use": "Dry Hop", "time": 3, "amount": 40}]
    with patch("oss.routers.brewfather.get_settings") as mock_cfg, \
         patch("oss.routers.brewfather.httpx.AsyncClient") as mock_cls:
        mock_cfg.return_value = _mock_settings()
        mock_cls.return_value = _async_client_mock([_fake_batch_with_hops(hops)])
        r = app_client.get("/brewfather/batch/?fermenting=true", headers=headers)
    dry_hops = r.json()[0]["dryHops"]
    assert dry_hops[0]["trigger_hours_before"] == 24


def test_list_non_dry_hop_use_excluded(app_client):
    """Hops with use values other than 'Dry Hop' (Boil, Aroma) are excluded."""
    hops = [
        {"name": "Warrior", "use": "Boil", "time": 60, "timeUnit": "minutes", "amount": 20},
        {"name": "Galaxy", "use": "Aroma", "time": 10, "timeUnit": "minutes", "amount": 25},
        {"name": "Citra", "use": "Dry Hop", "time": 2, "timeUnit": "days", "amount": 50},
    ]
    with patch("oss.routers.brewfather.get_settings") as mock_cfg, \
         patch("oss.routers.brewfather.httpx.AsyncClient") as mock_cls:
        mock_cfg.return_value = _mock_settings()
        mock_cls.return_value = _async_client_mock([_fake_batch_with_hops(hops)])
        r = app_client.get("/brewfather/batch/?fermenting=true", headers=headers)
    dry_hops = r.json()[0]["dryHops"]
    assert len(dry_hops) == 1
    assert dry_hops[0]["name"] == "Citra"


def test_list_no_hops_returns_empty_dry_hops(app_client):
    """A batch with no hops in the recipe returns an empty dryHops list."""
    with patch("oss.routers.brewfather.get_settings") as mock_cfg, \
         patch("oss.routers.brewfather.httpx.AsyncClient") as mock_cls:
        mock_cfg.return_value = _mock_settings()
        mock_cls.return_value = _async_client_mock([_fake_batch()])
        r = app_client.get("/brewfather/batch/?fermenting=true", headers=headers)
    assert r.json()[0]["dryHops"] == []


# ---------------------------------------------------------------------------
# GET /brewfather/batch/{id}
# ---------------------------------------------------------------------------

def test_get_batch_invalid_id_returns_400(app_client):
    """GET /batch/{id} returns 400 for invalid batch ID characters."""
    r = app_client.get("/brewfather/batch/inv@lid!", headers=headers)
    assert r.status_code == 400


def test_get_batch_missing_keys_returns_424(app_client):
    """GET /batch/{id} returns 424 when keys are not configured."""
    with patch("oss.routers.brewfather.get_settings") as mock_cfg:
        mock_cfg.return_value = MagicMock(
            brewfather_user_key=SecretStr(""),
            brewfather_api_key=SecretStr(""),
        )
        r = app_client.get("/brewfather/batch/abc123", headers=headers)
    assert r.status_code == 424


def test_get_batch_connect_error_returns_400(app_client):
    """GET /batch/{id} returns 400 when Brewfather is unreachable."""
    with patch("oss.routers.brewfather.get_settings") as mock_cfg, \
         patch("oss.routers.brewfather.httpx.AsyncClient") as mock_cls:
        mock_cfg.return_value = _mock_settings()
        mock_cls.return_value = _async_client_mock(None, side_effect=httpx.ConnectError(""))
        r = app_client.get("/brewfather/batch/abc123", headers=headers)
    assert r.status_code == 400


def test_get_batch_success(app_client):
    """GET /batch/{id} returns raw JSON from Brewfather on success."""
    fake = _fake_batch()
    with patch("oss.routers.brewfather.get_settings") as mock_cfg, \
         patch("oss.routers.brewfather.httpx.AsyncClient") as mock_cls:
        mock_cfg.return_value = _mock_settings()
        mock_cls.return_value = _async_client_mock(fake)
        r = app_client.get("/brewfather/batch/abc123", headers=headers)
    assert r.status_code == 200
    assert r.json()["_id"] == "abc123"
