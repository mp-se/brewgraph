# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for fermentation step endpoints — covers FermentationStepService."""
import uuid

from sqlalchemy.orm import Session

from core.config import get_settings
from core.db import engine
from oss.schemas.fermentation_step import suggest_trigger_type
from oss.services.fermentation_step import FermentationStepService
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

def _create_batch(app_client) -> str:
    truncate_database()
    return app_client.post(
        "/batches", json={"name": "Step Batch", "status": "fermenting"}, headers=headers
    ).json()["id"]


def _steps(batch_id: str):
    """Build step payloads with the required batchId."""
    return [
        {"batchId": batch_id, "order": 1, "type": "primary", "temp": 20.0, "days": 7},
        {"batchId": batch_id, "order": 2, "type": "secondary", "temp": 18.0, "days": 14},
    ]


def test_list_fermentation_steps_empty(app_client):
    """GET /batches/{id}/fermentation-steps returns [] when no steps exist."""
    batch_id = _create_batch(app_client)
    r = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


def test_create_fermentation_steps(app_client):
    """POST /batches/{id}/fermentation-steps creates steps and returns them ordered."""
    batch_id = _create_batch(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/fermentation-steps", json=_steps(batch_id), headers=headers
    )
    assert r.status_code == 201
    data = r.json()
    assert len(data) == 2
    assert data[0]["order"] == 1
    assert data[1]["type"] == "secondary"


def test_create_fermentation_steps_replaces_existing(app_client):
    """POST /batches/{id}/fermentation-steps replaces existing steps (re-import works)."""
    batch_id = _create_batch(app_client)
    app_client.post(
        f"/batches/{batch_id}/fermentation-steps", json=_steps(batch_id), headers=headers
    )
    replacement = [
        {"batchId": batch_id, "order": 1, "type": "primary", "temp": 19.0, "days": 10},
    ]
    r = app_client.post(
        f"/batches/{batch_id}/fermentation-steps", json=replacement, headers=headers
    )
    assert r.status_code == 201
    data = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers).json()
    assert len(data) == 1
    assert data[0]["temp"] == 19.0
    assert data[0]["days"] == 10


def test_create_fermentation_steps_empty_list(app_client):
    """POST /batches/{id}/fermentation-steps with an empty list returns 400."""
    batch_id = _create_batch(app_client)
    r = app_client.post(f"/batches/{batch_id}/fermentation-steps", json=[], headers=headers)
    assert r.status_code == 400


def test_create_fermentation_steps_rejects_oversized_import(app_client):
    """A schedule import cannot allocate an unbounded replacement transaction."""
    batch_id = _create_batch(app_client)
    payload = [
        {"batchId": batch_id, "order": index, "type": "primary", "temp": 20.0, "days": 1}
        for index in range(1001)
    ]
    r = app_client.post(f"/batches/{batch_id}/fermentation-steps", json=payload, headers=headers)
    assert r.status_code == 422


def test_list_fermentation_steps_after_create(app_client):
    """GET /batches/{id}/fermentation-steps returns created steps in order."""
    batch_id = _create_batch(app_client)
    app_client.post(
        f"/batches/{batch_id}/fermentation-steps", json=_steps(batch_id), headers=headers
    )
    r = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["order"] == 1


def test_delete_fermentation_steps(app_client):
    """DELETE /batches/{id}/fermentation-steps removes all steps for the batch."""
    batch_id = _create_batch(app_client)
    app_client.post(
        f"/batches/{batch_id}/fermentation-steps", json=_steps(batch_id), headers=headers
    )
    r = app_client.delete(f"/batches/{batch_id}/fermentation-steps", headers=headers)
    assert r.status_code == 204
    remaining = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers).json()
    assert remaining == []


def test_delete_fermentation_steps_idempotent(app_client):
    """DELETE /batches/{id}/fermentation-steps on an already-empty batch returns 204."""
    batch_id = _create_batch(app_client)
    r = app_client.delete(f"/batches/{batch_id}/fermentation-steps", headers=headers)
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# POST /batches/{id}/fermentation-steps/restore
# ---------------------------------------------------------------------------

def test_fermentation_step_trigger_type_defaults(app_client):
    """New columns: trigger_type defaults to 'day_offset', triggered_at to null."""
    batch_id = _create_batch(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/fermentation-steps", json=_steps(batch_id), headers=headers
    )
    assert r.status_code == 201
    data = r.json()
    assert data[0]["triggerType"] == "day_offset"
    assert data[0]["triggeredAt"] is None
    assert data[1]["triggerType"] == "day_offset"
    assert data[1]["triggeredAt"] is None


