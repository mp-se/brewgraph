# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for batch note endpoints — covers BatchNoteService and router."""
import uuid

from core.config import get_settings
from core.db import create_session
from oss.services.batch import BatchService
from oss.services.batch_note import BatchNote
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def _create_batch(app_client, brew_date: str = "2026-06-01") -> str:
    truncate_database()
    r = app_client.post(
        "/batches",
        json={"name": "Note Batch", "brewDate": brew_date},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# GET /batches/{id}/notes
# ---------------------------------------------------------------------------

def test_list_notes_empty(app_client):
    """GET /batches/{id}/notes returns [] when no notes exist."""
    batch_id = _create_batch(app_client)
    r = app_client.get(f"/batches/{batch_id}/notes", headers=headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


# ---------------------------------------------------------------------------
# POST /batches/{id}/notes
# ---------------------------------------------------------------------------

def test_create_note(app_client):
    """POST /batches/{id}/notes creates a note and returns 201."""
    batch_id = _create_batch(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Dry-hopped with 50g Citra"},
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["content"] == "Dry-hopped with 50g Citra"
    assert data["batchId"] == batch_id
    assert data["createdBy"] is None
    assert "id" in data
    assert "createdAt" in data
    assert "updatedAt" in data


def test_create_note_with_custom_timestamp(app_client):
    """POST accepts an explicit created_at within [brew_date, now]."""
    batch_id = _create_batch(app_client, brew_date="2026-06-01")
    r = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Primary fermentation started", "createdAt": "2026-06-02T10:00:00Z"},
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["createdAt"].startswith("2026-06-02")


def test_create_note_with_timezone_naive_timestamp(app_client):
    """POST accepts a created_at with no UTC offset instead of 500ing.

    Pydantic's `Optional[datetime]` on BatchNoteCreate has no offset constraint, so a
    client omitting the offset (unlike every other timestamp in this file, which all
    carry a trailing Z) produces a timezone-naive datetime. Comparing that directly
    against datetime.now(UTC) raises TypeError — surfaced as an unhandled 500, not the
    422 the future/before-brew-date checks intend. Regression for that gap.
    """
    batch_id = _create_batch(app_client, brew_date="2026-06-01")
    r = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "No offset on this one", "createdAt": "2026-06-02T10:00:00"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["createdAt"].startswith("2026-06-02")


def test_create_note_future_timestamp_rejected(app_client):
    """POST rejects created_at in the future with 422."""
    batch_id = _create_batch(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Future event", "createdAt": "2099-01-01T00:00:00Z"},
        headers=headers,
    )
    assert r.status_code == 422


def test_create_note_before_brew_date_rejected(app_client):
    """POST rejects created_at before batch brew_date with 422."""
    batch_id = _create_batch(app_client, brew_date="2026-06-01")
    r = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Too early", "createdAt": "2026-05-01T00:00:00Z"},
        headers=headers,
    )
    assert r.status_code == 422


def test_create_note_empty_content_rejected(app_client):
    """POST rejects empty content with 422."""
    batch_id = _create_batch(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": ""},
        headers=headers,
    )
    assert r.status_code == 422


def test_create_note_batch_not_found(app_client):
    """POST returns 404 for a non-existent batch."""
    truncate_database()
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = app_client.post(
        f"/batches/{fake_id}/notes",
        json={"content": "Ghost note"},
        headers=headers,
    )
    assert r.status_code == 404


def test_list_notes_ordered_by_created_at(app_client):
    """GET /notes returns notes in ascending created_at order."""
    batch_id = _create_batch(app_client, brew_date="2026-06-01")
    app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Second", "createdAt": "2026-06-03T12:00:00Z"},
        headers=headers,
    )
    app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "First", "createdAt": "2026-06-02T08:00:00Z"},
        headers=headers,
    )
    r = app_client.get(f"/batches/{batch_id}/notes", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["content"] == "First"
    assert items[1]["content"] == "Second"


# ---------------------------------------------------------------------------
# PATCH /batches/{id}/notes/{note_id}
# ---------------------------------------------------------------------------

def test_update_note_content(app_client):
    """PATCH updates note content and bumps updated_at."""
    batch_id = _create_batch(app_client)
    note_id = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Original text"},
        headers=headers,
    ).json()["id"]

    r = app_client.patch(
        f"/batches/{batch_id}/notes/{note_id}",
        json={"content": "Updated text"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["content"] == "Updated text"


def test_update_note_not_found(app_client):
    """PATCH returns 404 for non-existent note."""
    batch_id = _create_batch(app_client)
    fake_id = "00000000-0000-0000-0000-000000000001"
    r = app_client.patch(
        f"/batches/{batch_id}/notes/{fake_id}",
        json={"content": "Ghost"},
        headers=headers,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /batches/{id}/notes/{note_id}
# ---------------------------------------------------------------------------

def test_delete_note(app_client):
    """DELETE removes note and returns 204."""
    batch_id = _create_batch(app_client)
    note_id = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "To be deleted"},
        headers=headers,
    ).json()["id"]

    r = app_client.delete(f"/batches/{batch_id}/notes/{note_id}", headers=headers)
    assert r.status_code == 204

    notes = app_client.get(f"/batches/{batch_id}/notes", headers=headers).json()["items"]
    assert len(notes) == 0


def test_delete_note_not_found(app_client):
    """DELETE returns 404 for non-existent note."""
    batch_id = _create_batch(app_client)
    fake_id = "00000000-0000-0000-0000-000000000002"
    r = app_client.delete(f"/batches/{batch_id}/notes/{fake_id}", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /batches/{id}/notes/{note_id}/restore
# ---------------------------------------------------------------------------

def test_restore_note_not_deleted_returns_404(app_client):
    """POST .../restore on a note that isn't deleted returns 404."""
    batch_id = _create_batch(app_client)
    note_id = app_client.post(
        f"/batches/{batch_id}/notes", json={"content": "Never deleted"}, headers=headers,
    ).json()["id"]
    r = app_client.post(f"/batches/{batch_id}/notes/{note_id}/restore", headers=headers)
    assert r.status_code == 404


def test_restore_note_not_found(app_client):
    """POST .../restore on a nonexistent note returns 404."""
    batch_id = _create_batch(app_client)
    fake_id = "00000000-0000-0000-0000-000000000003"
    r = app_client.post(f"/batches/{batch_id}/notes/{fake_id}/restore", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Cascade independence — BatchNote.deleted_at vs Batch.deleted_at
# ---------------------------------------------------------------------------

class TestCascadeIndependence:
    """BatchNote.deleted_at is independent of Batch.deleted_at in both directions."""

    def test_batch_soft_delete_does_not_touch_notes(self, app_client):
        """Soft-deleting a batch leaves an existing note's deleted_at untouched."""
        batch_id = _create_batch(app_client)
        note_id = app_client.post(
            f"/batches/{batch_id}/notes",
            json={"content": "Survives batch delete"},
            headers=headers,
        ).json()["id"]

        session = create_session()
        BatchService(session).soft_delete(uuid.UUID(batch_id))
        note = session.get(BatchNote, uuid.UUID(note_id))
        assert note.deleted_at is None

    def test_batch_restore_does_not_resurrect_individually_deleted_note(self, app_client):
        """Restoring a batch does not restore a note the user deleted themselves."""
        batch_id = _create_batch(app_client)
        note_id = app_client.post(
            f"/batches/{batch_id}/notes",
            json={"content": "Deleted by user"},
            headers=headers,
        ).json()["id"]
        r = app_client.delete(f"/batches/{batch_id}/notes/{note_id}", headers=headers)
        assert r.status_code == 204

        session = create_session()
        batch_service = BatchService(session)
        batch_service.soft_delete(uuid.UUID(batch_id))
        batch_service.restore(uuid.UUID(batch_id))

        note = session.get(BatchNote, uuid.UUID(note_id))
        assert note.deleted_at is not None
        assert app_client.get(f"/batches/{batch_id}/notes", headers=headers).json()["items"] == []


# ---------------------------------------------------------------------------
# Diacetyl/VDK confirmation gate (forced-diacetyl test notes)
# ---------------------------------------------------------------------------

def _create_batch_with_manual_step(app_client):
    """Batch with a single active manual-trigger fermentation step."""
    batch_id = _create_batch(app_client)
    app_client.post(
        f"/batches/{batch_id}/fermentation-steps",
        json=[{
            "batchId": batch_id, "order": 1, "type": "diacetyl_rest",
            "control": "beer", "temp": 20.0, "days": 5, "triggerType": "manual",
        }],
        headers=headers,
    )
    app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
    return batch_id


def test_diacetyl_test_pass_fires_active_manual_step(app_client):
    """A diacetyl_test note with test_result=pass fires triggered_at on the
    batch's currently-active manual step."""
    batch_id = _create_batch_with_manual_step(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Forced diacetyl test", "noteType": "diacetyl_test", "testResult": "pass"},
        headers=headers,
    )
    assert r.status_code == 201
    steps = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers).json()
    assert steps[0]["triggeredAt"] is not None


def test_diacetyl_test_fail_does_not_fire_step(app_client):
    """A diacetyl_test note with test_result=fail leaves triggered_at null."""
    batch_id = _create_batch_with_manual_step(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Forced diacetyl test", "noteType": "diacetyl_test", "testResult": "fail"},
        headers=headers,
    )
    assert r.status_code == 201
    steps = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers).json()
    assert steps[0]["triggeredAt"] is None


def test_diacetyl_test_inconclusive_does_not_fire_step(app_client):
    """A diacetyl_test note with test_result=inconclusive leaves triggered_at null."""
    batch_id = _create_batch_with_manual_step(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/notes",
        json={
            "content": "Forced diacetyl test",
            "noteType": "diacetyl_test",
            "testResult": "inconclusive",
        },
        headers=headers,
    )
    assert r.status_code == 201
    steps = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers).json()
    assert steps[0]["triggeredAt"] is None


