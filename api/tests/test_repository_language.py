# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Keep tracked source and documentation aligned with supported behavior."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()
FROZEN = "api/migrations/versions/000_initial_schema.py"
SOURCE_SUFFIXES = {".py", ".js", ".ts", ".vue", ".md", ".yaml", ".yml", ".sh",
                   ".toml", ".html", ".css", ".json"}
DOC_NAMES = {"AGENTS.md", "CLAUDE.md", "README", "Makefile", "Dockerfile"}
DATABASE_NAME = re.compile("ora" + "cle", re.IGNORECASE)
PLAN_PATH = re.compile(r"tasks/|plan-[a-z-]*\.md", re.IGNORECASE)


def _tracked_text_files():
    """Yield tracked source and documentation files outside generated graph output."""
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                            capture_output=True)
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        name = raw_path.decode()
        path = ROOT / name
        if (name in {SELF, FROZEN} or name.startswith("graphify-out/")
                or not path.is_file() or (path.suffix not in SOURCE_SUFFIXES
                                           and path.name not in DOC_NAMES)):
            continue
        yield name, path.read_text(encoding="utf-8")


def test_no_unsupported_database_name():
    """Tracked source and docs do not name an unsupported database."""
    matches = [name for name, body in _tracked_text_files() if DATABASE_NAME.search(body)]
    assert not matches, matches


def test_no_plan_paths_in_source_or_docs():
    """Tracked source and docs do not cite planning files."""
    matches = [name for name, body in _tracked_text_files() if PLAN_PATH.search(body)]
    assert not matches, matches
