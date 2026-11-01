# Copyright (c) 2024-2026 Magnus Persson. All rights reserved.
"""Planned ABV follows the planned gravities, and the measured ABV is computed on read."""
from core.config import get_settings
from tests.conftest import truncate_database

headers = {"Authorization": "Bearer " + get_settings().api_key.get_secret_value()}


def _create(app_client, **fields):
    """Create a batch and return its id."""
    r = app_client.post("/batches", json={"name": "ABV batch", **fields}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _patch(app_client, batch_id, **fields):
    """Patch a batch and return the response body."""
    r = app_client.patch(f"/batches/{batch_id}", json=fields, headers=headers)
    assert r.status_code == 200
    return r.json()


def test_changing_gravity_recalculates_abv(app_client):
    """Changing og or fg with both set stores the recalculated planned ABV."""
    truncate_database()
    batch_id = _create(app_client, og=1.050)
    assert _patch(app_client, batch_id, fg=1.008)["abv"] == 5.5
    assert _patch(app_client, batch_id, og=1.060)["abv"] == 6.8


def test_explicit_abv_wins_over_recalculation(app_client):
    """An abv in the same request is stored as sent."""
    truncate_database()
    batch_id = _create(app_client, og=1.050, fg=1.010)
    assert _patch(app_client, batch_id, og=1.060, abv=7.0)["abv"] == 7.0


def test_unchanged_gravity_keeps_abv(app_client):
    """A request that does not change og or fg leaves an entered or imported abv alone."""
    truncate_database()
    batch_id = _create(app_client, og=1.050, fg=1.010, abv=4.9)
    assert _patch(app_client, batch_id, name="Renamed")["abv"] == 4.9
    assert _patch(app_client, batch_id, og=1.050, fg=1.010)["abv"] == 4.9
    assert _patch(app_client, batch_id, abv=5.5)["abv"] == 5.5


def test_one_gravity_alone_does_not_set_abv(app_client):
    """With only one planned gravity there is nothing to calculate."""
    truncate_database()
    batch_id = _create(app_client)
    assert _patch(app_client, batch_id, og=1.050)["abv"] is None


def test_measured_abv_is_computed_from_measured_gravities(app_client):
    """abvMeasured is null until both measured gravities exist and is never stored."""
    truncate_database()
    batch_id = _create(app_client, og=1.050)
    assert _patch(app_client, batch_id, fg=1.008)["abvMeasured"] is None
    assert _patch(app_client, batch_id, ogMeasured=1.048)["abvMeasured"] is None
    body = _patch(app_client, batch_id, fgMeasured=1.006)
    assert body["abvMeasured"] == 5.5
    assert body["abv"] == 5.5


def test_whole_form_patch_with_unchanged_abv_recalculates(app_client):
    """A client that repeats the stored abv while changing og still gets the recalculation."""
    truncate_database()
    batch_id = _create(app_client, og=1.050, fg=1.008, abv=5.5)
    body = _patch(app_client, batch_id, og=1.060, fg=1.008, abv=5.5)
    assert body["abv"] == 6.8
    assert _patch(app_client, batch_id, og=1.060, fg=1.008, abv=6.0)["abv"] == 6.0
