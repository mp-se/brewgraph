# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.
"""Every endpoint the frontend calls must exist on the API.

The frontend suites mock `apiJson`/`apiOk`/`apiFetch`, so they assert that a
store sends what the test says it sends — never that anything answers. A call
to a deleted or misspelled endpoint therefore stays green forever. That is not
hypothetical: `deviceStore.ts` called `/steps` for months after nothing
changed, and would have kept passing tests through a rename, because nothing
checks the mocked path against a real route.

This closes that gap from the side that knows the truth. It parses the API
call sites out of `web/src` and checks each one against the mounted route
table — the same object FastAPI serves. No new toolchain and no generated
types: the app is already importable here, so the route table is free.

Adapted for this repo's call convention. An axios-chained-method frontend
calls `api.get('/x')`; this repo's single frontend instead routes every call
through `apiJson`/`apiOk`/`apiFetch`
(`web/src/modules/apiClient.ts`), where the HTTP method is a string-literal
*first argument* and the path is relative (no leading `/`, no `/api` prefix —
`global.apiURL` in `globalStore.ts` prepends `baseURL + 'api/'` at call time).
Paths are frequently built by string concatenation (`'batches/' + id + '/x'`)
rather than template-literal interpolation, so the parser below walks a
balanced-paren/quote argument list instead of a single regex, and reduces
both `${expr}` and `+ identifier +` segments to the same `{}` placeholder
FastAPI's `{param}` path segments become after `_routes()`'s substitution.

What it cannot catch: request/response *shapes*. It answers "does something
answer this method and path", which is precisely the question the mocks
cannot.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from main_oss import app

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "web" / "src"

_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_CALL_START = re.compile(r"\b(?:apiJson|apiOk|apiFetch)\s*(?:<[^(]*?>)?\(")
_QUOTE_LITERAL = re.compile(r"""^(['"`])(.*)\1$""", re.S)

# (method, path) pairs with no server route, deliberately. Each entry needs a
# reason; an empty allowlist is the goal.
#
# The five entries below were all found by this check on its first run:
# `gravityStore.getLatestGravity`, `pressureStore.getLatestPressure`,
# `pourStore.getLatestPour`, `deviceStore.getLatestGravity`,
# `deviceStore.getLatestPressure` call "latest across everything"/"latest for
# this device" endpoints that were never implemented server-side. None of the
# five is called from any view or store outside its own definition and unit
# test — dead code with a green mocked test, exactly the gap this file exists
# to close. Not fixed here: whether the intent was a real endpoint (frontend
# bug) or the method should be deleted (dead code) is a product call, not a
# rename.
KNOWN_MISSING: dict[tuple[str, str], str] = {
    ("GET", "/api/batches/gravity/latest"): (
        "gravityStore.getLatestGravity() — unused outside its own unit test."
    ),
    ("GET", "/api/batches/pressure/latest"): (
        "pressureStore.getLatestPressure() — unused outside its own unit test."
    ),
    ("GET", "/api/vessels/pours/latest"): (
        "pourStore.getLatestPour() — unused outside its own unit test."
    ),
    ("GET", "/api/devices/{}/gravity/latest"): (
        "deviceStore.getLatestGravity() — unused outside its own unit test."
    ),
    ("GET", "/api/devices/{}/pressure/latest"): (
        "deviceStore.getLatestPressure() — unused outside its own unit test."
    ),
}


def _consume_quoted(text: str, i: int, quote: str, buf: list[str]) -> tuple[int, str | None]:
    """Append `text[i]` (part of an in-progress quoted span) to `buf`.

    Handles backslash escapes and quote termination. Returns the index to
    resume scanning from and the still-open quote char (`None` once closed).
    """
    ch = text[i]
    buf.append(ch)
    if ch == "\\":
        i += 1
        if i < len(text):
            buf.append(text[i])
    elif ch == quote:
        quote = None
    return i, quote


def _split_top_level(text: str, sep: str) -> list[str]:
    """Split `text` on `sep` at paren/bracket/brace depth 0, outside quotes."""
    parts: list[str] = []
    depth = 0
    quote: str | None = None
    buf: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            i, quote = _consume_quoted(text, i, quote, buf)
        else:
            if ch in "'\"`":
                quote = ch
                buf.append(ch)
            elif ch in "([{":
                depth += 1
                buf.append(ch)
            elif ch in ")]}":
                depth -= 1
                buf.append(ch)
            elif ch == sep and depth == 0:
                parts.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts]


def _call_args(text: str, open_paren_index: int) -> list[str]:
    """Given the index of a call's opening `(`, return its top-level args."""
    depth = 0
    quote: str | None = None
    buf: list[str] = []
    args: list[str] = []
    i = open_paren_index
    while i < len(text):
        ch = text[i]
        if quote:
            i, quote = _consume_quoted(text, i, quote, buf)
        else:
            if ch in "'\"`":
                quote = ch
                buf.append(ch)
            elif ch == "(":
                depth += 1
                if depth > 1:
                    buf.append(ch)
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    args.append("".join(buf))
                    return [a.strip() for a in args]
                buf.append(ch)
            elif ch in "[{":
                depth += 1
                buf.append(ch)
            elif ch in "]}":
                depth -= 1
                buf.append(ch)
            elif ch == "," and depth == 1:
                args.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        i += 1
    return [a.strip() for a in args]


def _continues_after_newline(text: str, i: int, buf: list[str]) -> bool:
    """Should a multi-line `const x = ...` expression keep consuming past a newline?

    Yes while the RHS has not started yet (`const path =` dangling at end of
    line, the RHS starting on the next line), or while the next line opens
    with `+` (string-concatenation continuation).
    """
    j = i + 1
    while j < len(text) and text[j] in " \t\n":
        j += 1
    stripped_so_far = "".join(buf).strip()
    return not stripped_so_far or (j < len(text) and text[j] == "+")


def _extract_identifier_expr(text: str, name: str, before: int) -> str | None:
    """Find `const/let/var <name> = <expr>` nearest before `text[before]`.

    Handles call sites (`batchStore.ts`, `vesselStore.ts`) that build a
    `path` variable across several lines before passing it to `apiJson`.
    Some files (`vesselStore.ts`'s `assignBatch`/`assignTap`) declare `path`
    more than once in different functions — the nearest *preceding*
    declaration is the right one, not the first in the file, so this scans
    all declarations and keeps the closest one before the call site.
    Consumes lines only while the next non-blank line starts with `+`
    (string-concatenation continuation), or the RHS has not started yet.
    """
    declares = list(re.finditer(rf"\b(?:const|let|var)\s+{re.escape(name)}\s*=", text[:before]))
    if not declares:
        return None
    match = declares[-1]
    i = match.end()
    depth = 0
    quote: str | None = None
    buf: list[str] = []
    while i < len(text):
        ch = text[i]
        if quote:
            i, quote = _consume_quoted(text, i, quote, buf)
        else:
            if ch in "'\"`":
                quote = ch
                buf.append(ch)
            elif ch in "([{":
                depth += 1
                buf.append(ch)
            elif ch in ")]}":
                depth -= 1
                buf.append(ch)
            elif ch == ";" and depth == 0:
                break
            elif ch == "\n" and depth == 0:
                if _continues_after_newline(text, i, buf):
                    buf.append(" ")
                else:
                    break
            else:
                buf.append(ch)
        i += 1
    return "".join(buf).strip()


def _normalise_segment(segment: str) -> str:
    """One `+`-joined term of a path expression -> its literal contribution."""
    literal = _QUOTE_LITERAL.match(segment)
    if literal:
        return re.sub(r"\$\{[^}]*\}", "{}", literal.group(2))
    if segment.startswith("(") and segment.endswith(")"):
        # A parenthesised ternary that only ever contributes an optional query
        # string, e.g. `(tapId ? '?tapId=' + tapId : '')` — the same shape the
        # `?` truncation above handles for template literals. Any branch
        # whose literal starts with `?` means the whole term is query-only
        # and can be dropped rather than turned into a spurious `{}` path
        # segment.
        inner = segment[1:-1]
        literals = re.findall(r"'([^']*)'|\"([^\"]*)\"|`([^`]*)`", inner)
        flat = [g for group in literals for g in group if g]
        if flat and all(text == "" or text.startswith("?") for text in flat):
            return ""
    return "{}"


def _normalise(expr: str) -> str:
    """Reduce a path expression to its static shape with `{}` placeholders."""
    segments = _split_top_level(expr, "+")
    joined = "".join(_normalise_segment(s) for s in segments)
    return joined.split("?", maxsplit=1)[0]


def _source_files() -> list[Path]:
    files: list[Path] = []
    for path in FRONTEND_SRC.rglob("*"):
        if path.suffix not in (".ts", ".vue"):
            continue
        # Test sources quote endpoints in mocks and prose, not in real calls.
        if any(part in ("test", "__tests__", "node_modules") for part in path.parts):
            continue
        files.append(path)
    return files


def _scan_text(text: str, label: str) -> list[tuple[str, str, str]]:
    """Return (method, path, "label:line") for every literal API call in `text`.

    A call whose options argument carries an explicit `baseURL` skips the
    `<origin>/api/` prefix (`apiClient.ts` uses `raw.baseURL ?? global.apiURL`),
    so its path is relative to the origin and is checked as `/<path>`. The SSE
    stream is the one such call: `apiFetch('GET', 'events', undefined,
    { baseURL: global.baseURL, ... })`, mounted outside `/api`.
    """
    sites: list[tuple[str, str, str]] = []
    for match in _CALL_START.finditer(text):
        args = _call_args(text, match.end() - 1)
        if len(args) < 2:
            continue
        method_literal = _QUOTE_LITERAL.match(args[0])
        if not method_literal or method_literal.group(2) not in _METHODS:
            continue
        method = method_literal.group(2)

        path_expr = args[1]
        bare_identifier = re.fullmatch(r"[A-Za-z_$][\w$]*", path_expr)
        if bare_identifier:
            resolved = _extract_identifier_expr(text, path_expr, match.start())
            if resolved is None:
                continue
            path_expr = resolved

        url = _normalise(path_expr)
        if not url:
            continue
        has_base_url = len(args) >= 4 and re.search(r"\bbaseURL\b", args[3]) is not None
        prefix = "/" if has_base_url else "/api/"
        line = text.count("\n", 0, match.start()) + 1
        sites.append((method, prefix + url, f"{label}:{line}"))
    return sites


def _call_sites() -> list[tuple[str, str, str]]:
    """Return (method, path, "file:line") for every literal API call."""
    sites: list[tuple[str, str, str]] = []
    for path in _source_files():
        text = path.read_text(encoding="utf-8")
        sites.extend(_scan_text(text, str(path.relative_to(REPO_ROOT))))
    return sites


def _routes() -> set[tuple[str, str]]:
    """(METHOD, path) for every mounted route, with path params as placeholders.

    Read from the OpenAPI schema rather than `app.routes` — the latter yields
    `_IncludedRouter` wrappers whose children are not walked, which silently
    reports almost every real route as missing.
    """
    return {
        (method.upper(), re.sub(r"\{[^}]*\}", "{}", path))
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }


def test_every_frontend_call_hits_a_real_endpoint():
    """Fail with file:line for any frontend call the API cannot answer."""
    routes = _routes()
    known_paths = {path for _, path in routes}

    failures = []
    for method, path, where in sorted(set(_call_sites())):
        if (method, path) in routes:
            continue
        if (method, path) in KNOWN_MISSING:
            continue
        if path in known_paths:
            allowed = sorted(m for m, p in routes if p == path)
            failures.append(f"{where}: {path} exists but not for {method} (has {allowed})")
        else:
            failures.append(f"{where}: no route serves {method} {path}")

    assert not failures, "Frontend calls endpoints the API does not serve:\n  " + "\n  ".join(
        failures
    )


def test_the_check_above_cannot_pass_vacuously():
    """Guard the parser: a regex that stops matching would make this suite useless."""
    sites = _call_sites()
    assert len(sites) > 20, f"only found {len(sites)} call sites — the extractor is broken"
    assert _routes(), "no routes discovered from the OpenAPI schema"


@pytest.mark.parametrize(("method", "path"), sorted(KNOWN_MISSING))
def test_known_missing_endpoints_are_still_missing(method, path):
    """Retire allowlist entries automatically once the endpoint lands."""
    assert (method, path) not in _routes(), (
        f"{method} {path} now exists — remove it from KNOWN_MISSING."
    )


def test_explicit_base_url_call_bypasses_the_api_prefix():
    """The SSE call shape resolves to `/events` and is matched against real routes."""
    text = (
        "const r = await apiFetch('GET', 'events', undefined, {\n"
        "  baseURL: global.baseURL,\n  signal: ac.signal\n})\n"
    )
    assert [(m, p) for m, p, _ in _scan_text(text, "x.ts")] == [("GET", "/events")]
    assert ("GET", "/events") in _routes()
    # Without the override the same path gets the /api/ prefix.
    plain = [(m, p) for m, p, _ in _scan_text("apiFetch('GET', 'events')", "x.ts")]
    assert plain == [("GET", "/api/events")]
    assert ("GET", "/api/events") not in _routes()


def test_a_wrong_path_is_still_reported():
    """A non-existent route is not exempted, with or without a `baseURL` option."""
    routes = _routes()
    for text, expected in (
        ("apiFetch('GET', 'nope', undefined, { baseURL: b })", ("GET", "/nope")),
        ("apiJson('GET', 'nope')", ("GET", "/api/nope")),
    ):
        (site,) = _scan_text(text, "x.ts")
        assert site[:2] == expected
        assert expected not in routes
