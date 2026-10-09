# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Configuration management and settings for BrewGraph API application."""
import logging
import secrets
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings
from starlette.config import Config

logger = logging.getLogger(__name__)
config = Config()


def generate_api_key(key_length: int) -> str:
    """Generate a cryptographically secure random API key."""
    return secrets.token_urlsafe(key_length)


class Settings(BaseSettings):
    """Application settings and configuration parameters."""
    version: str = "2.0.0"
    app_name: str = "BrewGraph API"
    redis_host: str = config("REDIS_HOST", cast=str, default="localhost")
    # Optional Redis AUTH password; empty (default) connects without auth.
    redis_password: SecretStr = config("REDIS_PASSWORD", cast=str, default="")
    scheduler_enabled: bool = config("SCHEDULER_ENABLED", cast=bool, default=True)
    cache_enabled: bool = config("CACHE_ENABLED", cast=bool, default=True)
    # Defaults to False: only set True when the API sits behind the bundled nginx
    # container (which sets X-Real-IP / X-Forwarded-For from $remote_addr).
    # Leaving it True when the API port is exposed directly lets callers spoof
    # their IP and bypass the auth brute-force rate limiter.
    trust_proxy_headers: bool = config("TRUST_PROXY_HEADERS", cast=bool, default=False)
    # Peers whose X-Real-IP / X-Forwarded-For are believed when TRUST_PROXY_HEADERS is on:
    # comma-separated IPs or CIDR ranges. Default: loopback and the private ranges.
    trusted_proxies: str = config(
        "TRUSTED_PROXIES", cast=str,
        default="127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7",
    )
    auth_max_failures: int = config("AUTH_MAX_FAILURES", cast=int, default=10)
    auth_block_seconds: int = config("AUTH_BLOCK_SECONDS", cast=int, default=300)
    # Grace period, in days, before a soft-deleted row (deleted_at set) is
    # permanently hard-deleted by the daily purge job
    # (oss/jobs/retention_purge.py). There is no export/archive feature, so once
    # a row crosses this window it is gone — unrecoverable. Set to -1 to
    # disable purging entirely (keep every soft-deleted row forever), matching
    # the "-1 = unlimited" convention used elsewhere in this codebase.
    soft_delete_purge_days: int = config("SOFT_DELETE_PURGE_DAYS", cast=int, default=7)
    # Cap on a stored JSON envelope. An unbounded JSON column is an unbounded row; 16 KiB
    # is generous for a firmware config and far past any prediction payload.
    max_envelope_bytes: int = config("MAX_ENVELOPE_BYTES", cast=int, default=16 * 1024)

    logger.info("redis_host: %s", redis_host)
    logger.info("redis_password: %s", "set" if redis_password else "not set")
    logger.info("scheduler_enabled: %s", scheduler_enabled)
    logger.info("cache_enabled: %s", cache_enabled)
    logger.info("trust_proxy_headers: %s", trust_proxy_headers)
    logger.info("auth_max_failures: %s", auth_max_failures)
    logger.info("auth_block_seconds: %s", auth_block_seconds)
    logger.info("soft_delete_purge_days: %s", soft_delete_purge_days)
    logger.info("max_envelope_bytes: %s", max_envelope_bytes)

    # Secrets and API keys (dont print to logs)
    database_url: SecretStr = config(
        "DATABASE_URL", cast=str, default="sqlite:///./brewgraph.sqlite"
    )
    api_key: SecretStr = config("API_KEY", cast=str, default=generate_api_key(20))
    brewfather_api_key: SecretStr = config("BREWFATHER_API_KEY", cast=str, default="")
    brewfather_user_key: SecretStr = config("BREWFATHER_USER_KEY", cast=str, default="")
    brewers_friend_api_key: SecretStr = config("BREWERS_FRIEND_API_KEY", cast=str, default="")
    brewers_friend_user_key: SecretStr = config("BREWERS_FRIEND_USER_KEY", cast=str, default="")


@lru_cache
def get_settings() -> Settings:
    """Get or create cached application settings instance."""
    settings = Settings()
    return settings
