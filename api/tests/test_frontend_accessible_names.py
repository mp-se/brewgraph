# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""An icon-only button must carry an accessible name.

A `<button>` whose entire content is a Bootstrap icon is announced by a screen
reader as "button". Thirteen were in that state across the views and fragments,
including every modal close control, which made keyboard and screen-reader
navigation of the batch screens guesswork.

Lives beside the endpoint contract test rather than in ESLint on purpose:
`eslint-plugin-vuejs-accessibility` covers this and more, but it brings a
dependency and a rule set to tune, and the one rule that actually bit is
mechanical enough to state directly.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_SRC = REPO_ROOT / "web" / "src"

_BUTTON = re.compile(r"<button\b[^>]*>(.*?)</button>", re.S)
_TAG = re.compile(r"<[^>]+>")


def _unlabelled_icon_buttons() -> list[str]:
    """Return `path:line` for every button with no text and no accessible name."""
    offenders: list[str] = []
    for path in sorted(WEB_SRC.rglob("*.vue")):
        text = path.read_text(encoding="utf-8")
        for match in _BUTTON.finditer(text):
            if _TAG.sub("", match.group(1)).strip():
                continue  # has visible text, which is its name
            head = match.group(0).split(">", 1)[0]
            if "aria-label" in head or "title" in head:
                continue
            line = text[: match.start()].count("\n") + 1
            offenders.append(f"{path.relative_to(REPO_ROOT)}:{line}")
    return offenders


def test_every_icon_button_has_an_accessible_name():
    """A screen reader must not announce a control as just "button"."""
    offenders = _unlabelled_icon_buttons()
    assert not offenders, (
        "these buttons have no text content and no aria-label or title, so a screen "
        "reader announces them as 'button'. Name the action:\n  "
        + "\n  ".join(offenders)
    )


def test_the_scan_can_see_a_violation():
    """Guards the guard: an empty glob or a stale regex would enforce nothing."""
    assert len(list(WEB_SRC.rglob("*.vue"))) > 20, "expected to scan the frontend"

    sample = '<button type="button" class="btn"><i class="bi bi-trash"></i></button>'
    match = _BUTTON.search(sample)
    assert match and not _TAG.sub("", match.group(1)).strip(), (
        "the button pattern no longer recognises an icon-only button"
    )
