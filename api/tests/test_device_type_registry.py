# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for the device-type registry and its schema-layer enforcement."""
import json

import pytest
from pydantic import ValidationError

from core.config import get_settings
from core.enums import DeviceType
from oss.registries.device_types import device_type_registry
from oss.schemas.device import DeviceCreate
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def test_init():
    """Reset database state before test scenarios."""
    truncate_database()


@pytest.mark.parametrize("device_type", [member.value for member in DeviceType])
def test_every_current_oss_device_type_still_validates(device_type):
    """Every device type supported before the registry existed still validates."""
    assert device_type_registry.is_registered(device_type)
    # Must not raise.
    DeviceCreate(name="d", device_type=device_type)


def test_unregistered_device_type_rejected_by_schema():
    """A device_type not in the registry is rejected at the schema layer."""
    assert not device_type_registry.is_registered("not_a_real_device")
    with pytest.raises(ValidationError):
        DeviceCreate(name="d", device_type="not_a_real_device")


def test_unregistered_device_type_rejected_with_422(app_client):
    """POST /devices/ with an unregistered device_type returns 422, not a silent store."""
    test_init()
    payload = {"name": "Bad Device", "deviceType": "not_a_real_device"}
    resp = app_client.post("/devices", json=payload, headers=headers)
    assert resp.status_code == 422


def test_registered_device_type_still_creates(app_client):
    """A currently-registered device_type still creates a device end to end."""
    test_init()
    payload = {"name": "Good Device", "deviceType": "kegmon"}
    resp = app_client.post("/devices", json=payload, headers=headers)
    assert resp.status_code == 201
    assert json.loads(resp.text)["deviceType"] == "kegmon"
