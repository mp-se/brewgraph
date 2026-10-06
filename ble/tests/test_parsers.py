# BrewGraph
# Copyright (c) 2024-2026 Magnus
# GPL-3 / Commercial dual license

"""Unit tests for BLE advertisement frame parsers in scan.py.

No hardware, no network. Each test:
  1. Builds a realistic advertisement byte payload using packets.py (same
     encoding the real firmware uses).
  2. Calls the parser directly with a mock device + advertisement object.
  3. Asserts the dict that would be POSTed to the ingest endpoint is correct.

requests.post is mocked so no HTTP traffic occurs.
"""

from unittest.mock import MagicMock, patch

import pytest

import scan
from tests.conftest import MockAdvertisementData, MockBLEDevice
from tests.packets import (FEAA_UUID, TEST_CHIP_ID, chamber_ibeacon,
                           gravitymon_eddystone, gravitymon_ibeacon,
                           pressuremon_ibeacon)

CHIP_HEX = hex(TEST_CHIP_ID)[2:]  # "dead"


def _capture_post():
    """Return a mock for requests.post that records calls."""
    return patch(
        "scan.requests.post",
        return_value=MagicMock(status_code=200, headers={}),
    )


def _throttled_post(retry_after="600"):
    """A mock server that refuses with 429 and asks for `retry_after` seconds."""
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    return patch(
        "scan.requests.post",
        return_value=MagicMock(status_code=429, headers=headers),
    )


# ---------------------------------------------------------------------------
# GravityMon iBeacon
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGravitymonIBeacon:
    """Tests for the GravityMon custom iBeacon parser."""

    async def test_gravity_and_temperature_decoded(self):
        """Gravity and temperature values are correctly scaled from uint16 wire format."""
        adv = MockAdvertisementData(
            manufacturer_data=gravitymon_ibeacon(gravity=1.048, temp_c=20.0)
        )
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_gravitymon(MockBLEDevice(), adv)
            scan.skip_push = True

        assert mock_post.called
        payload = mock_post.call_args[1]["json"]
        assert payload["gravity"] == pytest.approx(1.048, abs=0.0001)
        assert payload["temperature"] == pytest.approx(20.0, abs=0.1)

    async def test_chip_id_in_payload(self):
        """The transmitted ID maps to the configured GravityMon token before POST."""
        adv = MockAdvertisementData(manufacturer_data=gravitymon_ibeacon())
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_gravitymon(MockBLEDevice(), adv)
            scan.skip_push = True

        payload = mock_post.call_args[1]["json"]
        assert payload["ID"] == CHIP_HEX
        assert payload["token"] == "gravity-token"

    async def test_unknown_chip_id_posts_id_without_token(self):
        """A GravityMon ID is posted without a token for the OSS LAN fallback."""
        scan.gravitymon_device_tokens.clear()
        adv = MockAdvertisementData(manufacturer_data=gravitymon_ibeacon())
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_gravitymon(MockBLEDevice(), adv)
            scan.skip_push = True

        payload = mock_post.call_args[1]["json"]
        assert payload["ID"] == CHIP_HEX
        assert "token" not in payload

    async def test_angle_and_battery_decoded(self):
        """Angle and battery fields are scaled correctly from uint16."""
        adv = MockAdvertisementData(
            manufacturer_data=gravitymon_ibeacon(angle=32.75, battery=3.92)
        )
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_gravitymon(MockBLEDevice(), adv)
            scan.skip_push = True

        payload = mock_post.call_args[1]["json"]
        assert payload["angle"] == pytest.approx(32.75, abs=0.01)
        assert payload["battery"] == pytest.approx(3.92, abs=0.001)

    async def test_sentinel_0xffff_becomes_absent(self):
        """Fields encoded as 0xFFFF should be stripped by remove_none_values."""
        adv = MockAdvertisementData(
            manufacturer_data=gravitymon_ibeacon(battery=None, angle=None)
        )
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_gravitymon(MockBLEDevice(), adv)
            scan.skip_push = True

        payload = mock_post.call_args[1]["json"]
        assert "battery" not in payload
        assert "angle" not in payload

    async def test_non_matching_manufacturer_id_ignored(self):
        """Data for a different manufacturer ID should produce no post."""
        adv = MockAdvertisementData(manufacturer_data={0x0059: b"\x00" * 22})
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_gravitymon(MockBLEDevice(), adv)
            scan.skip_push = True

        assert not mock_post.called

    async def test_rate_limit_suppresses_duplicate(self):
        """A second call within MINIMUM_INTERVAL should not produce a second post."""
        scan.MINIMUM_INTERVAL = 9999
        adv = MockAdvertisementData(manufacturer_data=gravitymon_ibeacon())

        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_gravitymon(MockBLEDevice(), adv)
            await scan.parse_gravitymon(MockBLEDevice(), adv)
            scan.skip_push = True

        assert mock_post.call_count == 1


