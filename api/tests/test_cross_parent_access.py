# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# pylint: disable=redefined-outer-name

"""A child id is honoured only under its own parent.

Nested routes carry two ids (``/batches/{batch_id}/notes/{note_id}``). The child must be
resolved *within* the parent in the path; quoting another parent's child id must find nothing
and change nothing.
"""
import pytest

from core.config import get_settings
from tests.conftest import app_client, truncate_database  # noqa: F401  # pylint: disable=unused-import

HDR = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def _batch(client, name):
    r = client.post("/batches", json={"name": name}, headers=HDR)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _vessel(client, name):
    r = client.post("/vessels", json={"name": name, "vesselType": "keg",
                                      "totalVolume": 19.0, "status": "clean"}, headers=HDR)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# (parent route, parent factory, child path, create payload, patch payload, field, new value)
READING_CASES = [
    ("batches", _batch, "gravity", {"gravity": 1.050}, {"gravity": 1.020}, "gravity"),
    ("batches", _batch, "pressure", {"pressure": 100.0}, {"pressure": 50.0}, "pressure"),
    ("batches", _batch, "temp", {"temperature": 20.0}, {"temperature": 5.0}, "temperature"),
    ("vessels", _vessel, "pressure", {"pressure": 100.0}, {"pressure": 50.0}, "pressure"),
    ("vessels", _vessel, "temp", {"temperature": 4.0}, {"temperature": 9.0}, "temperature"),
]


@pytest.mark.parametrize("parent,factory,kind,create,patch,field", READING_CASES)
def test_reading_patch_through_other_parent_is_not_found(
        app_client, parent, factory, kind, create, patch, field):  # noqa: F811
    """PATCH of a reading via a different parent returns 404 and leaves the reading alone."""
    truncate_database()
    owner, other = factory(app_client, "A"), factory(app_client, "B")
    r = app_client.post(f"/{parent}/{owner}/{kind}", json=create, headers=HDR)
    assert r.status_code == 201, r.text
    reading_id = r.json()["id"]

    denied = app_client.patch(f"/{parent}/{other}/{kind}/{reading_id}", json=patch, headers=HDR)
    assert denied.status_code == 404

    allowed = app_client.patch(f"/{parent}/{owner}/{kind}/{reading_id}", json=patch, headers=HDR)
    assert allowed.status_code == 200
    assert allowed.json()[field] == patch[field]


def _note(client, batch_id):
    r = client.post(f"/batches/{batch_id}/notes", json={"content": "keep me"}, headers=HDR)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_note_patch_delete_restore_through_other_batch(app_client):  # noqa: F811
    """A note cannot be edited, deleted or restored through another batch."""
    truncate_database()
    owner, other = _batch(app_client, "A"), _batch(app_client, "B")
    note_id = _note(app_client, owner)

    assert app_client.patch(f"/batches/{other}/notes/{note_id}",
                            json={"content": "hijacked"}, headers=HDR).status_code == 404
    assert app_client.delete(f"/batches/{other}/notes/{note_id}", headers=HDR).status_code == 404
    assert app_client.post(f"/batches/{other}/notes/{note_id}/restore",
                           headers=HDR).status_code == 404

    notes = app_client.get(f"/batches/{owner}/notes", headers=HDR).json()["items"]
    assert [n["content"] for n in notes] == ["keep me"]


def test_fermentation_step_delete_through_other_batch(app_client):  # noqa: F811
    """A fermentation step cannot be deleted through another batch."""
    truncate_database()
    owner, other = _batch(app_client, "A"), _batch(app_client, "B")
    r = app_client.post(f"/batches/{owner}/fermentation-steps", headers=HDR, json=[
        {"batchId": owner, "order": 1, "type": "primary", "temp": 20.0, "days": 7}])
    assert r.status_code in (200, 201), r.text
    steps = app_client.get(f"/batches/{owner}/fermentation-steps", headers=HDR).json()
    step_id = (steps["items"] if isinstance(steps, dict) else steps)[0]["id"]

    app_client.delete(f"/batches/{other}/fermentation-steps/{step_id}", headers=HDR)

    after = app_client.get(f"/batches/{owner}/fermentation-steps", headers=HDR).json()
    assert len(after["items"] if isinstance(after, dict) else after) == 1

