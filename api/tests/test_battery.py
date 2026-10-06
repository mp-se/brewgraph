# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/battery.py — battery voltage → State of Charge conversion."""
import ast

import pytest

import oss.jobs.predictions as predictions_module
from oss.battery import (OCV_18650, OCV_LIPO_POUCH, table_for,
                          voltage_to_soc)


# ---------------------------------------------------------------------------
# voltage_to_soc
# ---------------------------------------------------------------------------

class TestVoltageToSoc:
    """voltage_to_soc maps 18650 open-circuit voltage to state-of-charge percent."""

    def test_full_charge(self):
        """4.20V is a full battery."""
        assert voltage_to_soc(4.20) == pytest.approx(100.0)

    def test_above_max_clamps_to_100(self):
        """Voltages above the curve maximum clamp to 100%."""
        assert voltage_to_soc(4.5) == pytest.approx(100.0)

    def test_below_min_clamps_to_0(self):
        """Voltages below the curve minimum clamp to 0%."""
        assert voltage_to_soc(2.5) == pytest.approx(0.0)

    def test_midpoint_interpolated(self):
        """Voltages between curve points interpolate linearly."""
        # 3.75V is halfway between 3.70 (60%) and 3.80 (70%) → 65%
        assert voltage_to_soc(3.75) == pytest.approx(65.0, abs=0.1)

    def test_known_point(self):
        """An exact curve point returns its tabulated SoC."""
        assert voltage_to_soc(3.60) == pytest.approx(50.0)

    def test_none_in_returns_none_out(self):
        """No voltage reading (e.g. a mains-powered device) is not a flat cell."""
        assert voltage_to_soc(None) is None

    def test_healthy_cell_not_reported_as_low(self):
        """Regression: 3.9V is a healthy 18650 charge, not a low-battery reading.

        A consumer that compares the raw `battery` volts column against a
        percentage threshold reads a healthy 3.9V cell as "4%" and fires
        constant low-battery alerts. 3.9V must map to a comfortably high SoC.
        """
        assert voltage_to_soc(3.9) > 20


# ---------------------------------------------------------------------------
# table_for
# ---------------------------------------------------------------------------

class TestTableFor:
    """table_for selects the OCV curve for a given device type."""

    def test_none_defaults_to_18650(self):
        """No device type given falls back to the 18650 curve."""
        assert table_for(None) is OCV_18650

    def test_unknown_device_type_defaults_to_18650(self):
        """An unrecognised device type also falls back to the 18650 curve."""
        assert table_for("some-unknown-device") is OCV_18650

    def test_pressuremon_has_its_own_entry(self):
        """pressuremon resolves to its own (currently aliased) curve."""
        assert table_for("pressuremon") is OCV_LIPO_POUCH


# ---------------------------------------------------------------------------
# Duplicate-conversion regression guard
# ---------------------------------------------------------------------------

def test_predictions_job_has_no_duplicate_ocv_table():
    """The OCV table must live in exactly one place: oss/battery.py.

    oss/jobs/predictions.py must not carry its own copy (_OCV_TABLE) or a
    _voltage_to_soc() function — that duplication is the drift hazard
    oss/battery.py exists to close. Guard against either reappearing there.
    """
    with open(predictions_module.__file__, encoding="utf-8") as fh:
        source = ast.parse(fh.read())
    top_level_names = {
        node.name
        for node in ast.walk(source)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "_voltage_to_soc" not in top_level_names
    assert not hasattr(predictions_module, "_OCV_TABLE")
