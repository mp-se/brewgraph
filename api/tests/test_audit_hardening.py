# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Regression coverage for security and resource-bound audit fixes."""
import ipaddress
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from starlette.exceptions import HTTPException

from core import cache
from core.utils import resolve_and_pin_outbound_url
from oss.services._chart_window import (MAX_CHART_SOURCE_ROWS, MAX_CHART_WINDOW,
                                        bounded_chart_rows, bounded_chart_window)


def test_outbound_hostname_is_pinned_but_tls_identity_is_preserved():
    """A later DNS answer cannot change the TCP peer selected for delivery."""
    with patch(
        "core.utils._resolve_host_addresses",
        return_value={ipaddress.ip_address("8.8.8.8")},
    ):
        target = resolve_and_pin_outbound_url("https://hooks.example:8443/pour")
    assert target.url == "https://8.8.8.8:8443/pour"
    assert target.host_header == "hooks.example:8443"
    assert target.sni_hostname == "hooks.example"


@pytest.mark.parametrize(
    "key",
    (
        "auth:failures:client",
        "ingest:rate:client",
        "ingest:blocked:client",
        "ingest_rl_device:token-hash",
        "ingest_throttle_device-id",
    ),
)
def test_cache_fallback_keeps_rate_limit_counters_when_redis_is_disabled(key):
    """Counter and block-key semantics survive without a Redis process."""
    with patch("core.cache.pool", None):
        cache._fallback_values.clear()  # pylint: disable=protected-access
        try:
            assert cache.increment_key(key, 60) == 1
            assert cache.increment_key(key, 60) == 2
            assert cache.exist_key(key)
            assert cache.key_ttl(key) is not None
            cache.delete_key(key)
            assert not cache.exist_key(key)
        finally:
            cache._fallback_values.clear()  # pylint: disable=protected-access


def test_explicit_chart_windows_default_to_a_bounded_recent_period():
    """A one-sided chart range cannot expand into an unbounded query."""
    start, end = bounded_chart_window(None, None)
    assert start is None
    assert end is None
    start, end = bounded_chart_window(None, datetime.now(UTC))
    assert end - start == MAX_CHART_WINDOW


def test_chart_windows_reject_ranges_over_the_resource_ceiling():
    """Older data is retrieved in explicit adjacent windows."""
    end = datetime.now(UTC)
    with pytest.raises(HTTPException, match="must not exceed"):
        bounded_chart_window(end - timedelta(days=32), end)


def test_chart_rows_reject_an_overly_dense_time_window():
    """The source query cannot materialise more than the chart resource ceiling."""
    query = MagicMock()
    session = MagicMock()
    session.scalars.return_value.all.return_value = list(range(MAX_CHART_SOURCE_ROWS + 1))
    with pytest.raises(HTTPException, match="too many readings"):
        bounded_chart_rows(session, query)
    query.limit.assert_called_once_with(MAX_CHART_SOURCE_ROWS + 1)
