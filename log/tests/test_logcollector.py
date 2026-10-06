# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Unit tests for logcollector.py — pure-logic parts only.

Coverage targets:
- write_key(): Redis pool-is-None short-circuit, successful set, ConnectionError fallback.
- ThreadWrapper: initial state, stop(), idempotent stop.

Not covered here (require live WebSocket / HTTP server):
- websocket_collector() I/O loop
- main() async polling loop
"""

from unittest.mock import MagicMock, patch

import redis

import logcollector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_pool():
    logcollector.pool = None


# ---------------------------------------------------------------------------
# write_key
# ---------------------------------------------------------------------------

class TestWriteKey:
    """Tests for write_key() Redis helper."""

    def setup_method(self):
        _reset_pool()

    def teardown_method(self):
        _reset_pool()

    def test_returns_true_when_pool_is_none(self):
        """No Redis pool — write_key should short-circuit and return True."""
        assert logcollector.write_key("some_key", "some_value") is True

    def test_sets_key_and_returns_true_when_redis_available(self):
        """Successful Redis set returns True and calls set() with correct args."""
        mock_redis_instance = MagicMock()
        logcollector.pool = MagicMock()

        with patch("logcollector.redis.Redis", return_value=mock_redis_instance):
            result = logcollector.write_key("log_DEV01_count", 42)

        assert result is True
        mock_redis_instance.set.assert_called_once_with(
            name="log_DEV01_count", value="42", ex=60 * 60 * 6
        )

    def test_returns_false_on_connection_error(self):
        """Redis ConnectionError causes write_key to return False."""
        logcollector.pool = MagicMock()

        with patch("logcollector.redis.Redis") as mock_cls:
            mock_cls.return_value.set.side_effect = redis.exceptions.ConnectionError("refused")
            result = logcollector.write_key("log_DEV01_count", 1)

        assert result is False


# ---------------------------------------------------------------------------
# _fetch_devices
# ---------------------------------------------------------------------------

class TestFetchDevices:
    """Tests for the API pagination response parser."""

    def setup_method(self):
        logcollector.endpoint = "http://brewgraph-api/api/devices?pageSize=200"
        logcollector.headers = {"Authorization": "Bearer test"}

    def test_returns_items_from_paginated_response(self):
        """The API wraps device rows in the ``items`` field."""
        response = MagicMock(ok=True)
        response.json.return_value = {"items": [{"chipId": "DEV01"}], "total": 1}

        with patch("logcollector.requests.get", return_value=response) as get:
            assert logcollector._fetch_devices() == [{"chipId": "DEV01"}]

        get.assert_called_once_with(
            "http://brewgraph-api/api/devices?pageSize=200",
            headers={"Authorization": "Bearer test"},
            timeout=10,
        )

    def test_returns_empty_list_for_unexpected_response(self):
        """Malformed or legacy response payloads must not start bogus collectors."""
        response = MagicMock(ok=True)
        response.json.return_value = [{"chipId": "DEV01"}]

        with patch("logcollector.requests.get", return_value=response):
            assert logcollector._fetch_devices() == []


# ---------------------------------------------------------------------------
# ThreadWrapper
# ---------------------------------------------------------------------------

class TestThreadWrapper:
    """Tests for ThreadWrapper state machine."""

    def test_initial_state_is_not_stopped(self):
        """A freshly created wrapper should not be in stopped state."""
        tw = logcollector.ThreadWrapper()
        assert tw.is_stopped() is False

    def test_stop_transitions_to_stopped(self):
        """Calling stop() should set the stopped flag."""
        tw = logcollector.ThreadWrapper()
        tw.stop()
        assert tw.is_stopped() is True

    def test_stop_is_idempotent(self):
        """Calling stop() twice should not raise and should stay stopped."""
        tw = logcollector.ThreadWrapper()
        tw.stop()
        tw.stop()
        assert tw.is_stopped() is True

    def test_is_alive_reflects_thread_state(self):
        """is_alive() delegates to the underlying thread."""
        import threading

        tw = logcollector.ThreadWrapper()
        barrier = threading.Barrier(2)

        def _worker():
            barrier.wait()   # signal: thread is running
            barrier.wait()   # wait: hold until we check is_alive

        tw.thread = threading.Thread(target=_worker, daemon=True)
        tw.thread.start()
        barrier.wait()       # wait until thread is running

        assert tw.is_alive() is True

        barrier.wait()       # release thread to finish
        tw.thread.join()
        assert tw.is_alive() is False