# ---------------------------------------------------------------------------
# GravityMon Eddystone
# ---------------------------------------------------------------------------

class TestGravitymonEddystone:
    """Tests for the GravityMon Eddystone-TLM parser."""

    def test_gravity_and_temperature_decoded(self):
        """Gravity and temperature are correctly scaled from the Eddystone payload."""
        svc_data = gravitymon_eddystone(gravity=1.060, temp_c=18.5)
        adv = MockAdvertisementData(
            service_data=svc_data,
            service_uuids=[FEAA_UUID],
        )
        with _capture_post() as mock_post:
            scan.skip_push = False
            scan.parse_gravitymon_eddystone(MockBLEDevice(name="gravitymon"), adv)
            scan.skip_push = True

        assert mock_post.called
        payload = mock_post.call_args[1]["json"]
        assert payload["gravity"] == pytest.approx(1.060, abs=0.0001)
        assert payload["temperature"] == pytest.approx(18.5, abs=0.1)

    def test_angle_battery_chip_id_decoded(self):
        """Angle, battery, and chip ID fields are decoded from the Eddystone frame."""
        svc_data = gravitymon_eddystone(chip_id=TEST_CHIP_ID, angle=30.0, battery=4.1)
        adv = MockAdvertisementData(service_data=svc_data, service_uuids=[FEAA_UUID])
        with _capture_post() as mock_post:
            scan.skip_push = False
            scan.parse_gravitymon_eddystone(MockBLEDevice(name="gravitymon"), adv)
            scan.skip_push = True

        payload = mock_post.call_args[1]["json"]
        assert payload["ID"] == CHIP_HEX
        assert payload["token"] == "gravity-token"
        assert payload["angle"] == pytest.approx(30.0, abs=0.01)
        assert payload["battery"] == pytest.approx(4.1, abs=0.001)

    def test_missing_service_data_ignored(self):
        """An Eddystone advertisement with no service data payload should be silently ignored."""
        adv = MockAdvertisementData(service_uuids=[FEAA_UUID])
        with _capture_post() as mock_post:
            scan.skip_push = False
            scan.parse_gravitymon_eddystone(MockBLEDevice(name="gravitymon"), adv)
            scan.skip_push = True

        assert not mock_post.called

    def test_unknown_chip_id_posts_id_without_token(self):
        """An Eddystone GravityMon ID reaches the OSS fallback without a token map."""
        scan.gravitymon_device_tokens.clear()
        adv = MockAdvertisementData(
            service_data=gravitymon_eddystone(),
            service_uuids=[FEAA_UUID],
        )
        with _capture_post() as mock_post:
            scan.skip_push = False
            scan.parse_gravitymon_eddystone(MockBLEDevice(name="gravitymon"), adv)
            scan.skip_push = True

        payload = mock_post.call_args[1]["json"]
        assert payload["ID"] == CHIP_HEX
        assert "token" not in payload


# ---------------------------------------------------------------------------
# PressureMon iBeacon
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPressuremonIBeacon:
    """Tests for the PressureMon iBeacon parser."""

    async def test_pressure_and_temperature_decoded(self):
        """Primary pressure and temperature values are correctly scaled."""
        adv = MockAdvertisementData(
            manufacturer_data=pressuremon_ibeacon(pressure=10.5, temp_c=4.0)
        )
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_pressuremon(MockBLEDevice(), adv)
            scan.skip_push = True

        assert mock_post.called
        payload = mock_post.call_args[1]["json"]
        assert payload["pressure"] == pytest.approx(10.5, abs=0.01)
        assert payload["temperature"] == pytest.approx(4.0, abs=0.1)

    async def test_dual_pressure_sensors_decoded(self):
        """Both pressure sensor channels are decoded independently."""
        adv = MockAdvertisementData(
            manufacturer_data=pressuremon_ibeacon(pressure=12.0, pressure1=3.5)
        )
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_pressuremon(MockBLEDevice(), adv)
            scan.skip_push = True

        payload = mock_post.call_args[1]["json"]
        assert payload["pressure"] == pytest.approx(12.0, abs=0.01)
        assert payload["pressure1"] == pytest.approx(3.5, abs=0.01)

    async def test_transmitted_id_maps_to_pressuremon_token(self):
        """The transmitted ID maps through the PressureMon-specific token registry."""
        adv = MockAdvertisementData(manufacturer_data=pressuremon_ibeacon())
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_pressuremon(MockBLEDevice(), adv)
            scan.skip_push = True

        payload = mock_post.call_args[1]["json"]
        assert payload["ID"] == CHIP_HEX
        assert payload["token"] == "pressure-token"

    async def test_unknown_transmitted_id_posts_id_without_token(self):
        """A PressureMon ID is posted without a token for the OSS LAN fallback."""
        scan.pressuremon_device_tokens.clear()
        adv = MockAdvertisementData(manufacturer_data=pressuremon_ibeacon())
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_pressuremon(MockBLEDevice(), adv)
            scan.skip_push = True

        payload = mock_post.call_args[1]["json"]
        assert payload["ID"] == CHIP_HEX
        assert "token" not in payload

    async def test_sentinel_pressure_becomes_absent(self):
        """A 0xFFFF sentinel in the pressure field should be stripped from the payload."""
        adv = MockAdvertisementData(
            manufacturer_data=pressuremon_ibeacon(pressure=None)
        )
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_pressuremon(MockBLEDevice(), adv)
            scan.skip_push = True

        payload = mock_post.call_args[1]["json"]
        assert "pressure" not in payload


