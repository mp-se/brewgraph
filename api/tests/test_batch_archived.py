# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for the `archived` batch status — see spec-data-model.md §5.7 "Archiving".

Covers: reachability from either fermenting or packaged, read-only enforcement
on the batch itself and its sub-resources, chamber-control deactivation on
archive, and the live-state (not stored-snapshot) un-archive derivation.
"""
from core.config import get_settings
from tests.conftest import DEVICE_DEFAULTS, truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BATCH_DATA = {"name": "Archive Test Batch", "og": 1.050, "fg": 1.010}


def test_init():
    """Reset database state before test scenarios."""
    truncate_database()


def _create_batch(app_client, overrides=None) -> dict:
    data = {**BATCH_DATA, **(overrides or {})}
    r = app_client.post("/batches", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


def _create_device(app_client, chip_id: str) -> dict:
    data = {"name": f"Dev {chip_id}", "deviceType": "chamber", "chipId": chip_id, **DEVICE_DEFAULTS}
    r = app_client.post("/devices", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


def _create_vessel(app_client, batch_id: str) -> dict:
    data = {
        "batchId": batch_id,
        "vesselType": "keg",
        "name": "Keg 1",
        "fillDate": "2026-05-01",
        "totalVolume": 19.0,
        "volumeRemaining": 19.0,
        "status": "filled",
    }
    r = app_client.post("/vessels", json=data, headers=headers)
    assert r.status_code == 201
    return r.json()


# --- reachability ---

def test_archive_from_fermenting(app_client):
    """A fermenting batch can be archived directly, with no packaging step."""
    test_init()
    batch = _create_batch(app_client)
    r = app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "archived"


def test_archive_from_packaged(app_client):
    """A packaged batch can be archived too."""
    test_init()
    batch = _create_batch(app_client)
    app_client.patch(f"/batches/{batch['id']}", json={"status": "packaged"}, headers=headers)
    r = app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "archived"


# --- chamber control cleanup ---

def test_archiving_fermenting_batch_deactivates_chamber_control(app_client):
    """Archiving a batch under active chamber control ends that control in the
    same request — an archived batch is not under active control by definition."""
    test_init()
    batch = _create_batch(app_client)
    batch_id = batch["id"]
    device = _create_device(app_client, "ARCHCC01")
    app_client.patch(f"/devices/{device['id']}", json={"batchId": batch_id}, headers=headers)
    app_client.post(
        f"/batches/{batch_id}/fermentation-steps",
        json=[{"batchId": batch_id, "deviceId": device["id"], "order": 1, "type": "primary",
               "temp": 20.0, "days": 7, "control": "beer"}],
        headers=headers,
    )
    activated = app_client.post(f"/batches/{batch_id}/fermentation-steps/activate", headers=headers)
    assert activated.status_code == 200

    r = app_client.get(f"/batches/{batch_id}", headers=headers)
    assert r.json()["chamberControlActive"] is True

    r = app_client.patch(f"/batches/{batch_id}", json={"status": "archived"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["chamberControlActive"] is False


# --- read-only enforcement ---

def test_archived_batch_rejects_field_edits(app_client):
    """Any field but `status` is rejected (400) once a batch is archived."""
    test_init()
    batch = _create_batch(app_client)
    app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=headers)

    r = app_client.patch(
        f"/batches/{batch['id']}", json={"name": "Renamed"}, headers=headers
    )
    assert r.status_code == 400


def test_archived_batch_rejects_new_notes(app_client):
    """A note cannot be added to an archived batch — 404, matching a
    soft-deleted batch's sub-resource rejection."""
    test_init()
    batch = _create_batch(app_client)
    app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=headers)

    r = app_client.post(
        f"/batches/{batch['id']}/notes", json={"content": "late note"}, headers=headers
    )
    assert r.status_code == 404


def test_archived_batch_rejects_new_dry_hops(app_client):
    """A dry hop cannot be added to an archived batch — 404."""
    test_init()
    batch = _create_batch(app_client)
    app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=headers)

    r = app_client.post(
        f"/batches/{batch['id']}/dry-hops",
        json=[{"name": "Citra", "amount": 50.0, "triggerMethod": "hours_before_completion",
               "triggerHoursBefore": 24}],
        headers=headers,
    )
    assert r.status_code == 404


def test_archived_batch_rejects_new_vessel_link(app_client):
    """A vessel cannot be newly linked to an archived batch — 409."""
    test_init()
    batch = _create_batch(app_client)
    app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=headers)

    r = app_client.post(
        "/vessels",
        json={
            "batchId": batch["id"], "vesselType": "keg", "name": "Keg 1",
            "fillDate": "2026-05-01", "totalVolume": 19.0, "volumeRemaining": 19.0,
        },
        headers=headers,
    )
    assert r.status_code == 409


def test_rating_allowed_while_archived(app_client):
    """`rating` is the one field still settable once packaged or archived."""
    test_init()
    batch = _create_batch(app_client)
    app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=headers)

    r = app_client.patch(f"/batches/{batch['id']}", json={"rating": 4}, headers=headers)
    assert r.status_code == 200
    assert r.json()["rating"] == 4


# --- un-archiving: live-state derivation, not stored history ---

def test_unarchive_without_vessel_restores_fermenting(app_client):
    """A batch archived straight from fermenting, with no vessel ever
    connected, un-archives to fermenting."""
    test_init()
    batch = _create_batch(app_client)
    app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=headers)

    r = app_client.patch(f"/batches/{batch['id']}", json={"status": "fermenting"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "fermenting"


def test_unarchive_with_connected_vessel_restores_packaged(app_client):
    """A batch with a currently-connected vessel un-archives to packaged,
    regardless of the literal status value the client sent."""
    test_init()
    batch = _create_batch(app_client)
    _create_vessel(app_client, batch["id"])
    app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=headers)

    # Deliberately send "fermenting" -- the server must ignore it and derive
    # "packaged" from the live vessel connection instead.
    r = app_client.patch(f"/batches/{batch['id']}", json={"status": "fermenting"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "packaged"


def test_unarchive_after_vessel_detached_restores_fermenting(app_client):
    """A batch once packaged, whose vessel was later emptied and detached
    before archiving, un-archives to fermenting -- live state, not a replayed
    snapshot of what it used to be."""
    test_init()
    batch = _create_batch(app_client)
    vessel = _create_vessel(app_client, batch["id"])
    app_client.patch(f"/batches/{batch['id']}", json={"status": "packaged"}, headers=headers)
    # Empty and detach the vessel.
    app_client.patch(f"/vessels/{vessel['id']}", json={"batchId": None}, headers=headers)

    app_client.patch(f"/batches/{batch['id']}", json={"status": "archived"}, headers=headers)
    r = app_client.patch(f"/batches/{batch['id']}", json={"status": "packaged"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "fermenting"
