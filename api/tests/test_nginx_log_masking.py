# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""The web nginx access log masks the device token carried in the URL path."""
import re
from pathlib import Path

import pytest

NGINX_DIR = Path(__file__).resolve().parents[2] / "web" / "ngnix"
CONFS = ["nginx.http.conf", "nginx.https.conf"]
MAP_LINE = re.compile(r'^\s*~(\S+)\s+"?([^";]+)"?;\s*$')


def _mask_rules(conf: str):
    """Return (regex, template) pairs from the $brewgraph_log_path map, in order."""
    block = re.search(r"map \$request_uri \$brewgraph_log_path \{(.*?)\n\}", conf, re.S)
    assert block, "log-path map missing"
    rules = []
    for line in block.group(1).splitlines():
        found = MAP_LINE.match(line)
        if found:
            pattern = found.group(1).replace("(?<", "(?P<")
            template = re.sub(r"\$\{?(\w+)\}?", r"\\g<\1>", found.group(2))
            rules.append((re.compile(pattern), template))
    return rules


def _mask(rules, request_uri: str) -> str:
    for regex, template in rules:
        found = regex.match(request_uri)
        if found:
            return found.expand(template)
    return "-"


@pytest.mark.parametrize("name", CONFS)
@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        ("/ingest/ispindel/abc", "/ingest/ispindel/{token}"),
        ("/api/ingest/ispindel/abc", "/api/ingest/ispindel/{token}"),
        ("/ingest/gravitymon/abc?x=1", "/ingest/gravitymon/{token}"),
        ("/api/ingest/pressuremon/abc", "/api/ingest/pressuremon/{token}"),
        ("/api/ingest/test/abc", "/api/ingest/test/{token}"),
        ("/ingest/ispindel", "/ingest/ispindel"),
        ("/ingest/ispindel?token=abc", "/ingest/ispindel"),
        ("/api/ingest/kegmon/beer", "/api/ingest/kegmon/beer"),
        ("/api/ingest/register", "/api/ingest/register"),
    ],
)
def test_token_masked_in_log_path(name, uri, expected):
    """Token segments become {token}; query strings and other routes are not logged raw."""
    rules = _mask_rules((NGINX_DIR / name).read_text())
    assert _mask(rules, uri) == expected


@pytest.mark.parametrize("name", CONFS)
def test_every_server_uses_masked_access_log(name):
    """Each server block overrides the image's default access log."""
    conf = (NGINX_DIR / name).read_text()
    servers = len(re.findall(r"^server \{", conf, re.M))
    assert conf.count("access_log /var/log/nginx/access.log brewgraph_masked;") == servers
