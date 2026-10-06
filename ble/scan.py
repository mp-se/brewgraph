# BrewGraph
# Copyright (c) 2021-2026 Magnus
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Alternatively, this software may be used under the terms of a
# commercial license. See LICENSE_COMMERCIAL for details.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""BLE scanner for brewing sensors: GravityMon, PressureMon, ChamberCtl.

The scanner is a pure bridge: it parses an advertisement and POSTs it to the matching
ingest endpoint. It holds no cache and no shared state — the only state is an in-memory
last-post timestamp per device, which is all a single process with sole ownership of one
radio needs. That is also what the GravityMon Gateway does in hardware, so this stays the
software reference implementation of the same design rather than a parallel mechanism.

Not supported, for reasons worth keeping since they are easy to re-litigate:

- **Tilt-format and RAPT.** Tilt-format was GravityMon broadcasting in Tilt's wire format,
  not Tilt hydrometer support; without it, a GravityMon configured for it must be
  reconfigured to iBeacon or Eddystone. RAPT never posted a reading at all — its
  parsers only wrote cache keys — so there is no functional loss. `rapt_pill` is
  not a device type this repo's ingest API accepts, which is why it does not belong
  here.
- **Redis.** A `ble_*` status mirror and a dedup clock would need it. Chamber posts
  through the same ingest path as every other format, so the API already holds
  everything such a mirror would, with real history behind it besides. The dedup
  clock is a plain dict instead.

Requires the following environment variables:

  API_HOST:     Hostname/IP of the API (e.g. brewgraph-api)
  API_KEY:      API key, used **only** to fetch the device list for the token maps.
                The ingest endpoints themselves take no credential — `ingest_auth` is
                IP rate-limiting, not authentication.

Optional:

  MIN_INTERVAL: Minimum seconds between repeated posts for the same device (default: 900)
