# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""'Send test payload' sends exactly what the payload preview shows.

The device name is the target's own name, so each target sends a name of its own.
The dummy values pinned here are the literals of DUMMY_READINGS in
web/src/core/integrations/integrationPreview.ts (which pins the same literals on the client
side); change all three together.
"""
import json
from unittest.mock import AsyncMock

import pytest

from core.config import get_settings
from tests.conftest import truncate_database

HEADERS = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

DEVICE_ID = "00000000-0000-0000-0000-000000000001"
BATCH_ID = "00000000-0000-0000-0000-000000000002"
STAMP = "2026-01-01T12:00:00+00:00"

# measurement -> (template, the JSON the documented dummy reading renders it to)
CUSTOM_CASES = {
    "gravity": (
        '{"name":"${deviceName}","deviceId":"${deviceId}","chipId":"${chipId}",'
        '"batchId":"${batchId}","gravity":${gravity},"temperature":${temperature},'
        '"angle":${angle},"velocity":${velocity},"battery":${battery},"rssi":${rssi},'
        '"timestamp":"${timestamp}"}',
        {
            "name": "test delivery", "deviceId": DEVICE_ID, "chipId": "a1b2c3",
            "batchId": BATCH_ID, "gravity": 1.042, "temperature": 20.5, "angle": 45.2,
            "velocity": 0.15, "battery": 3.98, "rssi": -62, "timestamp": STAMP,
        },
    ),
    "pressure": (
        '{"name":"${deviceName}","deviceId":"${deviceId}","chipId":"${chipId}",'
        '"batchId":"${batchId}","pressure":${pressure},"temperature":${temperature},'
        '"battery":${battery},"rssi":${rssi},"timestamp":"${timestamp}"}',
        {
            "name": "test delivery", "deviceId": DEVICE_ID, "chipId": "a1b2c3",
            "batchId": BATCH_ID, "pressure": 12.5, "temperature": 4.0, "battery": 3.98,
            "rssi": -62, "timestamp": STAMP,
        },
    ),
    "temp": (
        '{"name":"${deviceName}","deviceId":"${deviceId}","chipId":"${chipId}",'
        '"batchId":"${batchId}","temperature":${temperature},"tempType":"${tempType}",'
        '"battery":${battery},"rssi":${rssi},"timestamp":"${timestamp}"}',
        {
            "name": "test delivery", "deviceId": DEVICE_ID, "chipId": "a1b2c3",
            "batchId": BATCH_ID, "temperature": 18.5, "tempType": "beer", "battery": 3.98,
            "rssi": -62, "timestamp": STAMP,
        },
    ),
    "pour": (
        '{"tapId":"${tapId}","tapName":"${tapName}","vesselId":"${vesselId}",'
        '"batchId":"${batchId}","pourAmount":${pourAmount},'
        '"volumeRemaining":${volumeRemaining},"timestamp":"${timestamp}"}',
        {
            "tapId": "00000000-0000-0000-0000-000000000003", "tapName": "Tap 1",
            "vesselId": "00000000-0000-0000-0000-000000000004", "batchId": BATCH_ID,
            "pourAmount": 0.33, "volumeRemaining": 12.4, "timestamp": STAMP,
        },
    ),
}


def _create(app_client, measurement, type_, config):
    """Create an Integration on a public IP so the outbound safety check stays exercised."""
    response = app_client.post(
        "/integrations",
        json={
            "name": "test delivery", "measurement": measurement, "type": type_,
            "enabled": True, "config": config,
        },
        headers=HEADERS,
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    monkeypatch.setattr("oss.services.integration.increment_key", lambda *_a, **_k: 1)


def test_ispindel_test_delivery_sends_what_the_real_builder_builds(app_client, monkeypatch):
    """The iSpindel body has the chip id, battery and interval, and no [SG] added."""
    truncate_database()
    target = _create(app_client, "gravity", "ispindel_forward", {"url": "https://8.8.8.8/i"})
    post = AsyncMock(return_value=True)
    monkeypatch.setattr("oss.services.integration.http_post", post)
    response = app_client.post(f"/integrations/{target['id']}/test", headers=HEADERS)
    assert response.json() == {"outcome": "delivered"}
    assert post.await_args.args[1] == {
        "name": "test delivery", "ID": "a1b2c3", "angle": 45.2, "temperature": 20.5,
        "temp_units": "C", "battery": 3.98, "gravity": 1.042, "interval": 900, "RSSI": -62,
    }


def test_brewfather_test_delivery_sends_what_the_real_builder_builds(app_client, monkeypatch):
    """The Brewfather body carries battery/angle/rssi and the [SG] name suffix."""
    truncate_database()
    target = _create(app_client, "gravity", "brewfather_forward", {"url": "https://8.8.8.8/b"})
    post = AsyncMock(return_value=True)
    monkeypatch.setattr("oss.services.integration.http_post", post)
    response = app_client.post(f"/integrations/{target['id']}/test", headers=HEADERS)
    assert response.json() == {"outcome": "delivered"}
    assert post.await_args.args[1] == {
        "name": "test delivery[SG]", "temp": 20.5, "temp_unit": "C", "gravity": 1.042,
        "gravity_unit": "G", "battery": 3.98, "angle": 45.2, "rssi": -62,
    }


def test_brewfather_pressure_test_delivery_sends_what_the_real_builder_builds(
    app_client, monkeypatch
):
    """Pressure goes out in kPa with the reading's own temperature and no [SG] on the name."""
    truncate_database()
    target = _create(app_client, "pressure", "brewfather_forward", {"url": "https://8.8.8.8/b"})
    post = AsyncMock(return_value=True)
    monkeypatch.setattr("oss.services.integration.http_post", post)
    response = app_client.post(f"/integrations/{target['id']}/test", headers=HEADERS)
    assert response.json() == {"outcome": "delivered"}
    assert post.await_args.args[1] == {
        "name": "test delivery", "pressure": 12.5, "pressure_unit": "KPA", "temp": 4.0,
        "temp_unit": "C", "battery": 3.98, "rssi": -62,
    }


