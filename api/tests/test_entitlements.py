# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for the capability predicate on AuthContext.

The answer to "may this principal use X" is unconditionally yes: this is a
single-operator instance, so there is no second principal to distinguish.
These tests exist to keep it that way — a deny path added here would silently
disable features on self-hosted instances, which is a restriction this build
must never acquire.

Capability names are deliberately meaningless strings here. This codebase
defines no vocabulary of them, so the tests use invented names rather than
naming anything real.
"""
from dataclasses import fields

from core.middleware.auth import AuthContext


class TestCanIsTotal:
    """``can()`` permits every input, including names nothing defines."""

    def test_permits_a_well_formed_name(self):
        """A well-formed, dotted capability name is permitted."""
        assert AuthContext().can("example.capability") is True

    def test_permits_an_undefined_name(self):
        """There is no capability vocabulary here, so an unknown name is not special."""
        assert AuthContext().can("nonexistent.made.up.name") is True

    def test_permits_degenerate_inputs(self):
        """Total means total: no input shape falls through to a deny."""
        auth = AuthContext()
        for value in ("", " ", "*", "..", "a" * 500, "UPPER.CASE", "1", "-"):
            assert auth.can(value) is True, f"can({value!r}) must be True"

    def test_entitlements_do_not_depend_on_quota_state(self):
        """A configured quota limit must not make a capability check deny.

        Quotas and capabilities are different questions — "how many" versus
        "may you at all" — carried on the same object. Coupling them would make
        a self-hosted instance lose a feature for having set a limit.
        """
        auth = AuthContext(quota_limits={"batches": 0, "devices": 0})
        assert auth.can("example.capability") is True
        assert auth.quota_limit("batches") == 0

    def test_can_is_not_overridable_by_construction(self):
        """``can`` is a method, not a settable field.

        Guards the extension contract: an extending deployment overrides the
        class, it does not pass a predicate in as data. If this ever becomes a
        dataclass field, every caller's contract changes shape.
        """
        assert "can" not in {f.name for f in fields(AuthContext)}
