# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""The state-transition endpoints that CRUD absorbed must stay gone.

The data API is CRUD, so a dedicated endpoint needs a reason a field write cannot
express. These had none: each wrote one column that `PATCH` already carries (see
test_vessels.py and test_batch_dry_hops.py).

Pinned here because the failure mode is silent: reintroducing one gives a second
write path for the same column, and the two drift.

**The /restore routes are no longer in this list.** They were removed alongside the
others, on the same reasoning — but the reasoning did not hold for them. `deletedAt`
is not writable through `PATCH` and deliberately never will be, since that would make
`PATCH` a second way to *delete*. So removing them left no way to undo a deletion at
all, which is the opposite of a field write in disguise: it is a transition with a
real precondition (the row must currently be deleted; restoring a live one is a 404)
and no alternative expression. Restore for batch, note, device, tap and vessel is
back.

The dry-hop and fermentation-step restores stay gone: those are recipe data the brewer
is actively editing and cheap to re-add.
"""
import uuid

from core.config import get_settings

HDR = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH = str(uuid.uuid4())
CHILD = str(uuid.uuid4())

REMOVED = [
    ("patch", f"/vessels/{CHILD}/assign-batch"),
    ("patch", f"/vessels/{CHILD}/assign-tap"),
    ("post", f"/batches/{BATCH}/dry-hops/{CHILD}/complete"),
    ("post", f"/batches/{BATCH}/dry-hops/{CHILD}/restore"),
    ("post", f"/batches/{BATCH}/fermentation-steps/restore"),
    ("post", f"/batches/{BATCH}/fermentation-steps/{CHILD}/restore"),
]


def test_removed_endpoints_have_no_route(app_client):
    """No handler matches — not merely a row that happens not to exist."""
    for method, path in REMOVED:
        r = getattr(app_client, method)(path, json={}, headers=HDR)
        # 405 rather than 404 for the bulk-steps path: with its POST gone,
        # /fermentation-steps/restore now matches /fermentation-steps/{step_id}, which
        # only accepts DELETE. Either way no handler exists.
        assert r.status_code in (404, 405), (
            f"{method.upper()} {path} still routes ({r.status_code})"
        )
        # A surviving route would 404 on the random ids above and read identically at
        # the status-code level, so the body is what distinguishes the two.
        assert r.json()["message"] in ("Not Found", "Method Not Allowed"), (path, r.json())
