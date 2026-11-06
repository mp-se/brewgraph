# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""The fixed tap list logo set and the SVG files the display app serves for it."""
import pathlib
import re

import pytest

from oss.schemas.platform import TAP_LIST_LOGOS

LOGO_DIR = pathlib.Path(__file__).resolve().parents[2] / "display" / "public" / "logos"


def test_logo_keys_are_the_fixed_set():
    """The accepted keys are exactly the eight documented symbols."""
    assert set(TAP_LIST_LOGOS) == {
        "hop", "barley", "barrel", "kettle", "bottle", "glass", "tap", "yeast",
    }


@pytest.mark.parametrize("key", TAP_LIST_LOGOS)
def test_every_key_has_a_monochrome_svg(key):
    """Each key has display/public/logos/<key>.svg drawn on a 24x24 canvas in currentColor."""
    svg = (LOGO_DIR / f"{key}.svg").read_text(encoding="utf-8")
    assert 'viewBox="0 0 24 24"' in svg
    assert 'fill="currentColor"' in svg
    assert not re.search(r"#[0-9a-fA-F]{3,6}|<image|<script", svg)


def test_no_stray_logo_files():
    """Every file in the logo directory belongs to a key."""
    assert {p.stem for p in LOGO_DIR.glob("*.svg")} == set(TAP_LIST_LOGOS)