# ---------------------------------------------------------------------------
# Chamber Controller iBeacon
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestChamberIBeacon:
    """Tests for the Chamber Controller iBeacon parser."""

    @pytest.fixture(autouse=True)
    def _reset_chamber_state(self):
        """Clear the throttle/token maps and give MINIMUM_INTERVAL a real value.

        `chambers` is module-level state, so without the reset one test's post
        suppresses the next one's and the suite passes or fails on ordering.

        `MINIMUM_INTERVAL` matters more than it looks: it is `0` until `main()` sets
        it from the environment, and `main()` never runs under test. At `0` every
        throttle in this module is a no-op, so a test written against the default
        would assert nothing while appearing to cover the interval. Production uses
        300s by default.
        """
        original_interval = scan.MINIMUM_INTERVAL
        scan.MINIMUM_INTERVAL = 300
        scan.chambers.clear()
        scan.chamber_device_tokens.clear()
        yield
        scan.chambers.clear()
        scan.chamber_device_tokens.clear()
        scan.MINIMUM_INTERVAL = original_interval

    async def test_posts_in_the_shape_the_endpoint_accepts(self):
        """The payload must match `ChamberIngestRequest`, not the endpoint's docstring.

        That docstring advertises `beer-temp`/`fridge-temp`; the schema requires
        `beer_temperature`/`fridge_temperature` and would 422 the hyphenated form.
        """
        scan.chamber_device_tokens[CHIP_HEX] = "chamber-token"
        adv = MockAdvertisementData(
            manufacturer_data=chamber_ibeacon(chamber_temp_c=16.0, beer_temp_c=20.5)
        )
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_chamber(MockBLEDevice(), adv)
            scan.skip_push = True

        assert mock_post.called
        payload = mock_post.call_args[1]["json"]
        assert payload["token"] == "chamber-token"
        assert payload["id"] == CHIP_HEX
        assert payload["beer_temperature"] == pytest.approx(20.5, abs=0.1)
        assert payload["fridge_temperature"] == pytest.approx(16.0, abs=0.1)
        assert payload["temp_units"] == "C"
        # `current_mode` is deliberately absent: a broadcast carries no mode, so
        # sending a placeholder would assert something untrue about the
        # controller. The field is optional and simply omitted.
        assert "current_mode" not in payload

    async def test_posts_chip_id_alone_when_no_token_is_registered(self):
        """An unmapped chamber still posts, resolving server-side by chip ID.

        `/api/ingest/chamber` accepts `chamber_controller` in `resolve_device`'s
        trusted-LAN fallback, matching GravityMon and PressureMon, so a chamber
        missing from the device list still posts and resolves server-side by
        chip ID.
        """
        adv = MockAdvertisementData(
            manufacturer_data=chamber_ibeacon(chamber_temp_c=16.0, beer_temp_c=20.5)
        )
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_chamber(MockBLEDevice(), adv)
            scan.skip_push = True

        assert mock_post.called
        payload = mock_post.call_args[1]["json"]
        assert payload["id"] == CHIP_HEX
        assert "token" not in payload, "a None token must be stripped, not sent as null"

    async def test_repeat_advertisements_are_throttled(self):
        """A chamber broadcasts every few seconds; only the first post gets through.

        This is the whole point of the MIN_INTERVAL map — without it the scanner would
        post on every advertisement and be rate-limited by the server instead.
        """
        scan.chamber_device_tokens[CHIP_HEX] = "chamber-token"
        adv = MockAdvertisementData(
            manufacturer_data=chamber_ibeacon(chamber_temp_c=16.0, beer_temp_c=20.5)
        )
        with _capture_post() as mock_post:
            scan.skip_push = False
            for _ in range(5):
                await scan.parse_chamber(MockBLEDevice(), adv)
            scan.skip_push = True

        assert mock_post.call_count == 1, "throttle let a repeat advertisement through"

    async def test_posts_again_once_the_interval_has_passed(self):
        """The throttle must expire, or a chamber posts once and never again."""
        scan.chamber_device_tokens[CHIP_HEX] = "chamber-token"
        adv = MockAdvertisementData(
            manufacturer_data=chamber_ibeacon(chamber_temp_c=16.0, beer_temp_c=20.5)
        )
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_chamber(MockBLEDevice(), adv)
            # Rewind the recorded post past the interval rather than sleeping.
            scan.chambers[CHIP_HEX] -= scan.MINIMUM_INTERVAL + 1
            await scan.parse_chamber(MockBLEDevice(), adv)
            scan.skip_push = True

        assert mock_post.call_count == 2