def test_diacetyl_test_invalid_result_rejected(app_client):
    """An unknown test_result value is rejected with 422."""
    batch_id = _create_batch_with_manual_step(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/notes",
        json={
            "content": "Forced diacetyl test",
            "noteType": "diacetyl_test",
            "testResult": "maybe",
        },
        headers=headers,
    )
    assert r.status_code == 422


def test_test_result_without_note_type_rejected(app_client):
    """test_result without note_type='diacetyl_test' is rejected with 422."""
    batch_id = _create_batch(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Odd note", "testResult": "pass"},
        headers=headers,
    )
    assert r.status_code == 422


def test_ordinary_note_unaffected_by_diacetyl_fields(app_client):
    """An ordinary note (no note_type) behaves exactly as before."""
    batch_id = _create_batch(app_client)
    r = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Just a note"},
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["noteType"] is None
    assert data["testResult"] is None


def test_restore_undoes_a_note_delete(app_client):
    """POST /batches/{id}/notes/{noteId}/restore brings a deleted note back."""
    batch_id = _create_batch(app_client)
    note = app_client.post(
        f"/batches/{batch_id}/notes", json={"content": "Keep me"}, headers=headers
    ).json()

    assert app_client.delete(
        f"/batches/{batch_id}/notes/{note['id']}", headers=headers
    ).status_code == 204
    assert app_client.get(f"/batches/{batch_id}/notes", headers=headers).json()["items"] == []

    r = app_client.post(
        f"/batches/{batch_id}/notes/{note['id']}/restore", headers=headers
    )
    assert r.status_code == 200
    listed = app_client.get(f"/batches/{batch_id}/notes", headers=headers).json()["items"]
    assert [n["content"] for n in listed] == ["Keep me"]


