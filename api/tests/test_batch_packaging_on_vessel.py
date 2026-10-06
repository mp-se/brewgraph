# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Packaging follows the vessel: filling a keg or bottles packages the batch.

There is no POST /batches/{id}/package endpoint: fill date, conditioning days
and carbonation target are already fields on the batch form; putting beer
into a cellar vessel is what packaging *is*, so the transition follows the
vessel link.

`packaged` snapshots measured OG/FG from the batch's own readings, and it
unlocks `rating`.
"""
import uuid
from datetime import UTC, datetime, timedelta

from core.config import get_settings
from core.db import create_session
from core.models.registry import resolve_model
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def _create_batch(app_client, **overrides) -> str:
    payload = {"name": "Packaging Batch", "status": "fermenting", "volume": 19.0, **overrides}
    r = app_client.post("/batches", json=payload, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _create_clean_keg(app_client, name="Corny Keg") -> str:
    r = app_client.post("/vessels", json={
        "vesselType": "keg",
        "name": name,
        "fillDate": "2026-01-01",
        "totalVolume": 19.0,
        "volumeRemaining": 0.0,
        "status": "clean",
    }, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _get_batch(app_client, batch_id) -> dict:
    r = app_client.get(f"/batches/{batch_id}", headers=headers)
    assert r.status_code == 200
    return r.json()


def _add_gravity_readings(batch_id: str, values) -> None:
    """Write gravity readings directly, oldest first, so OG/FG have something to snapshot."""
    gravity_model = resolve_model("GravityReading")
    session = create_session()
    try:
        base = datetime.now(UTC) - timedelta(days=len(values))
        for offset, value in enumerate(values):
            session.add(gravity_model(
                batch_id=uuid.UUID(batch_id),
                gravity=value,
                temperature=20.0,
                excluded=False,
                created_at=base + timedelta(days=offset),
            ))
        session.commit()
    finally:
        session.close()


def test_assigning_a_keg_packages_the_batch(app_client):
    """Assigning a clean keg flips the batch to packaged and stamps the package date."""
    truncate_database()
    batch_id = _create_batch(app_client)
    keg_id = _create_clean_keg(app_client)

    r = app_client.patch(f"/vessels/{keg_id}", json={"batchId": batch_id}, headers=headers)
    assert r.status_code == 200

    batch = _get_batch(app_client, batch_id)
    assert batch["status"] == "packaged"
    assert batch["packageDate"] is not None


def test_creating_bottles_packages_the_batch(app_client):
    """Bottles are created already linked rather than assigned, and must package too.

    The two paths reach the batch differently, so which control the user clicked would
    otherwise decide whether the batch ever left `fermenting`.
    """
    truncate_database()
    batch_id = _create_batch(app_client)

    r = app_client.post("/vessels", json={
        "batchId": batch_id,
        "vesselType": "bottles",
        "name": "Bottles",
        "fillDate": "2026-02-02",
        "totalVolume": 9.9,
        "volumeRemaining": 9.9,
        "bottleCount": 30,
        "bottlesRemaining": 30,
        "bottleVolume": 0.33,
        "status": "filled",
    }, headers=headers)
    assert r.status_code == 201

    batch = _get_batch(app_client, batch_id)
    assert batch["status"] == "packaged"
    assert batch["packageDate"] == "2026-02-02"


def test_package_date_comes_from_the_vessel_fill_date(app_client):
    """The stamped date is the vessel's fill date, not today."""
    truncate_database()
    batch_id = _create_batch(app_client)
    r = app_client.post("/vessels", json={
        "vesselType": "keg", "name": "Keg", "fillDate": "2026-03-03",
        "totalVolume": 19.0, "volumeRemaining": 0.0, "status": "clean",
    }, headers=headers)
    keg_id = r.json()["id"]

    app_client.patch(f"/vessels/{keg_id}", json={"batchId": batch_id}, headers=headers)

    assert _get_batch(app_client, batch_id)["packageDate"] == "2026-03-03"


def test_packaging_snapshots_measured_og_and_fg(app_client):
    """First and last non-excluded readings are captured when the batch packages."""
    truncate_database()
    batch_id = _create_batch(app_client)
    _add_gravity_readings(batch_id, [1.050, 1.030, 1.012])
    keg_id = _create_clean_keg(app_client)

    app_client.patch(f"/vessels/{keg_id}", json={"batchId": batch_id}, headers=headers)

    batch = _get_batch(app_client, batch_id)
    assert batch["ogMeasured"] == 1.050
    assert batch["fgMeasured"] == 1.012


