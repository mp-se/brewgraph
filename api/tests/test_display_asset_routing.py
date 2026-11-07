# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""The display's bundles use their own asset prefix, routed to the display container.

The web app owns /assets/ in the shared proxy; a display built with the default
assetsDir would request /assets/index-*.js and receive the web app's index.html.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFS = ["nginx.http.conf", "nginx.https.conf"]


def _assets_dir() -> str:
    config = (ROOT / "display" / "vite.config.ts").read_text(encoding="utf-8")
    found = re.search(r"assetsDir:\s*'([^']+)'", config)
    assert found, "display/vite.config.ts must set build.assetsDir"
    return found.group(1)


def test_display_assets_dir_differs_from_web_default():
    assert _assets_dir() != "assets"


@pytest.mark.parametrize("name", CONFS)
def test_proxy_routes_display_assets_to_display_container(name):
    conf = (ROOT / "web" / "ngnix" / name).read_text(encoding="utf-8")
    block = re.search(
        r"location \^~ /" + re.escape(_assets_dir()) + r"/ \{(.*?)\}", conf, re.S
    )
    assert block, "no proxy location for the display asset prefix"
    assert "proxy_pass http://brewgraph-display;" in block.group(1)


@pytest.mark.parametrize("name", CONFS)
def test_proxy_routes_display_theme_to_display_container(name):
    conf = (ROOT / "web" / "ngnix" / name).read_text(encoding="utf-8")
    block = re.search(r"location = /theme\.css \{(.*?)\}", conf, re.S)
    assert block, "no proxy location for the display theme.css"
    assert "proxy_pass http://brewgraph-display;" in block.group(1)
