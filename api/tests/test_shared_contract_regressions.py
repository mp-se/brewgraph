# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph

"""Regression coverage for converged paid-GA safeguards that also serve OSS."""
import uuid
from unittest.mock import AsyncMock

from core.config import get_settings
from core.db import create_session
from core.models.registry import resolve_model
from oss.services.integration import TEST_SENDS_PER_HOUR
from tests.conftest import truncate_database

Integration = resolve_model("Integration")
PourEvent = resolve_model("PourEvent")

HEADERS = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def _setup_tapped_vessel(app_client):
    """Create the batch/vessel/tap trio needed by the write-path checks."""
    truncate_database()
    batch = app_client.post(
        "/batches", json={"name": "GA batch", "status": "packaged"}, headers=HEADERS
    ).json()
    vessel = app_client.post(
        "/vessels",
        json={
            "batchId": batch["id"], "vesselType": "keg", "name": "GA keg",
            "fillDate": "2026-09-08", "totalVolume": 19.0,
            "volumeRemaining": 19.0, "status": "serving",
        },
        headers=HEADERS,
    ).json()
    tap = app_client.post("/taps", json={"name": "GA tap"}, headers=HEADERS).json()
    vessel = app_client.patch(
        f"/vessels/{vessel['id']}", json={"tapId": tap["id"]}, headers=HEADERS
    ).json()
    return batch, vessel, tap


def _create_integration(app_client):
    """Use a public IP so the normal outbound safety check remains exercised."""
    response = app_client.post(
        "/integrations",
        json={
            "name": "GA integration", "measurement": "gravity",
            "type": "custom_forward", "enabled": True,
            "config": {
                "url": "https://8.8.8.8/forward", "method": "POST",
                "template": '{"gravity":${gravity}}',
            },
        },
        headers=HEADERS,
    )
    assert response.status_code == 201
    return response.json()


def test_converged_versions_increment_on_write(app_client):
    """All four shared mutable models expose a version that advances on update."""
    batch, vessel, tap = _setup_tapped_vessel(app_client)
    integration = _create_integration(app_client)

    updates = [
        (f"/batches/{batch['id']}", {"name": "GA batch v2"}, batch),
        (f"/vessels/{vessel['id']}", {"location": "Cellar"}, vessel),
        (f"/taps/{tap['id']}", {"notes": "Cleaned"}, tap),
        (f"/integrations/{integration['id']}", {"name": "GA integration v2"}, integration),
    ]
    for path, body, original in updates:
        response = app_client.patch(path, json=body, headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["version"] == original["version"] + 1


def test_dispatch_pour_idempotency_replays_without_double_decrement(app_client):
    """Header-only idempotency works through dispatch and shares one receipt/event."""
    _, vessel, tap = _setup_tapped_vessel(app_client)
    payload = {"token": tap["token"], "pour": 1.0, "volume": 18.0, "maxVolume": 19.0}
    replay_headers = {"Idempotency-Key": "pour-receipt-1"}

    first = app_client.post("/ingest/dispatch", json=payload, headers=replay_headers)
    second = app_client.post("/ingest/dispatch", json=payload, headers=replay_headers)

    assert first.status_code == second.status_code == 200
    session = create_session()
    try:
        pours = session.query(PourEvent).filter_by(
            vessel_id=uuid.UUID(vessel["id"])
        ).all()
        assert len(pours) == 1
        assert pours[0].event_id == "pour-receipt-1"
    finally:
        session.remove()
    vessel_response = app_client.get(f"/vessels/{vessel['id']}", headers=HEADERS)
    assert vessel_response.json()["volumeRemaining"] == 18.0


def test_integration_test_records_redacted_health_without_touching_strikes(app_client, monkeypatch):
    """Test sends report a category, never consume strikes, and obey their own limit."""
    truncate_database()
    target = _create_integration(app_client)
    session = create_session()
    try:
        row = session.get(Integration, uuid.UUID(target["id"]))
        row.consecutive_failures = 2
        row.enabled = False
        session.commit()
    finally:
        session.remove()

    monkeypatch.setattr("oss.services.integration.increment_key", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(
        "oss.services.integration.deliver_custom", AsyncMock(return_value="failed")
    )
    response = app_client.post(f"/integrations/{target['id']}/test", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"outcome": "failed"}

    session = create_session()
    try:
        row = session.get(Integration, uuid.UUID(target["id"]))
        assert row.consecutive_failures == 2
        assert row.enabled is False
        assert row.last_failure_code == "delivery_failed"
        assert row.last_failure_at is not None
    finally:
        session.remove()

    over_limit = TEST_SENDS_PER_HOUR + 1
    monkeypatch.setattr(
        "oss.services.integration.increment_key", lambda *_args, **_kwargs: over_limit
    )
    limited = app_client.post(f"/integrations/{target['id']}/test", headers=HEADERS)
    assert limited.status_code == 429