def test_a_second_vessel_does_not_restamp_or_resnapshot(app_client):
    """Adding another keg to an already-packaged batch changes nothing about it.

    The rule is fermenting-only precisely so this is a no-op: re-stamping the date on
    every keg would make the package date mean "most recent keg".
    """
    truncate_database()
    batch_id = _create_batch(app_client)
    _add_gravity_readings(batch_id, [1.050, 1.010])

    first_keg = _create_clean_keg(app_client, name="Keg 1")
    app_client.patch(f"/vessels/{first_keg}", json={"batchId": batch_id}, headers=headers)
    after_first = _get_batch(app_client, batch_id)

    # A later reading would change the snapshot if it were taken again.
    _add_gravity_readings(batch_id, [1.005])
    second_keg = _create_clean_keg(app_client, name="Keg 2")
    app_client.patch(f"/vessels/{second_keg}", json={"batchId": batch_id}, headers=headers)

    after_second = _get_batch(app_client, batch_id)
    assert after_second["packageDate"] == after_first["packageDate"]
    assert after_second["fgMeasured"] == after_first["fgMeasured"]


def test_manual_gravity_corrections_are_never_overwritten(app_client):
    """An OG/FG already set by hand survives packaging."""
    truncate_database()
    batch_id = _create_batch(app_client)
    _add_gravity_readings(batch_id, [1.050, 1.012])
    r = app_client.patch(f"/batches/{batch_id}",
                         json={"ogMeasured": 1.061, "fgMeasured": 1.009}, headers=headers)
    assert r.status_code == 200

    keg_id = _create_clean_keg(app_client)
    app_client.patch(f"/vessels/{keg_id}", json={"batchId": batch_id}, headers=headers)

    batch = _get_batch(app_client, batch_id)
    assert batch["ogMeasured"] == 1.061
    assert batch["fgMeasured"] == 1.009


def test_an_archived_batch_is_never_dragged_back_to_packaged(app_client):
    """Only a fermenting batch transitions — archived must stay archived."""
    truncate_database()
    batch_id = _create_batch(app_client)
    app_client.patch(f"/batches/{batch_id}", json={"status": "archived"}, headers=headers)
    keg_id = _create_clean_keg(app_client)

    app_client.patch(f"/vessels/{keg_id}", json={"batchId": batch_id}, headers=headers)

    assert _get_batch(app_client, batch_id)["status"] == "archived"


def test_emptying_a_keg_does_not_change_the_batch(app_client):
    """PATCH with batchId null empties the keg; the batch it left stays packaged."""
    truncate_database()
    batch_id = _create_batch(app_client)
    keg_id = _create_clean_keg(app_client)
    app_client.patch(f"/vessels/{keg_id}", json={"batchId": batch_id}, headers=headers)

    r = app_client.patch(f"/vessels/{keg_id}", json={"batchId": None}, headers=headers)
    assert r.status_code == 200

    assert _get_batch(app_client, batch_id)["status"] == "packaged"


def test_rating_is_unlocked_once_a_vessel_packages_the_batch(app_client):
    """Rating is rejected while fermenting and accepted after packaging.

    This is the second thing `packaged` gates, and the reason the transition could not
    simply be dropped along with the endpoint.
    """
    truncate_database()
    batch_id = _create_batch(app_client)

    rejected = app_client.patch(f"/batches/{batch_id}", json={"rating": 4}, headers=headers)
    assert rejected.status_code == 400

    keg_id = _create_clean_keg(app_client)
    app_client.patch(f"/vessels/{keg_id}", json={"batchId": batch_id}, headers=headers)

    accepted = app_client.patch(f"/batches/{batch_id}", json={"rating": 4}, headers=headers)
    assert accepted.status_code == 200
    assert accepted.json()["rating"] == 4


def test_a_failed_packaging_leaves_no_vessel_behind(app_client, monkeypatch):
    """The bottles path is one transaction, not two.

    `create()` must commit the vessel and package the batch atomically — a
    failure between the two steps would leave a committed vessel attached to
    a batch that was never packaged (still fermenting, no package_date, no
    gravity snapshot), with nothing in the product able to reconcile the two.
    """
    truncate_database()
    batch_id = _create_batch(app_client)

    from oss.services.batch import BatchService

    def _explode(self, *args, **kwargs):
        raise RuntimeError("packaging failed")

    monkeypatch.setattr(BatchService, "mark_packaged", _explode)

    try:
        app_client.post("/vessels", json={
            "batchId": batch_id,
            "vesselType": "bottles",
            "name": "Doomed Bottles",
            "fillDate": "2026-02-02",
            "totalVolume": 9.9,
            "volumeRemaining": 9.9,
            "bottleCount": 30,
            "bottlesRemaining": 30,
            "bottleVolume": 0.33,
            "status": "filled",
        }, headers=headers)
    except RuntimeError:
        pass

    monkeypatch.undo()

    vessels = app_client.get("/vessels", headers=headers).json()
    names = [v["name"] for v in (vessels.get("items", vessels) if isinstance(vessels, dict) else vessels)]
    assert "Doomed Bottles" not in names, "vessel survived a failed packaging"
    assert _get_batch(app_client, batch_id)["status"] == "fermenting"
