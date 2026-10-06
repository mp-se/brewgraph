# BrewGraph
# Copyright (c) 2024-2026 Magnus
# GPL-3 / Commercial dual license

"""Pytest fixtures and import bootstrap for BLE scanner tests.

scan.py calls asyncio.run(main()) at module level, which would block forever if
imported normally. We patch asyncio.run before the import so the module loads
without starting the scan loop.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch

import pytest

# Set env before scan.py is imported so module-level globals are correct
os.environ.setdefault("SKIP_PUSH", "true")
os.environ.setdefault("API_HOST", "localhost:8080")
os.environ.setdefault("API_KEY", "devkey")

# Patch asyncio.run so the module-level asyncio.run(main()) call is a no-op
_run_patcher = patch("asyncio.run")
_run_patcher.start()

sys.path.insert(0, str(Path(__file__).parent.parent))
import scan  # noqa: E402  pylint: disable=wrong-import-position,wrong-import-order

_run_patcher.stop()


# ---------------------------------------------------------------------------
# Minimal mock types that stand in for bleak's BLEDevice / AdvertisementData
# ---------------------------------------------------------------------------

@dataclass
class MockBLEDevice:
    """Minimal stand-in for bleak's BLEDevice."""

    name: str = "gravitymon"
    address: str = "AA:BB:CC:DD:EE:FF"


@dataclass
class MockAdvertisementData:
    """Minimal stand-in for bleak's AdvertisementData."""
    manufacturer_data: Dict[int, bytes] = field(default_factory=dict)
    service_data: Dict[str, bytes] = field(default_factory=dict)
    service_uuids: List[str] = field(default_factory=list)
    rssi: int = -70


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Clear per-device rate-limit dicts and disable the interval between tests."""
    scan.gravitymons.clear()
    scan.pressuremons.clear()
    scan.gravitymon_device_tokens.clear()
    scan.gravitymon_device_tokens["dead"] = "gravity-token"
    scan.pressuremon_device_tokens.clear()
    scan.pressuremon_device_tokens["dead"] = "pressure-token"
    scan.MINIMUM_INTERVAL = 0
    yield
    scan.gravitymons.clear()
    scan.pressuremons.clear()
    scan.gravitymon_device_tokens.clear()
    scan.pressuremon_device_tokens.clear()
