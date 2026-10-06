# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for chamber control activation. Covers FermentationStepService.activate/deactivate
and IngestionService.resolve_chamber_mode."""
from datetime import UTC, date, datetime, timedelta
import uuid

from core.config import get_settings
from core.db import create_session
from core.models.registry import resolve_model
from tests.conftest import DEVICE_DEFAULTS, truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def _create_batch(app_client) -> str:
    return app_client.post(
        "/batches", json={"name": "Chamber Batch", "status": "fermenting"}, headers=headers
    ).json()["id"]


def _create_device(app_client, chip_id: str) -> dict:
    data = {
        "name": f"Chamber {chip_id}",
        "deviceType": "chamber",
        "chipId": chip_id,
        **DEVICE_DEFAULTS,
    }
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


def _link_device_to_batch(app_client, device_id: str, batch_id: str) -> None:
    r = app_client.patch(f"/devices/{device_id}", json={"batchId": batch_id}, headers=headers)
    assert r.status_code == 200


def _create_steps(app_client, batch_id: str, device_id: str):
    return app_client.post(
        f"/batches/{batch_id}/fermentation-steps",
        json=[
            {"batchId": batch_id, "deviceId": device_id, "order": 1, "type": "primary",
             "temp": 20.0, "days": 7, "control": "beer"},
            {"batchId": batch_id, "deviceId": device_id, "order": 2, "type": "secondary",
             "temp": 18.0, "days": 14, "control": "fridge"},
        ],
        headers=headers,
    ).json()


def _poll(app_client, token: str) -> dict:
    r = app_client.post(
        "/ingest/chamber",
        json={
            "token": token,
            "beer_temperature": 18.5,
            "temp_units": "C",
            "current_mode": "B",
            "current_target": 18.5,
        },
    )
    assert r.status_code == 200
    return r.json()


class TestActivateDeactivate:
    """Activation computes step dates and marks the batch under active control."""

    def test_activate_computes_step_dates_and_marks_batch_active(self, app_client):
        """Activating steps computes each step's date and flips chamber_control_active."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CA01")
        _create_steps(app_client, batch_id, device["id"])

        r = app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
        assert r.status_code == 200
        steps = r.json()
        assert steps[0]["date"] == date.today().isoformat()
        assert steps[1]["date"] == (date.today() + timedelta(days=7)).isoformat()

        batch = app_client.get(f"/batches/{batch_id}", headers=headers).json()
        assert batch["chamberControlActive"] is True

    def test_activate_with_no_steps_returns_400(self, app_client):
        """Activating a batch with no fermentation steps is rejected."""
        truncate_database()
        batch_id = _create_batch(app_client)
        r = app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
        assert r.status_code == 400

    def test_reactivate_recomputes_dates_from_today(self, app_client):
        """Re-activating discards the previous schedule and recomputes from today."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CA02")
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
        r = app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
        assert r.json()[0]["date"] == date.today().isoformat()

    def test_deactivate_marks_batch_inactive(self, app_client):
        """Deactivating steps flips chamber_control_active back off."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CA03")
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        r = app_client.post(f"/batches/{batch_id}/fermentation-steps/deactivate", headers=headers)
        assert r.status_code == 204
        batch = app_client.get(f"/batches/{batch_id}", headers=headers).json()
        assert batch["chamberControlActive"] is False

    def test_deactivate_unknown_batch_returns_404(self, app_client):
        """Deactivating a nonexistent batch returns 404."""
        truncate_database()
        r = app_client.post(
            "/batches/00000000-0000-0000-0000-000000000000/fermentation-steps/deactivate",
            headers=headers,
        )
        assert r.status_code == 404

    def test_deactivate_soft_deleted_batch_returns_404(self, app_client):
        """Deactivating chamber control on a soft-deleted batch is rejected —
        a deleted batch must not still have its controller mutable."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CA04")
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
        assert app_client.delete(f"/batches/{batch_id}", headers=headers).status_code == 204

        r = app_client.post(f"/batches/{batch_id}/fermentation-steps/deactivate", headers=headers)
        assert r.status_code == 404


class TestChamberPollResolution:
    """resolve_chamber_mode's setpoint resolution steps 1-6."""

    def test_poll_before_activation_returns_r(self, app_client):
        """Steps exist but the batch was never activated -> bare R."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CP01")
        _link_device_to_batch(app_client, device["id"], batch_id)
        _create_steps(app_client, batch_id, device["id"])

        data = _poll(app_client, device["token"])
        assert data["mode"] == "R"
        assert data["target_temperature"] is None

    def test_poll_device_not_linked_to_any_batch_returns_r(self, app_client):
        """A device with no batch link at all -> bare R."""
        truncate_database()
        device = _create_device(app_client, "CP02")
        data = _poll(app_client, device["token"])
        assert data["mode"] == "R"

    def test_poll_after_activation_returns_matching_step_setpoint(self, app_client):
        """After activation, the step matching today's date sets the target."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CP03")
        _link_device_to_batch(app_client, device["id"], batch_id)
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        data = _poll(app_client, device["token"])
        assert data["mode"] == "B"
        assert data["target_temperature"] == 20.0

    def test_poll_after_deactivate_returns_r(self, app_client):
        """After deactivation, polling returns bare R again."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CP04")
        _link_device_to_batch(app_client, device["id"], batch_id)
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
        app_client.post(f"/batches/{batch_id}/fermentation-steps/deactivate", headers=headers)

        data = _poll(app_client, device["token"])
        assert data["mode"] == "R"

    def test_poll_past_last_step_auto_deactivates(self, app_client):
        """Push the (activated) step's date into the past directly via the service
        layer — days=0 activation is now rejected (see test below), so expiry has
        to be simulated by backdating."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CP05")
        _link_device_to_batch(app_client, device["id"], batch_id)
        app_client.post(
            f"/batches/{batch_id}/fermentation-steps",
            json=[{"batchId": batch_id, "deviceId": device["id"], "order": 1,
                   "type": "primary", "temp": 20.0, "days": 1, "control": "beer"}],
            headers=headers,
        )
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        fermentation_step_model = resolve_model("FermentationStep")
        db = create_session()
        try:
            for step in db.query(fermentation_step_model).all():
                step.date = date.today() - timedelta(days=10)
            db.commit()
        finally:
            db.remove()

        data = _poll(app_client, device["token"])
        assert data["mode"] == "R"
        batch = app_client.get(f"/batches/{batch_id}", headers=headers).json()
        assert batch["chamberControlActive"] is False

    def test_poll_local_timestamp_resolves_step_server_date_would_miss(self, app_client):
        """A valid local_timestamp+timezone drives day-window matching even when the
        server's own date would land past the (backdated) step's window."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CP09")
        _link_device_to_batch(app_client, device["id"], batch_id)
        app_client.post(
            f"/batches/{batch_id}/fermentation-steps",
            json=[{"batchId": batch_id, "deviceId": device["id"], "order": 1,
                   "type": "primary", "temp": 20.0, "days": 1, "control": "beer"}],
            headers=headers,
        )
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        backdated_start = date.today() - timedelta(days=10)
        fermentation_step_model = resolve_model("FermentationStep")
        db = create_session()
        try:
            for step in db.query(fermentation_step_model).all():
                step.date = backdated_start
            db.commit()
        finally:
            db.remove()

        # Server's own date.today() is now 10 days past this step's window ->
        # bare R without the device-supplied local date (asserted by the
        # regression test below). With a local_timestamp landing inside the
        # backdated window, the device's own calendar date should win instead.
        r = app_client.post(
            "/ingest/chamber",
            json={
                "token": device["token"],
                "beer_temperature": 18.5,
                "temp_units": "C",
                "current_mode": "B",
                "current_target": 18.5,
                "local_timestamp": f"{backdated_start.isoformat()}T12:00:00",
                "timezone": "America/Chicago",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "B"
        assert data["target_temperature"] == 20.0

    def test_poll_without_local_timestamp_fields_unchanged(self, app_client):
        """A poll with neither `local_timestamp` nor `timezone` must fall back
        to server-date resolution — the same backdated-step setup produces
        server-date R."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CP10")
        _link_device_to_batch(app_client, device["id"], batch_id)
        app_client.post(
            f"/batches/{batch_id}/fermentation-steps",
            json=[{"batchId": batch_id, "deviceId": device["id"], "order": 1,
                   "type": "primary", "temp": 20.0, "days": 1, "control": "beer"}],
            headers=headers,
        )
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        fermentation_step_model = resolve_model("FermentationStep")
        db = create_session()
        try:
            for step in db.query(fermentation_step_model).all():
                step.date = date.today() - timedelta(days=10)
            db.commit()
        finally:
            db.remove()

        data = _poll(app_client, device["token"])
        assert data["mode"] == "R"
        assert data["target_temperature"] is None

    def test_poll_invalid_timezone_falls_back_to_server_date(self, app_client):
        """A garbage timezone string falls back to server-date behavior instead
        of raising — the poll must still return 200 with the server-date R."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CP11")
        _link_device_to_batch(app_client, device["id"], batch_id)
        app_client.post(
            f"/batches/{batch_id}/fermentation-steps",
            json=[{"batchId": batch_id, "deviceId": device["id"], "order": 1,
                   "type": "primary", "temp": 20.0, "days": 1, "control": "beer"}],
            headers=headers,
        )
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        backdated_start = date.today() - timedelta(days=10)
        fermentation_step_model = resolve_model("FermentationStep")
        db = create_session()
        try:
            for step in db.query(fermentation_step_model).all():
                step.date = backdated_start
            db.commit()
        finally:
            db.remove()

        r = app_client.post(
            "/ingest/chamber",
            json={
                "token": device["token"],
                "beer_temperature": 18.5,
                "temp_units": "C",
                "current_mode": "B",
                "current_target": 18.5,
                "local_timestamp": f"{backdated_start.isoformat()}T12:00:00",
                "timezone": "Not/A/Real/Zone",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "R"
        assert data["target_temperature"] is None

    def test_activate_rejects_zero_day_steps(self, app_client):
        """days < 1 makes a step unmatchable — activation rejects with 400."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CP08")
        app_client.post(
            f"/batches/{batch_id}/fermentation-steps",
            json=[{"batchId": batch_id, "deviceId": device["id"], "order": 1,
                   "type": "primary", "temp": 20.0, "days": 0, "control": "beer"}],
            headers=headers,
        )
        r = app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
        assert r.status_code == 400

    def test_poll_step_with_empty_control_returns_bare_r(self, app_client):
        """Matched step with control not in {beer, fridge} -> bare R, no target."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CP09")
        _link_device_to_batch(app_client, device["id"], batch_id)
        app_client.post(
            f"/batches/{batch_id}/fermentation-steps",
            json=[{"batchId": batch_id, "deviceId": device["id"], "order": 1,
                   "type": "primary", "temp": 20.0, "days": 7, "control": ""}],
            headers=headers,
        )
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        data = _poll(app_client, device["token"])
        assert data["mode"] == "R"
        assert data["target_temperature"] is None

    def test_replacing_steps_clears_active_flag(self, app_client):
        """A changed schedule requires explicit re-activation."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CP10")
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        app_client.post(
            f"/batches/{batch_id}/fermentation-steps",
            json=[{"batchId": batch_id, "deviceId": device["id"], "order": 1,
                   "type": "primary", "temp": 18.0, "days": 5, "control": "beer"}],
            headers=headers,
        )
        batch = app_client.get(f"/batches/{batch_id}", headers=headers).json()
        assert batch["chamberControlActive"] is False

    def test_poll_unassigned_device_ignores_other_batchs_step(self, app_client):
        """A device polling for chamber setpoint only matches steps assigned to it."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CP06")
        other_device = _create_device(app_client, "CP07")
        _link_device_to_batch(app_client, device["id"], batch_id)
        _create_steps(app_client, batch_id, other_device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        data = _poll(app_client, device["token"])
        assert data["mode"] == "R"


class TestTriggerTypeEarlyExit:
    """Event-driven early exit: triggered_at ends a step before its
    days window elapses; trigger_type='manual' steps never auto-time-out via
    days and only end via triggered_at (nothing sets it automatically
    today)."""

    def test_poll_ends_step_early_when_triggered_at_is_set(self, app_client):
        """Setting triggered_at directly on the current step advances polling
        to the next step's setpoint even though the days window hasn't
        elapsed yet."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CT01")
        _link_device_to_batch(app_client, device["id"], batch_id)
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        # Step 1 (order=1, control=beer, 7 days) is current right after
        # activation -- confirm that first, then mark it triggered.
        data = _poll(app_client, device["token"])
        assert data["mode"] == "B"

        fermentation_step_model = resolve_model("FermentationStep")
        db = create_session()
        try:
            step = (
                db.query(fermentation_step_model)
                .filter_by(batch_id=uuid.UUID(batch_id), order=1)
                .one()
            )
            step.triggered_at = datetime.now(UTC)
            db.commit()
        finally:
            db.remove()

        data = _poll(app_client, device["token"])
        assert data["mode"] == "F"
        assert data["target_temperature"] == 18.0

    def test_poll_advances_normally_via_days_timeout_when_triggered_at_stays_null(
        self, app_client
    ):
        """Without triggered_at, the days-window timeout must still govern
        step transitions."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CT02")
        _link_device_to_batch(app_client, device["id"], batch_id)
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        # Backdate step 1 so its 7-day window has elapsed; step 2 should
        # now be current via the ordinary days-timeout path.
        fermentation_step_model = resolve_model("FermentationStep")
        db = create_session()
        try:
            step1 = (
                db.query(fermentation_step_model)
                .filter_by(batch_id=uuid.UUID(batch_id), order=1)
                .one()
            )
            step1.date = date.today() - timedelta(days=8)
            step2 = (
                db.query(fermentation_step_model)
                .filter_by(batch_id=uuid.UUID(batch_id), order=2)
                .one()
            )
            step2.date = date.today()
            db.commit()
        finally:
            db.remove()

        data = _poll(app_client, device["token"])
        assert data["mode"] == "F"
        assert data["target_temperature"] == 18.0

    def test_poll_manual_step_never_times_out_via_days(self, app_client):
        """A trigger_type='manual' step stays current indefinitely via the
        days window -- only triggered_at can end it."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CT03")
        _link_device_to_batch(app_client, device["id"], batch_id)
        app_client.post(
            f"/batches/{batch_id}/fermentation-steps",
            json=[{"batchId": batch_id, "deviceId": device["id"], "order": 1,
                   "type": "primary", "temp": 20.0, "days": 1, "control": "beer",
                   "triggerType": "manual"}],
            headers=headers,
        )
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        fermentation_step_model = resolve_model("FermentationStep")
        db = create_session()
        try:
            step = db.query(fermentation_step_model).filter_by(batch_id=uuid.UUID(batch_id)).one()
            # Push the step's date+days window far into the past -- a
            # day_offset step would have timed out (and auto-deactivated)
            # long ago, but a manual step must still be current.
            step.date = date.today() - timedelta(days=100)
            db.commit()
        finally:
            db.remove()

        data = _poll(app_client, device["token"])
        assert data["mode"] == "B"
        assert data["target_temperature"] == 20.0
        batch = app_client.get(f"/batches/{batch_id}", headers=headers).json()
        assert batch["chamberControlActive"] is True

    def test_poll_manual_step_ends_via_triggered_at(self, app_client):
        """A manual step does end once triggered_at is set."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "CT04")
        _link_device_to_batch(app_client, device["id"], batch_id)
        app_client.post(
            f"/batches/{batch_id}/fermentation-steps",
            json=[
                {"batchId": batch_id, "deviceId": device["id"], "order": 1,
                 "type": "primary", "temp": 20.0, "days": 30, "control": "beer",
                 "triggerType": "manual"},
                {"batchId": batch_id, "deviceId": device["id"], "order": 2,
                 "type": "secondary", "temp": 18.0, "days": 14, "control": "fridge"},
            ],
            headers=headers,
        )
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        fermentation_step_model = resolve_model("FermentationStep")
        db = create_session()
        try:
            step = (
                db.query(fermentation_step_model)
                .filter_by(batch_id=uuid.UUID(batch_id), order=1)
                .one()
            )
            step.triggered_at = datetime.now(UTC)
            db.commit()
        finally:
            db.remove()

        data = _poll(app_client, device["token"])
        assert data["mode"] == "F"
        assert data["target_temperature"] == 18.0


def test_activate_computes_date_for_manual_and_default_steps_alike(app_client):
    """The activation cascade (date computed per step) is unaffected by
    trigger_type -- both manual and terminal_gravity steps get a date."""
    truncate_database()
    batch_id = _create_batch(app_client)
    device = _create_device(app_client, "CT05")
    app_client.post(
        f"/batches/{batch_id}/fermentation-steps",
        json=[
            {"batchId": batch_id, "deviceId": device["id"], "order": 1,
             "type": "primary", "temp": 20.0, "days": 7, "control": "beer",
             "triggerType": "manual"},
            {"batchId": batch_id, "deviceId": device["id"], "order": 2,
             "type": "secondary", "temp": 18.0, "days": 14, "control": "fridge",
             "triggerType": "terminal_gravity"},
        ],
        headers=headers,
    )
    r = app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
    assert r.status_code == 200
    steps = r.json()
    assert steps[0]["date"] == date.today().isoformat()
    assert steps[1]["date"] == (date.today() + timedelta(days=7)).isoformat()



class TestPerStepRoutes:
    """delete_by_id / restore_step / advance_step -- per-step-scoped routes,
    distinct from the bulk /fermentation-steps, /fermentation-steps/restore endpoints above."""

    def test_delete_single_step(self, app_client):
        """DELETE /fermentation-steps/{step_id} soft-deletes only that step; the sibling
        step stays visible."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "PS01")
        steps = _create_steps(app_client, batch_id, device["id"])

        url = f"/batches/{batch_id}/fermentation-steps/{steps[0]['id']}"
        r = app_client.delete(url, headers=headers)
        assert r.status_code == 204

        remaining = app_client.get(
            f"/batches/{batch_id}/fermentation-steps", headers=headers
        ).json()
        assert len(remaining) == 1
        assert remaining[0]["id"] == steps[1]["id"]

    def test_delete_nonexistent_step_returns_404(self, app_client):
        """Deleting a step_id that doesn't exist (or belongs to another batch)
        returns 404."""
        truncate_database()
        batch_id = _create_batch(app_client)
        r = app_client.delete(
            f"/batches/{batch_id}/fermentation-steps/00000000-0000-0000-0000-000000000000",
            headers=headers,
        )
        assert r.status_code == 404

    def test_restore_non_deleted_step_returns_404(self, app_client):
        """Restoring a step that was never deleted returns 404."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "PS02")
        steps = _create_steps(app_client, batch_id, device["id"])

        r = app_client.post(
            f"/batches/{batch_id}/fermentation-steps/{steps[0]['id']}/restore", headers=headers
        )
        assert r.status_code == 404

    def test_advance_fires_triggered_at_for_any_trigger_type(self, app_client):
        """advance_step ends the current step regardless of trigger_type."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "PS05")
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        r = app_client.post(f"/batches/{batch_id}/fermentation-steps/advance", headers=headers)
        assert r.status_code == 200
        result = r.json()
        assert result["order"] == 1
        assert result["triggeredAt"] is not None

    def test_advance_400_when_not_under_active_chamber_control(self, app_client):
        """Advancing a batch that was never activated returns 400."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "PS06")
        _create_steps(app_client, batch_id, device["id"])

        r = app_client.post(f"/batches/{batch_id}/fermentation-steps/advance", headers=headers)
        assert r.status_code == 400

    def test_advance_on_soft_deleted_batch_returns_404(self, app_client):
        """Advancing the schedule of a soft-deleted batch is rejected — a
        deleted batch must not still have its schedule mutable."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "PS07")
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
        assert app_client.delete(f"/batches/{batch_id}", headers=headers).status_code == 204

        r = app_client.post(f"/batches/{batch_id}/fermentation-steps/advance", headers=headers)
        assert r.status_code == 404

    def test_advance_400_when_no_current_step_matches(self, app_client):
        """Activated, but every step has already ended (triggered) -- 400."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "PS07")
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        fermentation_step_model = resolve_model("FermentationStep")
        db = create_session()
        try:
            for step in db.query(fermentation_step_model).filter_by(batch_id=uuid.UUID(batch_id)):
                step.triggered_at = datetime.now(UTC)
            db.commit()
        finally:
            db.remove()

        r = app_client.post(f"/batches/{batch_id}/fermentation-steps/advance", headers=headers)
        assert r.status_code == 400

    def test_advance_400_before_first_step_starts(self, app_client):
        """Activated, but the first step's start date is in the future -- 400."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "PS08")
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        fermentation_step_model = resolve_model("FermentationStep")
        db = create_session()
        try:
            for step in db.query(fermentation_step_model).filter_by(batch_id=uuid.UUID(batch_id)):
                step.date = date.today() + timedelta(days=5)
            db.commit()
        finally:
            db.remove()

        r = app_client.post(f"/batches/{batch_id}/fermentation-steps/advance", headers=headers)
        assert r.status_code == 400

    def test_advance_moves_ingest_resolution_to_next_step(self, app_client):
        """After advancing, a chamber poll resolves to the next step's setpoint."""
        truncate_database()
        batch_id = _create_batch(app_client)
        device = _create_device(app_client, "PS09")
        _link_device_to_batch(app_client, device["id"], batch_id)
        _create_steps(app_client, batch_id, device["id"])
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)

        data = _poll(app_client, device["token"])
        assert data["mode"] == "B"
        assert data["target_temperature"] == 20.0

        app_client.post(f"/batches/{batch_id}/fermentation-steps/advance", headers=headers)

        data = _poll(app_client, device["token"])
        assert data["mode"] == "F"
        assert data["target_temperature"] == 18.0
