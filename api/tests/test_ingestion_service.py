# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
"""Unit tests for IngestionService helpers — conversion branches and error logging."""
# pylint: disable=missing-function-docstring,protected-access
import uuid
from unittest.mock import MagicMock, patch

import pytest

from oss.services import ingestion as ingestion_module
from oss.services.ingestion import _safe_float


# ---------------------------------------------------------------------------
# _safe_float
# ---------------------------------------------------------------------------

def test_safe_float_non_numeric_returns_default():
    assert _safe_float("not-a-number") == 0.0


def test_safe_float_none_returns_default():
    assert _safe_float(None, default=99.0) == 99.0


def test_safe_float_inf_returns_default():
    assert _safe_float(float("inf")) == 0.0


def test_safe_float_clamps_high():
    assert _safe_float(200.0, lo=0.0, hi=100.0) == 100.0


def test_safe_float_clamps_low():
    assert _safe_float(-5.0, lo=0.0, hi=100.0) == 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ingestion_svc(db=None):
    from oss.services.ingestion import IngestionService  # pylint: disable=import-outside-toplevel
    settings = MagicMock()
    settings.unit_type = "metric"
    return IngestionService(db or MagicMock(), settings)


def _mock_device(vessel_id=None):
    d = MagicMock()
    d.id = uuid.uuid4()
    d.batch_id = uuid.uuid4()
    d.vessel_id = vessel_id
    return d


def _mock_batch(og=None, fg=None):
    b = MagicMock()
    b.id = uuid.uuid4()
    b.og = og
    b.fg = fg
    return b


# ---------------------------------------------------------------------------
# write_gravity — Fahrenheit conversion (lines 50-53)
# ---------------------------------------------------------------------------

def test_write_gravity_fahrenheit_converts_to_celsius():
    """Temperature in °F is converted to °C before storing."""
    svc = _make_ingestion_svc()
    svc._gravity_svc = MagicMock()
    captured = {}
    svc._gravity_svc.create.side_effect = (
        lambda r: captured.update({"temp": r.temperature}) or MagicMock()
    )

    svc.write_gravity(
        _mock_batch(), _mock_device(), {"gravity": 1.050, "temperature": 68.0, "temp_units": "F"}
    )
    assert captured["temp"] == pytest.approx(20.0, abs=0.1)


def test_write_gravity_plato_converts_to_sg():
    """Gravity in Plato is converted to SG before storing."""
    svc = _make_ingestion_svc()
    svc._gravity_svc = MagicMock()
    captured = {}
    svc._gravity_svc.create.side_effect = (
        lambda r: captured.update({"grav": r.gravity}) or MagicMock()
    )

    svc.write_gravity(
        _mock_batch(), _mock_device(), {"gravity": 12.0, "gravity-unit": "P", "temperature": 20.0}
    )
    assert captured["grav"] == pytest.approx(1.048, abs=0.002)


def test_write_gravity_sentinel_temperature_stored_as_none():
    """Temperature below valid range (-270) is stored as None."""
    svc = _make_ingestion_svc()
    svc._gravity_svc = MagicMock()
    captured = {}
    svc._gravity_svc.create.side_effect = (
        lambda r: captured.update({"temp": r.temperature}) or MagicMock()
    )

    svc.write_gravity(_mock_batch(), _mock_device(), {"gravity": 1.050, "temperature": -300.0})
    assert captured["temp"] is None


# ---------------------------------------------------------------------------
# write_gravity — OG/FG bounds auto-exclusion
# ---------------------------------------------------------------------------

def _write_gravity_and_capture_excluded(batch, gravity):
    svc = _make_ingestion_svc()
    svc._gravity_svc = MagicMock()
    captured = {}
    svc._gravity_svc.create.side_effect = (
        lambda r: captured.update({"excluded": r.excluded}) or MagicMock()
    )
    svc.write_gravity(batch, _mock_device(), {"gravity": gravity})
    return captured["excluded"]


def test_write_gravity_above_og_bound_excluded():
    """Reading >10% above OG is auto-excluded."""
    excluded = _write_gravity_and_capture_excluded(_mock_batch(og=1.050), 1.156)
    assert excluded is True


def test_write_gravity_below_fg_bound_excluded():
    """Reading >10% below FG is auto-excluded."""
    excluded = _write_gravity_and_capture_excluded(_mock_batch(fg=1.010), 0.908)
    assert excluded is True


def test_write_gravity_in_bounds_not_excluded():
    """Reading within OG/FG bounds is not excluded."""
    excluded = _write_gravity_and_capture_excluded(_mock_batch(og=1.050, fg=1.010), 1.030)
    assert excluded is False


def test_write_gravity_no_targets_not_excluded():
    """Batch with no OG/FG targets skips validation entirely."""
    excluded = _write_gravity_and_capture_excluded(_mock_batch(og=None, fg=None), 1.500)
    assert excluded is False


