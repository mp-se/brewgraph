# BrewGraph
# Copyright (c) 2024-2026 Magnus
# GPL-3 / Commercial dual license

"""BLE advertisement packet builders.

Mirrors the C++ encoding in gravitymon-ble/src exactly so tests use the same
byte layout the real firmware produces. Each function returns the dict that
bleak would produce in AdvertisementData.manufacturer_data (or service_data
for Eddystone), i.e. after bleak has stripped the 2-byte company identifier.

Sentinel value: 0xFFFF means "not available" for all uint16 fields.
"""

import struct

# Bleak manufacturer_data dict keys (company ID as little-endian uint16)
APPLE_MANUF_ID = 0x004C   # iBeacon / custom beacons

# Eddystone service UUID (full form as bleak reports it)
FEAA_UUID = "0000feaa-0000-1000-8000-00805f9b34fb"

# Default test chip ID — fits within the API's 6-char chip_id column as "dead"
TEST_CHIP_ID = 0xDEAD


def _u16(v: int) -> bytes:
    return struct.pack(">H", v & 0xFFFF)


def _u32(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)


def _enc16(value, scale: int, sentinel: bool = True) -> int:
    """Scale a float to uint16; return 0xFFFF sentinel if value is None."""
    if value is None and sentinel:
        return 0xFFFF
    return int(round(value * scale)) & 0xFFFF


# ---------------------------------------------------------------------------
# GravityMon — custom iBeacon (Apple 0x004C)
# Layout: 0x03 0x15 | "GRAVMON." | chipid(u32) | angle(u16) | battery(u16)
#         | gravity(u16) | temp(u16)
# ---------------------------------------------------------------------------

def gravitymon_ibeacon(
    chip_id: int = TEST_CHIP_ID,
    gravity: float = 1.048,
    temp_c: float = 20.0,
    angle: float = 25.5,
    battery: float = 3.92,
) -> dict:
    """Manufacturer data for a GravityMon custom iBeacon advertisement."""
    data = (
        b"\x03\x15"
        + b"GRAVMON."
        + _u32(chip_id)
        + _u16(_enc16(angle, 100))
        + _u16(_enc16(battery, 1000))
        + _u16(_enc16(gravity, 10000))
        + _u16(_enc16(temp_c, 1000))
    )
    return {APPLE_MANUF_ID: data}


# ---------------------------------------------------------------------------
# GravityMon — Eddystone-TLM
# Layout: 0x20 0x00 | battery(u16) | temp(u16) | gravity(u16) | angle(u16) | chipid(u32)
# Delivered via service_data[FEAA_UUID]; device name is "gravitymon"
# ---------------------------------------------------------------------------

def gravitymon_eddystone(
    chip_id: int = TEST_CHIP_ID,
    gravity: float = 1.048,
    temp_c: float = 20.0,
    angle: float = 25.5,
    battery: float = 3.92,
) -> dict:
    """Service data dict for a GravityMon Eddystone advertisement."""
    data = (
        b"\x20\x00"
        + _u16(_enc16(battery, 1000))
        + _u16(_enc16(temp_c, 1000))
        + _u16(_enc16(gravity, 10000))
        + _u16(_enc16(angle, 100))
        + _u32(chip_id)
    )
    return {FEAA_UUID: data}


# ---------------------------------------------------------------------------
# PressureMon — custom iBeacon (Apple 0x004C)
# Layout: 0x03 0x15 | "PRESMON." | chipid(u32) | pressure(u16) | pressure1(u16)
#         | battery(u16) | temp(u16)
# ---------------------------------------------------------------------------

def pressuremon_ibeacon(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    chip_id: int = TEST_CHIP_ID,
    pressure: float = 10.5,
    pressure1: float = 0.0,
    temp_c: float = 4.0,
    battery: float = 3.80,
) -> dict:
    """Manufacturer data for a PressureMon custom iBeacon advertisement."""
    data = (
        b"\x03\x15"
        + b"PRESMON."
        + _u32(chip_id)
        + _u16(_enc16(pressure, 100))
        + _u16(_enc16(pressure1, 100))
        + _u16(_enc16(battery, 1000))
        + _u16(int(round(temp_c * 1000)) & 0xFFFF)  # temp has no sentinel in C++
    )
    return {APPLE_MANUF_ID: data}


# ---------------------------------------------------------------------------
# Chamber Controller — custom iBeacon (Apple 0x004C)
# Layout: 0x03 0x15 | "CHAMBER." | chipid(u32) | chamberTemp(u16) | beerTemp(u16)
# ---------------------------------------------------------------------------

def chamber_ibeacon(
    chip_id: int = TEST_CHIP_ID,
    chamber_temp_c: float = 18.0,
    beer_temp_c: float = 20.5,
) -> dict:
    """Manufacturer data for a Chamber Controller iBeacon advertisement."""
    data = (
        b"\x03\x15"
        + b"CHAMBER."
        + _u32(chip_id)
        + _u16(int(round(chamber_temp_c * 1000)) & 0xFFFF)
        + _u16(int(round(beer_temp_c * 1000)) & 0xFFFF)
    )
    return {APPLE_MANUF_ID: data}


# ---------------------------------------------------------------------------
# There are no Tilt-format or RAPT builders, and no parsers for them.
# ---------------------------------------------------------------------------