def test_fermentation_step_trigger_type_accepts_explicit_value(app_client):
    """trigger_type can be set explicitly on create (e.g. 'manual')."""
    batch_id = _create_batch(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/fermentation-steps",
        json=[{"batchId": batch_id, "order": 1, "type": "primary", "temp": 20.0,
               "days": 7, "triggerType": "manual"}],
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()[0]["triggerType"] == "manual"


class TestSuggestTriggerType:
    """oss.schemas.fermentation_step.suggest_trigger_type — auto-suggest
    defaults for step template names, not wired into any auto-creation flow."""

    def test_primary_suggests_terminal_gravity(self):
        """A step template named 'Primary' suggests terminal_gravity."""
        assert suggest_trigger_type("Primary") == "terminal_gravity"

    def test_diacetyl_rest_suggests_day_offset(self):
        """A step template named 'Diacetyl rest' suggests day_offset."""
        assert suggest_trigger_type("Diacetyl rest") == "day_offset"

    def test_cold_crash_suggests_day_offset(self):
        """A step template named 'Cold crash' suggests day_offset."""
        assert suggest_trigger_type("Cold crash") == "day_offset"

    def test_unknown_name_defaults_to_day_offset(self):
        """An unrecognized step template name defaults to day_offset."""
        assert suggest_trigger_type("Some Unknown Step") == "day_offset"


# ---------------------------------------------------------------------------
# FermentationStepService.confirm_diacetyl_pass
# ---------------------------------------------------------------------------

class TestConfirmDiacetylPass:
    """Service-level tests for the diacetyl/VDK confirmation gate."""

    @staticmethod
    def _service():
        return FermentationStepService(Session(engine))

    def test_batch_not_under_chamber_control_returns_false(self, app_client):
        """A batch with no chamber control active never confirms a pass."""
        batch_id = _create_batch(app_client)
        app_client.post(
        f"/batches/{batch_id}/fermentation-steps", json=_steps(batch_id), headers=headers
    )
        svc = self._service()
        assert svc.confirm_diacetyl_pass(uuid.UUID(batch_id)) is False

    def test_no_matching_manual_step_returns_false(self, app_client):
        """A batch under chamber control with no manual step returns False."""
        batch_id = _create_batch(app_client)
        app_client.post(
        f"/batches/{batch_id}/fermentation-steps", json=_steps(batch_id), headers=headers
    )
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
        svc = self._service()
        assert svc.confirm_diacetyl_pass(uuid.UUID(batch_id)) is False

    def test_already_triggered_step_returns_false(self, app_client):
        """A manual step confirms once, then returns False on a second call."""
        batch_id = _create_batch(app_client)
        app_client.post(
            f"/batches/{batch_id}/fermentation-steps",
            json=[{"batchId": batch_id, "order": 1, "type": "diacetyl_rest",
                   "control": "beer", "temp": 20.0, "days": 5, "triggerType": "manual"}],
            headers=headers,
        )
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
        svc = self._service()
        assert svc.confirm_diacetyl_pass(uuid.UUID(batch_id)) is True
        assert svc.confirm_diacetyl_pass(uuid.UUID(batch_id)) is False

    def test_earlier_non_manual_step_still_current_is_noop(self, app_client):
        """The manual diacetyl step never becomes current while an earlier
        non-manual step is still within its own days window -- no-op."""
        batch_id = _create_batch(app_client)
        app_client.post(
            f"/batches/{batch_id}/fermentation-steps",
            json=[
                {"batchId": batch_id, "order": 1, "type": "primary", "control": "beer",
                 "temp": 20.0, "days": 5, "triggerType": "day_offset"},
                {"batchId": batch_id, "order": 2, "type": "diacetyl_rest", "control": "beer",
                 "temp": 20.0, "days": 5, "triggerType": "manual"},
            ],
            headers=headers,
        )
        app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
        svc = self._service()
        assert svc.confirm_diacetyl_pass(uuid.UUID(batch_id)) is False
        steps = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers).json()
        manual_step = next(s for s in steps if s["triggerType"] == "manual")
        assert manual_step["triggeredAt"] is None


def test_fermentation_step_date_round_trips(app_client):
    """A valid ISO date on create is stored and returned as the same date.

    date was a String(20) column; a client-supplied date now goes through the
    Date column type end to end.
    """
    batch_id = _create_batch(app_client)
    payload = _steps(batch_id)
    payload[0]["date"] = "2024-03-15"
    r = app_client.post(
        f"/batches/{batch_id}/fermentation-steps", json=payload, headers=headers
    )
    assert r.status_code == 201
    assert r.json()[0]["date"] == "2024-03-15"

    r = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers)
    assert r.json()[0]["date"] == "2024-03-15"


def test_fermentation_step_date_defaults_to_null(app_client):
    """A step created without a date has date: null, not an empty string.

    The old String(20) column defaulted new steps to "" (the frontend sent
    date: '' explicitly); the Date column can't hold that, so unset now means
    null all the way from the frontend payload through to the response.
    """
    batch_id = _create_batch(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/fermentation-steps", json=_steps(batch_id), headers=headers
    )
    assert r.status_code == 201
    assert r.json()[0]["date"] is None


def test_fermentation_step_date_rejects_malformed_value(app_client):
    """A malformed date is now rejected at the API instead of being stored as-is.

    The old String(20) column accepted any string up to 20 characters — a typo
    like "2024-13-45" or free text would be silently stored, and every reader
    of the field (activate/advance/diacetyl-confirm/chamber jobs) had to guard
    against it with a try/except around date.fromisoformat(). The Date column
    now makes that class of bad data impossible to write in the first place.
    """
    batch_id = _create_batch(app_client)
    payload = _steps(batch_id)
    payload[0]["date"] = "not-a-date"
    r = app_client.post(
        f"/batches/{batch_id}/fermentation-steps", json=payload, headers=headers
    )
    assert r.status_code == 422