def test_restore_a_live_note_is_404(app_client):
    """A note that was never deleted cannot be restored."""
    batch_id = _create_batch(app_client)
    note = app_client.post(
        f"/batches/{batch_id}/notes", json={"content": "Here"}, headers=headers
    ).json()
    r = app_client.post(f"/batches/{batch_id}/notes/{note['id']}/restore", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /batches/{id}/notes/{noteId} — test_result amendment
# ---------------------------------------------------------------------------


def test_amend_note_to_pass_fires_gate_once(app_client):
    """Amending a note's test_result from fail/inconclusive/null into pass
    fires confirm_diacetyl_pass exactly on the transition into pass."""
    batch_id = _create_batch_with_manual_step(app_client)
    note = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Diacetyl check", "noteType": "diacetyl_test", "testResult": "fail"},
        headers=headers,
    ).json()
    steps = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers).json()
    assert steps[0]["triggeredAt"] is None

    r = app_client.patch(
        f"/batches/{batch_id}/notes/{note['id']}",
        json={"testResult": "pass", "noteType": "diacetyl_test"},
        headers=headers,
    )
    assert r.status_code == 200
    steps = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers).json()
    assert steps[0]["triggeredAt"] is not None


def test_content_only_patch_on_existing_pass_does_not_refire(app_client):
    """A content-only PATCH on a note already holding test_result=pass must
    not re-fire confirm_diacetyl_pass (triggered_at stays the same value,
    no duplicate side effect)."""
    batch_id = _create_batch_with_manual_step(app_client)
    note = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Diacetyl check", "noteType": "diacetyl_test", "testResult": "pass"},
        headers=headers,
    ).json()
    steps = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers).json()
    triggered_at_before = steps[0]["triggeredAt"]
    assert triggered_at_before is not None

    r = app_client.patch(
        f"/batches/{batch_id}/notes/{note['id']}",
        json={"content": "Diacetyl check (typo fixed)"},
        headers=headers,
    )
    assert r.status_code == 200
    steps = app_client.get(f"/batches/{batch_id}/fermentation-steps", headers=headers).json()
    assert steps[0]["triggeredAt"] == triggered_at_before