def test_write_gravity_at_og_boundary_not_excluded():
    """Reading exactly at the 10%-above-OG boundary is inclusive (not excluded)."""
    excluded = _write_gravity_and_capture_excluded(_mock_batch(og=1.050), 1.155)
    assert excluded is False


def test_write_gravity_at_fg_boundary_not_excluded():
    """Reading exactly at the 10%-below-FG boundary is inclusive (not excluded)."""
    excluded = _write_gravity_and_capture_excluded(_mock_batch(fg=1.010), 0.909)
    assert excluded is False


# ---------------------------------------------------------------------------
# write_pressure — BAR unit and Fahrenheit (lines 196, 208-212)
# ---------------------------------------------------------------------------

def test_write_pressure_bar_converts_to_kpa():
    """Pressure in BAR is multiplied by 100 to get kPa."""
    svc = _make_ingestion_svc()
    svc._pressure_svc = MagicMock()
    captured = {}
    svc._pressure_svc.create.side_effect = (
        lambda r: captured.update({"pres": r.pressure}) or MagicMock()
    )

    svc.write_pressure(_mock_device(), {"pressure": 1.5, "pressure_units": "BAR"})
    assert captured["pres"] == pytest.approx(150.0, abs=0.01)


def test_write_pressure_fahrenheit_converts_to_celsius():
    """Pressure-sensor temperature in °F is converted to °C."""
    svc = _make_ingestion_svc()
    svc._pressure_svc = MagicMock()
    captured = {}
    svc._pressure_svc.create.side_effect = (
        lambda r: captured.update({"temp": r.temperature}) or MagicMock()
    )

    svc.write_pressure(
        _mock_device(), {"pressure": 10.0, "temperature": 32.0, "temp_units": "F"}
    )
    assert captured["temp"] == pytest.approx(0.0, abs=0.1)


# ---------------------------------------------------------------------------
# log_ingestion_error (lines 223-239)
# ---------------------------------------------------------------------------

def test_log_ingestion_error_writes_entry():
    """log_ingestion_error commits an IngestionLog row and redacts token."""
    from oss.services.ingestion import IngestionService  # pylint: disable=import-outside-toplevel
    db = MagicMock()
    svc = IngestionService(db, MagicMock())
    svc.log_ingestion_error(
        ip="1.2.3.4", device_type="gravitymon", reason="invalid_token",
        error_detail="mismatch", payload={"token": "secret", "gravity": 1.050},
    )
    db.add.assert_called_once()
    db.commit.assert_called_once()
    stored = db.add.call_args[0][0]
    assert "***" in (stored.payload or "")


def test_log_ingestion_error_truncates_ip_address():
    """The stored IngestionLog row never carries the full client IP."""
    db = MagicMock()
    ingestion_module.IngestionService(db, MagicMock()).log_ingestion_error(
        ip="203.0.113.77", device_type="gravitymon", reason="invalid_token",
    )
    stored = db.add.call_args[0][0]
    assert stored.ip_address == "203.0.113.0"


def test_log_ingestion_error_handles_db_failure():
    """log_ingestion_error swallows exceptions and rolls back."""
    from oss.services.ingestion import IngestionService  # pylint: disable=import-outside-toplevel
    db = MagicMock()
    db.add.side_effect = Exception("db down")
    IngestionService(db, MagicMock()).log_ingestion_error(ip="x", device_type="t", reason="fail")
    db.rollback.assert_called_once()


def test_log_ingestion_error_none_payload():
    """log_ingestion_error handles None payload."""
    from oss.services.ingestion import IngestionService  # pylint: disable=import-outside-toplevel
    db = MagicMock()
    IngestionService(db, MagicMock()).log_ingestion_error(
        ip="x", device_type="t", reason="r", payload=None
    )
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# trigger_dry_hops — advisory follow-on handling
# ---------------------------------------------------------------------------

def test_trigger_dry_hops_records_failure_and_keeps_ingest_non_fatal(caplog):
    """A failed background trigger rolls back and is visible in System Logs.

    The ingest request has already committed when this runs, so the exception must
    not escape.  Pending hops remain untriggered and the next gravity reading retries
    the idempotent evaluation.
    """
    from oss.services.ingestion import IngestionService  # pylint: disable=import-outside-toplevel

    db = MagicMock()
    batch_id = uuid.uuid4()
    svc = IngestionService(db, MagicMock())
    with patch(
        "oss.services.batch_dry_hop.BatchDryHopService.check_and_trigger",
        side_effect=RuntimeError("database unavailable"),
    ), patch("oss.services.ingestion._gravity.system_log") as system_log_mock:
        svc.trigger_dry_hops(batch_id, 1.020)

    db.rollback.assert_called_once()
    system_log_mock.assert_called_once()
    assert system_log_mock.call_args.args[0] == "dry_hop_trigger_failed"
    assert str(batch_id) in system_log_mock.call_args.args[1]
    assert "Dry-hop trigger failed" in caplog.text