def test_brewfather_temp_test_delivery_sends_what_the_real_builder_builds(
    app_client, monkeypatch
):
    """Temperature goes out in Celsius with the device name as is."""
    truncate_database()
    target = _create(app_client, "temp", "brewfather_forward", {"url": "https://8.8.8.8/b"})
    post = AsyncMock(return_value=True)
    monkeypatch.setattr("oss.services.integration.http_post", post)
    response = app_client.post(f"/integrations/{target['id']}/test", headers=HEADERS)
    assert response.json() == {"outcome": "delivered"}
    assert post.await_args.args[1] == {
        "name": "test delivery", "temp": 18.5, "temp_unit": "C", "battery": 3.98, "rssi": -62,
    }


@pytest.mark.parametrize("measurement", sorted(CUSTOM_CASES))
def test_custom_test_delivery_renders_the_documented_dummy_reading(
    app_client, monkeypatch, measurement
):
    """Every token of each measurement renders to the documented dummy value."""
    truncate_database()
    template, expected = CUSTOM_CASES[measurement]
    target = _create(
        app_client, measurement, "custom_forward",
        {"url": "https://8.8.8.8/c", "method": "POST", "template": template},
    )
    post = AsyncMock(return_value=True)
    monkeypatch.setattr("oss.jobs._forward_common.http_post", post)
    response = app_client.post(f"/integrations/{target['id']}/test", headers=HEADERS)
    assert response.json() == {"outcome": "delivered"}
    assert post.await_args.args[1] == expected
    assert json.loads(post.await_args.kwargs["raw"]) == expected


def test_custom_get_test_delivery_renders_the_query_string(app_client, monkeypatch):
    """A GET target receives the rendered query string of the same dummy reading."""
    truncate_database()
    target = _create(
        app_client, "gravity", "custom_forward",
        {"url": "https://8.8.8.8/c", "method": "GET", "template": "g=${gravity}&t=${temperature}"},
    )
    get = AsyncMock(return_value=True)
    monkeypatch.setattr("oss.jobs._forward_common.http_get", get)
    app_client.post(f"/integrations/{target['id']}/test", headers=HEADERS)
    assert get.await_args.args[1] == "g=1.042&t=20.5"


def test_each_target_sends_its_own_name_so_a_per_name_limit_cannot_throttle_another(
    app_client, monkeypatch
):
    """Two Brewfather targets tested back to back send two different device names."""
    truncate_database()
    post = AsyncMock(return_value=True)
    monkeypatch.setattr("oss.services.integration.http_post", post)
    names = []
    for name in ("Fermenter A", "Fermenter B"):
        target = app_client.post(
            "/integrations",
            json={"name": name, "measurement": "pressure", "type": "brewfather_forward",
                  "enabled": True, "config": {"url": "https://8.8.8.8/b"}},
            headers=HEADERS,
        ).json()
        app_client.post(f"/integrations/{target['id']}/test", headers=HEADERS)
        names.append(post.await_args.args[1]["name"])
    assert names == ["Fermenter A", "Fermenter B"]


def test_test_send_is_limited_to_twenty_per_target_per_hour(app_client, monkeypatch):
    """The 21st test of one target in an hour is refused with 429."""
    truncate_database()
    target = _create(app_client, "gravity", "ispindel_forward", {"url": "https://8.8.8.8/i"})
    monkeypatch.setattr("oss.services.integration.http_post", AsyncMock(return_value=True))
    for count in (20, 21):
        monkeypatch.setattr("oss.services.integration.increment_key", lambda *_a, c=count, **_k: c)
        response = app_client.post(f"/integrations/{target['id']}/test", headers=HEADERS)
        assert response.status_code == (200 if count == 20 else 429)