def test_amend_pass_to_fail_leaves_triggered_at_and_later_steps_alone(app_client):
    """Amending pass -> fail on a step whose triggered_at is already set must
    leave that stamp, and every later step's effective_start, unchanged."""
    batch_id = _create_batch_with_manual_step(app_client)
    note = app_client.post(
        f"/batches/{batch_id}/notes",
        json={"content": "Diacetyl check", "noteType": "diacetyl_test", "testResult": "pass"},
        headers=headers,
    ).json()
    steps_before = app_client.get(
        f"/batches/{batch_id}/fermentation-steps", headers=headers
    ).json()
    assert steps_before[0]["triggeredAt"] is not None

    r = app_client.patch(
        f"/batches/{batch_id}/notes/{note['id']}",
        json={"testResult": "fail", "noteType": "diacetyl_test"},
        headers=headers,
    )
    assert r.status_code == 200
    steps_after = app_client.get(
        f"/batches/{batch_id}/fermentation-steps", headers=headers
    ).json()
    # effective_start is not part of the API response; asserting the full
    # step list is unchanged (dates, triggeredAt) is the available proxy for
    # "no later step's effective_start was rewritten".
    assert steps_after == steps_before


def test_patch_note_test_result_without_note_type_rejected(app_client):
    """The 422 validator on update matches create: test_result set without
    note_type='diacetyl_test' is rejected."""
    batch_id = _create_batch(app_client)
    note = app_client.post(
        f"/batches/{batch_id}/notes", json={"content": "Just a note"}, headers=headers
    ).json()
    r = app_client.patch(
        f"/batches/{batch_id}/notes/{note['id']}",
        json={"testResult": "pass"},
        headers=headers,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Cross-batch ownership scoping — note_id resolved through the wrong batch's URL
# ---------------------------------------------------------------------------

def _create_batch_no_truncate(app_client, brew_date: str = "2026-06-01") -> str:
    """Like `_create_batch`, but without the truncate — for tests that need two
    live batches at once (`_create_batch` wipes the database on every call)."""
    r = app_client.post(
        "/batches",
        json={"name": "Note Batch", "brewDate": brew_date},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_batch_with_manual_step_no_truncate(app_client):
    """Like `_create_batch_with_manual_step`, but without the truncate."""
    batch_id = _create_batch_no_truncate(app_client)
    app_client.post(
        f"/batches/{batch_id}/fermentation-steps",
        json=[{
            "batchId": batch_id, "order": 1, "type": "diacetyl_rest",
            "control": "beer", "temp": 20.0, "days": 5, "triggerType": "manual",
        }],
        headers=headers,
    )
    app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
    return batch_id


def test_patch_note_through_wrong_batch_url_is_404(app_client):
    """A note created on batch A cannot be edited through batch B's URL."""
    truncate_database()
    batch_a = _create_batch_no_truncate(app_client)
    batch_b = _create_batch_no_truncate(app_client)
    note = app_client.post(
        f"/batches/{batch_a}/notes", json={"content": "Batch A's note"}, headers=headers,
    ).json()

    r = app_client.patch(
        f"/batches/{batch_b}/notes/{note['id']}",
        json={"content": "Hijacked"},
        headers=headers,
    )
    assert r.status_code == 404


def test_delete_note_through_wrong_batch_url_is_404(app_client):
    """A note created on batch A cannot be deleted through batch B's URL."""
    truncate_database()
    batch_a = _create_batch_no_truncate(app_client)
    batch_b = _create_batch_no_truncate(app_client)
    note = app_client.post(
        f"/batches/{batch_a}/notes", json={"content": "Batch A's note"}, headers=headers,
    ).json()

    r = app_client.delete(f"/batches/{batch_b}/notes/{note['id']}", headers=headers)
    assert r.status_code == 404
    listed = app_client.get(f"/batches/{batch_a}/notes", headers=headers).json()["items"]
    assert len(listed) == 1


def test_restore_note_through_wrong_batch_url_is_404(app_client):
    """A note deleted on batch A cannot be restored through batch B's URL."""
    truncate_database()
    batch_a = _create_batch_no_truncate(app_client)
    batch_b = _create_batch_no_truncate(app_client)
    note = app_client.post(
        f"/batches/{batch_a}/notes", json={"content": "Batch A's note"}, headers=headers,
    ).json()
    assert app_client.delete(
        f"/batches/{batch_a}/notes/{note['id']}", headers=headers
    ).status_code == 204

    r = app_client.post(f"/batches/{batch_b}/notes/{note['id']}/restore", headers=headers)
    assert r.status_code == 404


def test_amend_note_to_pass_through_wrong_batch_url_does_not_fire_wrong_batch_gate(app_client):
    """The concrete exploit this scoping check closes: PATCHing batch A's
    diacetyl-test note through batch B's URL must 404, not fire batch B's
    manual fermentation step."""
    truncate_database()
    batch_a = _create_batch_with_manual_step_no_truncate(app_client)
    batch_b = _create_batch_with_manual_step_no_truncate(app_client)
    note = app_client.post(
        f"/batches/{batch_a}/notes",
        json={"content": "Diacetyl check", "noteType": "diacetyl_test", "testResult": "fail"},
        headers=headers,
    ).json()

    r = app_client.patch(
        f"/batches/{batch_b}/notes/{note['id']}",
        json={"testResult": "pass", "noteType": "diacetyl_test"},
        headers=headers,
    )
    assert r.status_code == 404

    steps_b = app_client.get(f"/batches/{batch_b}/fermentation-steps", headers=headers).json()
    assert steps_b[0]["triggeredAt"] is None
