# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Secrets in Settings are SecretStr, never printed, and generated keys are random."""
import pytest
from pydantic import SecretStr

from core.config import Settings, generate_api_key, get_settings

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
