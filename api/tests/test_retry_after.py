# Copyright (c) 2024-2026 Magnus Persson. All rights reserved.
# Commercial License is required for commercial use of this software.
"""`Retry-After` on rate-limited responses.

The header is required on every 429. A 429 without it tells firmware to back off
and not for how long, so a device either retries immediately — burning the
budget again — or invents a delay.
"""
from unittest.mock import patch

from core.middleware.auth import retry_after_headers


class TestRetryAfterHeaders:
    """`retry_after_headers` turns a throttle key into the header, or into nothing."""

    def test_prefers_the_live_ttl_over_the_nominal_interval(self):
        """A device throttled 2s into a 300s window is told 298, not 300."""
        with patch("core.middleware.auth.key_ttl", return_value=298):
            assert retry_after_headers("k", fallback=300) == {"Retry-After": "298"}

    def test_falls_back_when_the_ttl_is_unknown(self):
        """Redis down or key without expiry — the nominal interval is still honest."""
        with patch("core.middleware.auth.key_ttl", return_value=None):
            assert retry_after_headers("k", fallback=300) == {"Retry-After": "300"}

    def test_omits_the_header_rather_than_guessing(self):
        """With neither a TTL nor a fallback, no header. A wrong value is worse
        than none: a client that trusts it retries early and is throttled again."""
        with patch("core.middleware.auth.key_ttl", return_value=None):
            headers = retry_after_headers("k")
        assert isinstance(headers, dict) and not headers

    def test_never_advertises_zero(self):
        """A TTL of 0 means the key expires this second, so the honest wait is 1 —
        not the nominal interval (the window has nearly elapsed) and not 0, which
        advertises 'retry now' as the answer to a request just refused."""
        with patch("core.middleware.auth.key_ttl", return_value=0):
            assert retry_after_headers("k", fallback=60) == {"Retry-After": "1"}
