# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Contract tests for the anonymous OSS public-display resources."""
from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

from core.db import create_session
from core.models.registry import resolve_model
from tests.conftest import truncate_database

Batch = resolve_model("Batch")
PourEvent = resolve_model("PourEvent")
PressureReading = resolve_model("PressureReading")
StorageVessel = resolve_model("StorageVessel")
Tap = resolve_model("Tap")
TempReading = resolve_model("TempReading")
TenantSettings = resolve_model("TenantSettings")


def test_init():
    """Reset database state before this public-resource scenario group."""
    truncate_database()


def _add_public_fixture(*, deleted_batch: bool = False) -> None:
    """Create serving, empty, bottle, and excluded/deleted measurement cases."""
    now = datetime.now(UTC)
    db = create_session()
    try:
        settings = TenantSettings(
            brewery_name="Sunset Brewing",
            logo_url="https://example.com/logo.png",
            theme="chalkboard",
            primary_color="#f59e0b",
        )
        batch = Batch(
            name="Hazy IPA",
            style="New England IPA",
            abv=6.2,
            ibu=45,
            ebc=12,
            deleted_at=now if deleted_batch else None,
        )
        live_tap = Tap(name="Tap 4", tap_number=4, notes="Never publish this")
        empty_tap = Tap(name="Tap 5", tap_number=5)
        deleted_tap = Tap(name="Deleted", tap_number=6, deleted_at=now)
        db.add_all([settings, batch, live_tap, empty_tap, deleted_tap])
        db.flush()

        keg = StorageVessel(
            batch_id=batch.id,
            tap_id=live_tap.id,
            vessel_type="keg",
            name="Private keg name",
            fill_date=date(2026, 9, 13),
            total_volume=20.0,
            volume_remaining=12.4,
            status="serving",
            location="Do not expose",
            notes="Do not expose",
        )
        bottles = StorageVessel(
            batch_id=batch.id,
            vessel_type="bottles",
            name="Private bottle vessel name",
            fill_date=date(2026, 9, 13),
            total_volume=7.92,
            volume_remaining=5.94,
            bottle_volume=0.33,
            bottle_count=24,
            bottles_remaining=18,
            status="filled",
            location="Do not expose",
            notes="Do not expose",
        )
        empty_bottles = StorageVessel(
            batch_id=batch.id,
            vessel_type="bottles",
            name="Empty bottles",
            fill_date=date(2026, 9, 13),
            total_volume=7.92,
            volume_remaining=0.0,
            bottle_volume=0.33,
            bottle_count=24,
            bottles_remaining=0,
            status="serving",
        )
        deleted_bottles = StorageVessel(
            batch_id=batch.id,
            vessel_type="bottles",
            name="Deleted bottles",
            fill_date=date(2026, 9, 13),
            total_volume=7.92,
            volume_remaining=7.92,
            bottle_volume=0.33,
            bottle_count=24,
            bottles_remaining=24,
            status="filled",
            deleted_at=now,
        )
        db.add_all([keg, bottles, empty_bottles, deleted_bottles])
        db.flush()

        db.add_all([
            TempReading(
                vessel_id=keg.id,
                temperature=5.2,
                created_at=now - timedelta(minutes=2),
            ),
            TempReading(
                vessel_id=keg.id,
                temperature=99.0,
                excluded=True,
                created_at=now - timedelta(minutes=1),
            ),
            TempReading(
                vessel_id=keg.id,
                temperature=98.0,
                deleted_at=now,
                created_at=now,
            ),
            PressureReading(
                vessel_id=keg.id,
                pressure=110.4,
                created_at=now - timedelta(minutes=2),
            ),
            PressureReading(
                vessel_id=keg.id,
                pressure=999.0,
                is_aggregate=True,
                created_at=now - timedelta(minutes=1),
            ),
            PourEvent(
                vessel_id=keg.id,
                batch_id=batch.id,
                tap_id=live_tap.id,
                pour_amount=0.4,
                volume_remaining=12.4,
                created_at=now - timedelta(minutes=2),
            ),
            PourEvent(
                vessel_id=keg.id,
                batch_id=batch.id,
                tap_id=live_tap.id,
                pour_amount=99.0,
                volume_remaining=0.0,
                excluded=True,
                created_at=now - timedelta(minutes=1),
            ),
            PourEvent(
                vessel_id=keg.id,
                batch_id=batch.id,
                tap_id=empty_tap.id,
                pour_amount=98.0,
                volume_remaining=0.0,
                created_at=now,
            ),
        ])
        db.commit()
    finally:
        db.remove()