@pytest.mark.asyncio
class TestServerThrottleBackoff:
    """A 429 must push the next post out to when the server said, not the next interval.

    The scanner keeps its own MIN_INTERVAL clock. Without this it retries on that clock
    regardless of what the server answered, so a device whose server-side window is
    longer than MIN_INTERVAL gets refused over and over — the scanner spending requests
    to be told the same thing.
    """

    @pytest.fixture(autouse=True)
    def _reset(self):
        original = scan.MINIMUM_INTERVAL
        scan.MINIMUM_INTERVAL = 300
        scan.chambers.clear()
        scan.chamber_device_tokens.clear()
        scan.chamber_device_tokens[CHIP_HEX] = "chamber-token"
        yield
        scan.chambers.clear()
        scan.chamber_device_tokens.clear()
        scan.MINIMUM_INTERVAL = original

    @staticmethod
    def _adv():
        return MockAdvertisementData(
            manufacturer_data=chamber_ibeacon(chamber_temp_c=16.0, beer_temp_c=20.5)
        )

    async def test_a_429_defers_past_the_normal_interval(self):
        """After a refusal asking for 600s, the 300s interval alone must not be enough."""
        with _throttled_post("600") as mock_post:
            scan.skip_push = False
            await scan.parse_chamber(MockBLEDevice(), self._adv())
            # Advance past MIN_INTERVAL, which without back-off would allow a retry.
            scan.chambers[CHIP_HEX] -= scan.MINIMUM_INTERVAL + 1
            await scan.parse_chamber(MockBLEDevice(), self._adv())
            scan.skip_push = True

        assert mock_post.call_count == 1, "retried inside the window the server asked for"

    async def test_posting_resumes_once_the_advertised_delay_elapses(self):
        """Back-off must expire too, or one 429 silences a device permanently."""
        with _throttled_post("600") as mock_post:
            scan.skip_push = False
            await scan.parse_chamber(MockBLEDevice(), self._adv())
            scan.chambers[CHIP_HEX] -= 601
            await scan.parse_chamber(MockBLEDevice(), self._adv())
            scan.skip_push = True

        assert mock_post.call_count == 2

    async def test_a_429_without_a_usable_header_falls_back_to_the_normal_interval(self):
        """No header, or an unparseable one, leaves the existing throttle in charge.

        Refusing to post at all would be the wrong failure: the server may have been
        throttling for a reason that has since passed, and the scanner has no other
        signal to act on.
        """
        for header in (None, "next tuesday"):
            scan.chambers.clear()
            with _throttled_post(header) as mock_post:
                scan.skip_push = False
                await scan.parse_chamber(MockBLEDevice(), self._adv())
                scan.chambers[CHIP_HEX] -= scan.MINIMUM_INTERVAL + 1
                await scan.parse_chamber(MockBLEDevice(), self._adv())
                scan.skip_push = True
            assert mock_post.call_count == 2, f"header {header!r} should not defer"

    async def test_a_short_retry_after_does_not_shorten_the_scanner_interval(self):
        """The scanner may be more conservative than the server; that needs no fixing."""
        with _throttled_post("10") as mock_post:
            scan.skip_push = False
            await scan.parse_chamber(MockBLEDevice(), self._adv())
            for _ in range(3):
                await scan.parse_chamber(MockBLEDevice(), self._adv())
            scan.skip_push = True

        assert mock_post.call_count == 1, "a short Retry-After must not relax the throttle"

    async def test_a_success_never_defers(self):
        """Only a 429 moves the clock; a 200 leaves the ordinary interval in place."""
        with _capture_post() as mock_post:
            scan.skip_push = False
            await scan.parse_chamber(MockBLEDevice(), self._adv())
            scan.chambers[CHIP_HEX] -= scan.MINIMUM_INTERVAL + 1
            await scan.parse_chamber(MockBLEDevice(), self._adv())
            scan.skip_push = True

        assert mock_post.call_count == 2
