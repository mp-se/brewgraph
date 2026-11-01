# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Secrets in Settings are SecretStr, never printed, and generated keys are random."""
import pytest
from pydantic import SecretStr

from fastapi.testclient import TestClient

from core.config import Settings, api_key_setting, generate_api_key, get_settings
from main_oss import app

SECRET_FIELDS = ["api_key", "database_url", "redis_password", "brewfather_api_key",
                 "brewfather_user_key", "brewers_friend_api_key", "brewers_friend_user_key"]


@pytest.mark.parametrize("name", SECRET_FIELDS)
def test_secret_fields_are_secretstr(name):
    """Every secret setting is a SecretStr."""
    assert isinstance(getattr(get_settings(), name), SecretStr)


def test_repr_does_not_reveal_secrets(monkeypatch):
    """Printing the settings object never shows a secret value."""
    settings = get_settings()
    for name in SECRET_FIELDS:
        value = getattr(settings, name).get_secret_value()
        if value:
            assert value not in repr(settings) and value not in str(settings)


def test_generated_keys_are_random_and_long():
    """Generated keys come from secrets.token_urlsafe: unique, URL-safe, at least 160 bits."""
    keys = {generate_api_key(20) for _ in range(50)}
    assert len(keys) == 50
    assert all(len(k) >= 27 and k.replace("-", "").replace("_", "").isalnum() for k in keys)


def test_default_api_key_is_generated_when_unset():
    """With API_KEY unset the setting is a generated key, never empty."""
    assert Settings.model_fields["api_key"].default


def test_valid_api_key_is_accepted(monkeypatch):
    """A printable ASCII key is returned unchanged."""
    monkeypatch.setenv("API_KEY", "Abc123-_.~!#%&/=?+secret")
    assert api_key_setting() == "Abc123-_.~!#%&/=?+secret"


@pytest.mark.parametrize("key,codepoint,position", [
    ("Öå", "U+00D6", "position 0"),
    ("okÄkey", "U+00C4", "position 2"),
    ("key with space", "U+0020", "position 3"),
    ("tab\tkey", "U+0009", "position 3"),
    ("nb space", "U+00A0", "position 2"),
])
def test_invalid_api_key_is_rejected_without_leaking(monkeypatch, key, codepoint, position):
    """A key outside printable ASCII is refused; the message never contains the key."""
    monkeypatch.setenv("API_KEY", key)
    with pytest.raises(ValueError, match="API_KEY") as excinfo:
        api_key_setting()
    message = str(excinfo.value)
    assert codepoint in message and position in message
    assert key not in message


def test_empty_api_key_is_rejected(monkeypatch):
    """An API_KEY that is set but empty is refused."""
    monkeypatch.setenv("API_KEY", "")
    with pytest.raises(ValueError, match="API_KEY"):
        api_key_setting()


def test_unset_api_key_generates_valid_key(monkeypatch):
    """With API_KEY unset a generated, printable ASCII key is used."""
    monkeypatch.delenv("API_KEY", raising=False)
    key = api_key_setting()
    assert key and all(0x21 <= ord(c) <= 0x7E for c in key)


def test_configured_api_key_is_printable_ascii():
    """The key the auth comparison receives is always printable ASCII."""
    key = get_settings().api_key.get_secret_value()
    assert key and all(0x21 <= ord(c) <= 0x7E for c in key)


def test_non_ascii_bearer_token_is_401_not_500():
    """A client-supplied non-ASCII token is an authentication failure, not a server error."""
    with TestClient(app) as client:
        response = client.get(
            "/api/batches",
            headers={"Authorization": "Bearer ÖåÄsecret".encode("utf-8")},
        )
    assert response.status_code == 401