def test_public_context_is_unauthenticated_and_only_exposes_presentation(root_client):
    """GET /d needs no credential and emits the documented context shape."""
    test_init()
    _add_public_fixture()
    with patch("oss.routers.public_display.read_key", return_value=None), \
         patch("oss.routers.public_display.write_key", return_value=True):
        response = root_client.get("/d")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    assert response.json() == {
        "breweryName": "Sunset Brewing",
        "logoUrl": "https://example.com/logo.png",
        "theme": "chalkboard",
        "primaryColor": "#f59e0b",
    }


def test_public_taps_return_sanitized_current_keg_snapshots(root_client):
    """GET /t omits secrets/IDs and ignores excluded or deleted source rows."""
    test_init()
    _add_public_fixture()
    with patch("oss.routers.public_display.read_key", return_value=None), \
         patch("oss.routers.public_display.write_key", return_value=True):
        response = root_client.get("/t")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=15"
    data = response.json()
    assert [item["tapName"] for item in data] == ["Tap 4", "Tap 5"]
    serving_tap = data[0]
    assert serving_tap["beerName"] == "Hazy IPA"
    assert serving_tap["style"] == "New England IPA"
    assert serving_tap["serving"]["volumePoured"] == 7.6
    assert serving_tap["serving"]["temperature"] == 5.2
    assert serving_tap["serving"]["pressure"] == 110.4
    assert serving_tap["serving"]["lastPour"]["amount"] == 0.4
    assert "id" not in serving_tap
    assert "notes" not in serving_tap
    assert "token" not in serving_tap
    assert "location" not in serving_tap["serving"]
    assert data[1] == {"tapName": "Tap 5", "serving": None}


def test_public_bottles_are_separate_and_exclude_empty_or_deleted_vessels(root_client):
    """GET /b has no tap/keg data and returns only public packaged stock."""
    test_init()
    _add_public_fixture()
    with patch("oss.routers.public_display.read_key", return_value=None), \
         patch("oss.routers.public_display.write_key", return_value=True):
        response = root_client.get("/b")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=15"
    assert response.json() == [{
        "beerName": "Hazy IPA",
        "style": "New England IPA",
        "abv": 6.2,
        "ibu": 45.0,
        "ebc": 12.0,
        "bottleVolume": 0.33,
        "bottlesRemaining": 18,
        "totalBottleCount": 24,
        "availability": "available",
    }]


def test_deleted_batch_hides_its_serving_and_bottle_projection(root_client):
    """A live child cannot leak through the public display after parent deletion."""
    test_init()
    _add_public_fixture(deleted_batch=True)
    with patch("oss.routers.public_display.read_key", return_value=None), \
         patch("oss.routers.public_display.write_key", return_value=True):
        taps = root_client.get("/t")
        bottles = root_client.get("/b")

    assert taps.status_code == 200
    assert taps.json() == [
        {"tapName": "Tap 4", "serving": None},
        {"tapName": "Tap 5", "serving": None},
    ]
    assert bottles.status_code == 200
    assert bottles.json() == []


def test_public_resources_use_separate_rate_limit_keys(root_client):
    """One resource's polling budget cannot consume another resource's budget."""
    test_init()
    _add_public_fixture()
    with patch("oss.routers.public_display.read_key", return_value=None), \
         patch("oss.routers.public_display.write_key", return_value=True), \
         patch("oss.routers.public_display.enforce_request_rate_ceiling") as limit:
        assert root_client.get("/t").status_code == 200
        assert root_client.get("/b").status_code == 200

    tap_key = limit.call_args_list[0].args[0]
    bottle_key = limit.call_args_list[1].args[0]
    assert tap_key.startswith("public_display:rate:tap:")
    assert bottle_key.startswith("public_display:rate:bottle:")
    assert tap_key != bottle_key