"""

import asyncio
import json
import logging
import os
import time
from typing import Optional

import requests
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from construct import Const, Int16ub, Int32ub, Struct
from construct.core import ConstError, StreamError

logger = logging.getLogger(__file__)

# ── Feature flags (override at runtime via env for testing) ───────────────────
skip_push = os.getenv("SKIP_PUSH", "false").lower() == "true"
skip_chamber = os.getenv("SKIP_CHAMBER", "false").lower() == "true"
skip_pressuremon = os.getenv("SKIP_PRESSUREMON", "false").lower() == "true"
skip_gravitymon = os.getenv("SKIP_GRAVITYMON", "false").lower() == "true"
SKIP_NULL_VALUES = True  # Strip None-valued fields before posting

# ── v2 ingest endpoints ───────────────────────────────────────────────────────
_api_base = "http://" + (os.getenv("API_HOST") or "brewgraph-api")
_api_key = os.getenv("API_KEY", "")

endpoint_gravity = _api_base + "/api/ingest/gravitymon"
endpoint_pressure = _api_base + "/api/ingest/pressuremon"
endpoint_chamber = _api_base + "/api/ingest/chamber"
endpoint_devices = _api_base + "/api/devices/?pageSize=200"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + _api_key,
}

MINIMUM_INTERVAL = 0

# ── BLE advertisement frame formats ───────────────────────────────────────────

gravitymon_ibeacon_format = Struct(
    "type_length" / Const(b"\x03\x15"),
    "name" / Const(b"GRAVMON."),
    "chipid" / Int32ub,
    "angle" / Int16ub,
    "battery" / Int16ub,
    "gravity" / Int16ub,
    "temp" / Int16ub,
)

gravitymon_eddystone_format = Struct(
    "type_length" / Const(b"\x20\x00"),
    "battery" / Int16ub,
    "temp" / Int16ub,
    "gravity" / Int16ub,
    "angle" / Int16ub,
    "chipid" / Int32ub,
)

pressuremon_ibeacon_format = Struct(
    "type_length" / Const(b"\x03\x15"),
    "name" / Const(b"PRESMON."),
    "chipid" / Int32ub,
    "pressure" / Int16ub,
    "pressure1" / Int16ub,
    "battery" / Int16ub,
    "temp" / Int16ub,
)

chamber_ibeacon_format = Struct(
    "type_length" / Const(b"\x03\x15"),
    "name" / Const(b"CHAMBER."),
    "chipid" / Int32ub,
    "chamberTemp" / Int16ub,
    "beerTemp" / Int16ub,
)


# ── Per-device last-post clocks ───────────────────────────────────────────────

gravitymons: dict = {}
pressuremons: dict = {}
# Last-post timestamps per chip id, the same MIN_INTERVAL throttle every other format
# uses. A chamber controller broadcasts every few seconds; without this it would post
# on every advertisement.
chambers: dict = {}
gravitymon_device_tokens: dict[str, str] = {}
pressuremon_device_tokens: dict[str, str] = {}
chamber_device_tokens: dict[str, str] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def remove_none_values(obj):
    """Recursively strip keys whose value is None from dicts/lists."""
    if not SKIP_NULL_VALUES:
        return obj
    if isinstance(obj, dict):
        return {k: remove_none_values(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [remove_none_values(item) for item in obj if item is not None]
    return obj


def _normalize_transmitted_id(value: str) -> str:
    """Normalize a configured hexadecimal ID to the format transmitted by BLE parsers."""
    normalized = str(value).lower().removeprefix("0x").lstrip("0")
    return normalized or "0"


def _unique_device_tokens(devices: list[dict], device_type: str) -> dict[str, str]:
    """Build a fail-closed transmitted-ID-to-token map for one BLE protocol."""
    candidates: dict[str, str] = {}
    duplicate_ids: set[str] = set()
    for device in devices:
        if device.get("deviceType") != device_type:
            continue
        device_id = device.get("chipId")
        token = device.get("token")
        if not device_id or not token:
            continue
        device_id = _normalize_transmitted_id(device_id)
        if device_id in candidates:
            duplicate_ids.add(device_id)
        else:
            candidates[device_id] = token
    for device_id in duplicate_ids:
        candidates.pop(device_id, None)
        logger.error(
            "Multiple %s devices use transmitted ID %s; BLE mapping disabled for it.",
            device_type,
            device_id,
        )
    return candidates


def load_device_tokens() -> bool:
    """Load authenticated, fail-closed token maps for each supported BLE protocol.

    All three protocols can now resolve server-side by chip ID, so these maps are an
    upgrade rather than a precondition: a token is the stronger identifier and is sent
    whenever one is known. This is the only call that needs `API_KEY` — the ingest
    endpoints take no credential.
    """
    try:
        response = requests.get(endpoint_devices, headers=headers, timeout=10)
        response.raise_for_status()
        body = response.json()
        devices = body.get("items", []) if isinstance(body, dict) else body
        if not isinstance(devices, list):
            raise TypeError("Device list response must contain an items list")
        gravitymon_candidates = _unique_device_tokens(devices, "gravitymon")
        pressuremon_candidates = _unique_device_tokens(devices, "pressuremon")
        chamber_candidates = _unique_device_tokens(devices, "chamber_controller")
        gravitymon_device_tokens.clear()
        gravitymon_device_tokens.update(gravitymon_candidates)
        pressuremon_device_tokens.clear()
        pressuremon_device_tokens.update(pressuremon_candidates)
        chamber_device_tokens.clear()
        chamber_device_tokens.update(chamber_candidates)
        logger.info(
            "Loaded %d GravityMon ID, %d PressureMon ID and %d Chamber ID token mappings.",
            len(gravitymon_candidates),
            len(pressuremon_candidates),
            len(chamber_candidates),
        )
        return bool(gravitymon_candidates or pressuremon_candidates or chamber_candidates)
    except (requests.exceptions.RequestException, TypeError, ValueError) as exc:
        gravitymon_device_tokens.clear()
        pressuremon_device_tokens.clear()
        chamber_device_tokens.clear()
        logger.error("Failed to load BLE device token mappings: %s", exc)
        return False


def _retry_after_seconds(response) -> Optional[float]:
    """Read `Retry-After` as a delay in seconds, or None if it is absent or unusable.

    The API sends an integer count of seconds, derived from the live TTL of the
    throttle key. HTTP also permits an absolute date; that form is not produced here
    and is deliberately not parsed — guessing at a format the server does not send
    would add a failure mode rather than remove one.
    """
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        seconds = float(raw)
    except (TypeError, ValueError):
        logger.warning("Ignoring uninterpretable Retry-After: %r", raw)
        return None
    return seconds if seconds > 0 else None


def _post(endpoint: str, data: dict, label: str) -> Optional[float]:
    """POST data to API; log on error.

    Returns the server's `Retry-After` delay in seconds when it throttled us, and
    None otherwise — see `_defer`, which is what acts on it.
    """
    if skip_push:
        return None
    try:
        logger.info("Posting %s data.", label)
        r = requests.post(endpoint, json=data, headers=headers, timeout=10)
        logger.info("Response %s.", r.status_code)
        if r.status_code == 429:
            wait = _retry_after_seconds(r)
            logger.warning(
                "Throttled posting %s data; server asks for %s more seconds.", label, wait
            )
            return wait
    except requests.exceptions.RequestException as e:
        logger.error("Failed to post %s data: %s", label, e)
    return None


def _defer(clock: dict, key: str, now: float, retry_after: Optional[float]) -> None:
    """Honour a server-side throttle by pushing this device's next post out.

    Without this the scanner keeps its own `MIN_INTERVAL` clock and retries on the
    next interval regardless of what the server said. BLE devices broadcast every few
    seconds, so with a short `MIN_INTERVAL` that means hammering an endpoint that has
    already refused for the rest of its window.

    The clocks store *when we last posted*, and a post is allowed once
    `MINIMUM_INTERVAL` has elapsed. Rewinding the stored value forward by the shortfall
    is what expresses "not before then" without a second piece of state to keep in step.

    A `retry_after` shorter than the interval we already observe is ignored: the
    scanner is being more conservative than the server requires, which needs no
    correction.
    """
    if retry_after is None or retry_after <= MINIMUM_INTERVAL:
        return
    clock[key] = now + retry_after - MINIMUM_INTERVAL


# ── Device parsers ────────────────────────────────────────────────────────────

async def parse_gravitymon(device: BLEDevice, advertisement_data: AdvertisementData):
    """Parse a GravityMon iBeacon or custom-iBeacon advertisement and POST to API."""
    if skip_gravitymon:
        return
    try:
        apple_data = advertisement_data.manufacturer_data[0x004C]
        ibeacon = gravitymon_ibeacon_format.parse(apple_data)
        chip_id = hex(ibeacon.chipid)[2:]

        logger.info("Parsing gravitymon iBeacon: %s", device)
        data = remove_none_values({
            "name": "",
            "ID": chip_id,
            "token": gravitymon_device_tokens.get(chip_id),
            "interval": 0,
            "battery": None if ibeacon.battery == 0xFFFF else ibeacon.battery / 1000,
            "gravity": None if ibeacon.gravity == 0xFFFF else ibeacon.gravity / 10000,
            "angle": None if ibeacon.angle == 0xFFFF else ibeacon.angle / 100,
            "temperature": None if ibeacon.temp == 0xFFFF else ibeacon.temp / 1000,
            "temp_units": "C",
            "RSSI": 0,
        })

        now = time.time()
        if abs(gravitymons.get(chip_id, now - MINIMUM_INTERVAL * 2) - now) >= MINIMUM_INTERVAL:
            gravitymons[chip_id] = now
            logger.info("Gravitymon reading: %s", json.dumps(data))
            _defer(gravitymons, chip_id, now, _post(endpoint_gravity, data, "gravitymon"))

    except (KeyError, ConstError, StreamError):
        pass


def parse_gravitymon_eddystone(device: BLEDevice, advertisement_data: AdvertisementData):
    """Parse a GravityMon Eddystone-TLM advertisement and POST to API."""
    if skip_gravitymon:
        return
    try:
        uuid = advertisement_data.service_uuids[0]
        raw = advertisement_data.service_data.get(uuid)
        eddy = gravitymon_eddystone_format.parse(raw)
        chip_id = hex(eddy.chipid)[2:]

        logger.info("Parsing gravitymon Eddystone: %s", device)
        data = remove_none_values({
            "name": "",
            "ID": chip_id,
            "token": gravitymon_device_tokens.get(chip_id),
            "interval": 0,
            "battery": None if eddy.battery == 0xFFFF else eddy.battery / 1000,
            "gravity": None if eddy.gravity == 0xFFFF else eddy.gravity / 10000,
            "angle": None if eddy.angle == 0xFFFF else eddy.angle / 100,
            "temperature": None if eddy.temp == 0xFFFF else eddy.temp / 1000,
            "temp_units": "C",
            "RSSI": 0,
        })

        now = time.time()
        if abs(gravitymons.get(chip_id, now - MINIMUM_INTERVAL * 2) - now) >= MINIMUM_INTERVAL:
            gravitymons[chip_id] = now
            logger.info("Gravitymon Eddystone reading: %s", json.dumps(data))
            _defer(
                gravitymons,
                chip_id,
                now,
                _post(endpoint_gravity, data, "gravitymon-eddystone"),
            )

    except (KeyError, ConstError, StreamError):
        pass


async def parse_pressuremon(device: BLEDevice, advertisement_data: AdvertisementData):
    """Parse a PressureMon iBeacon advertisement and POST to API."""
    if skip_pressuremon:
        return
    try:
        apple_data = advertisement_data.manufacturer_data[0x004C]
        ibeacon = pressuremon_ibeacon_format.parse(apple_data)
        chip_id = hex(ibeacon.chipid)[2:]

        logger.info("Parsing pressuremon iBeacon: %s", device)
        data = remove_none_values({
            "name": "",
            "ID": chip_id,
            "token": pressuremon_device_tokens.get(chip_id),
            "interval": 0,
            "battery": None if ibeacon.battery == 0xFFFF else ibeacon.battery / 1000,
            "pressure": None if ibeacon.pressure == 0xFFFF else ibeacon.pressure / 100,
            "pressure1": None if ibeacon.pressure1 == 0xFFFF else ibeacon.pressure1 / 100,
            "temperature": None if ibeacon.temp == 0xFFFF else ibeacon.temp / 1000,
            "pressure-unit": "PSI",
            "temperature-unit": "C",
            "RSSI": 0,
        })

        now = time.time()
        if abs(pressuremons.get(chip_id, now - MINIMUM_INTERVAL * 2) - now) >= MINIMUM_INTERVAL:
            pressuremons[chip_id] = now
            logger.info("Pressuremon reading: %s", json.dumps(data))
            _defer(pressuremons, chip_id, now, _post(endpoint_pressure, data, "pressuremon"))

    except (KeyError, ConstError):
        pass


async def parse_chamber(device: BLEDevice, advertisement_data: AdvertisementData):
    """Parse a Chamber Controller iBeacon advertisement and POST to the API.

    This parses the advertisement and posts to `/api/ingest/chamber`, which
    writes a `TempReading` — which is what these readings are; no new endpoint
    or model is needed.

    Three details of that endpoint shape the payload, and none are obvious from the
    advertisement:

    - **It resolves by token, then by chip ID**, matching GravityMon and
      PressureMon — a chamber with no entry in `chamber_device_tokens` can still
      be posted by chip ID alone. Both identifiers are sent when available and
      the server prefers the token.
    - **Field names are `beer_temperature`/`fridge_temperature`**, snake_case —
      the schema rejects the hyphenated `beer-temp`/`fridge-temp` form.
    - **`current_mode` is not sent.** It is optional and read by nothing — the
      server derives the returned setpoint from batch state. A broadcast cannot
      know the controller's mode, so sending a placeholder would assert
      something untrue.

    Posting is throttled by the same `MINIMUM_INTERVAL` every other format uses, keyed
    by chip id. The server independently enforces ~290s for this device type, so an
    eager scanner is refused rather than believed — but the client-side throttle is what
    stops it wasting a request every few seconds.
    """
    if skip_chamber:
        return
    try:
        apple_data = advertisement_data.manufacturer_data[0x004C]
        ibeacon = chamber_ibeacon_format.parse(apple_data)
        chip_id = hex(ibeacon.chipid)[2:]

        logger.info("Parsing chamber iBeacon: %s", device)
        beer_temp = None if ibeacon.beerTemp == 0xFFFF else ibeacon.beerTemp / 1000
        chamber_temp = None if ibeacon.chamberTemp == 0xFFFF else ibeacon.chamberTemp / 1000

        now = time.time()
        if beer_temp is None and chamber_temp is None:
            return  # the endpoint requires at least one temperature

        if abs(chambers.get(chip_id, now - MINIMUM_INTERVAL * 2) - now) >= MINIMUM_INTERVAL:
            data = remove_none_values({
                # Token when the device list gave us one, chip ID otherwise — the
                # endpoint accepts either, and prefers the token when both are sent.
                "token": chamber_device_tokens.get(chip_id),
                "id": chip_id,
                "beer_temperature": beer_temp,
                "fridge_temperature": chamber_temp,
                "temp_units": "C",
                # `current_mode` is deliberately absent: a broadcast carries no mode,
                # and the field is optional for exactly this case — sending a
                # placeholder value would assert something untrue about the
                # controller.
            })
            chambers[chip_id] = now
            logger.info("Chamber reading: %s", json.dumps(data))
            _defer(chambers, chip_id, now, _post(endpoint_chamber, data, "chamber"))

    except (KeyError, ConstError):
        pass


# ── Main scan callback ─────────────────────────────────────────────────────────

async def device_found(device: BLEDevice, advertisement_data: AdvertisementData):
    """Dispatch an incoming BLE advertisement to the matching device parser.

    Three formats, all first-party: GravityMon (iBeacon and Eddystone), PressureMon and
    chamber. Tilt-format and RAPT are not supported — see the module docstring
    for why — and a GravityMon configured to broadcast in Tilt format is not
    ingested and must be reconfigured.
    """
    if device.name == "gravitymon" and any(
        "0000feaa-" in s for s in advertisement_data.service_uuids
    ):
        parse_gravitymon_eddystone(device=device, advertisement_data=advertisement_data)
    else:
        await parse_gravitymon(device=device, advertisement_data=advertisement_data)
        await parse_pressuremon(device=device, advertisement_data=advertisement_data)
        await parse_chamber(device=device, advertisement_data=advertisement_data)


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    """Configure the scan interval, load the token maps, and start the BLE scan loop."""
    global MINIMUM_INTERVAL  # pylint: disable=global-statement

    t = os.getenv("MIN_INTERVAL")
    MINIMUM_INTERVAL = int(t) if t is not None else 15 * 60  # default 15 min

    load_device_tokens()
    scanner = BleakScanner(detection_callback=device_found, scanning_mode="active")

    logger.info(
        "Scanning for GravityMon/PressureMon/chamber BLE devices "
        "(min_interval=%ss, push=%s)...",
        MINIMUM_INTERVAL, not skip_push,
    )
    while True:
        await scanner.start()
        await asyncio.sleep(0.1)
        await scanner.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )
    asyncio.run(main())
    logger.info("Exit from scanner")
