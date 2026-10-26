# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Every tracked Python, TypeScript, JavaScript and Vue source file carries a copyright notice."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUFFIXES = {".py", ".ts", ".js", ".mjs", ".vue"}
# Written at container start by web/ngnix/entrypoint.sh; the tracked copy is a placeholder.
EXEMPT = {"web/public/env-config.js"}
NOTICE = b"Copyright (c)"
HEAD_BYTES = 2000


def test_source_files_carry_copyright_notice():
    """No tracked source file is missing its copyright notice near the top."""
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                            capture_output=True)
    missing = []
    for raw_path in result.stdout.split(b"\0"):
        name = raw_path.decode()
        path = ROOT / name
        if (not name or name in EXEMPT or path.suffix not in SUFFIXES
                or not path.is_file()):
            continue
        if NOTICE not in path.read_bytes()[:HEAD_BYTES]:
            missing.append(name)
    assert not missing, missing
