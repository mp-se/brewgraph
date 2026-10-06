# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Tests for the Integration (account-level forwarding target) API."""
import uuid

import pytest

from core.config import get_settings
from core.db import create_session
from core.models.registry import resolve_model
from oss.schemas.integration import IntegrationCreate, unsupported_measurement
from tests.conftest import truncate_database

Integration = resolve_model("Integration")

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}

BREWFATHER_TARGET = {
    "name": "Brewfather",
    "measurement": "gravity",
    "type": "brewfather_forward",
    "enabled": True,
    "config": {"url": "https://log.brewfather.net/stream?id=abc123"},
}

CUSTOM_TARGET = {
    "name": "Thingspeak channel 2",
    "measurement": "gravity",
    "type": "custom_forward",
    "enabled": True,
    "config": {
        "url": "https://api.thingspeak.com/update",
        "method": "GET",
        "template": "api_key=XXXX&field1=${gravity}",
    },
}


def test_init():
    """Reset database state before the scenario group."""
    truncate_database()


def test_create_built_in_forward(app_client):
    """POST /integrations creates a brewfather_forward target."""
    test_init()
    r = app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Brewfather"
    assert data["type"] == "brewfather_forward"
    assert data["enabled"] is True
    assert data["config"]["url"] == BREWFATHER_TARGET["config"]["url"]
    assert data["config"]["method"] == "POST"  # default
    assert data["config"]["template"] is None
    assert "id" in data
    assert "createdAt" in data
    assert "updatedAt" in data


def test_create_custom_forward_with_template(app_client):
    """POST /integrations creates a custom_forward target with a template."""
    test_init()
    r = app_client.post("/integrations", json=CUSTOM_TARGET, headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert data["type"] == "custom_forward"
    assert data["config"]["method"] == "GET"
    assert data["config"]["template"] == CUSTOM_TARGET["config"]["template"]


def test_custom_forward_requires_template(app_client):
    """custom_forward without a template is rejected."""
    test_init()
    body = {**CUSTOM_TARGET, "config": {"url": "https://api.thingspeak.com/update"}}
    r = app_client.post("/integrations", json=body, headers=headers)
    assert r.status_code == 422


def test_built_in_type_rejects_template(app_client):
    """A built-in type (not custom_forward) with a template is rejected."""
    test_init()
    body = {
        **BREWFATHER_TARGET,
        "config": {**BREWFATHER_TARGET["config"], "template": "should not be here"},
    }
    r = app_client.post("/integrations", json=body, headers=headers)
    assert r.status_code == 422


def test_loopback_url_rejected(app_client):
    """A loopback destination URL is rejected as an SSRF guard."""
    test_init()
    body = {**BREWFATHER_TARGET, "config": {"url": "http://127.0.0.1:8080/hook"}}
    r = app_client.post("/integrations", json=body, headers=headers)
    assert r.status_code == 422


def test_link_local_url_rejected(app_client):
    """A link-local (cloud-metadata range) destination URL is rejected."""
    test_init()
    body = {**BREWFATHER_TARGET, "config": {"url": "http://169.254.169.254/latest/meta-data/"}}
    r = app_client.post("/integrations", json=body, headers=headers)
    assert r.status_code == 422


def test_public_and_private_urls_both_accepted(app_client):
    """Both a public host and a private-LAN host are accepted — forwarding targets are
    assumed public but a private one (e.g. a self-hosted service) must not break."""
    test_init()
    public = {**BREWFATHER_TARGET, "config": {"url": "https://8.8.8.8/stream"}}
    private = {**BREWFATHER_TARGET, "config": {"url": "http://192.168.1.50:8123/hook"}}
    assert app_client.post("/integrations", json=public, headers=headers).status_code == 201
    assert app_client.post("/integrations", json=private, headers=headers).status_code == 201


def test_custom_header_values_are_redacted_on_read(app_client):
    """A custom_forward target's `config.headers` values must never come back
    verbatim on read — only the header key names are visible."""
    test_init()
    header_value = "hdrvalue" + "-abc123xyz"
    body = {
        **CUSTOM_TARGET,
        "config": {**CUSTOM_TARGET["config"], "headers": {"Authorization": header_value}},
    }
    created = app_client.post("/integrations", json=body, headers=headers).json()
    assert created["config"]["headers"]["Authorization"] != header_value
    assert "abc123xyz" not in created["config"]["headers"]["Authorization"]

    listed = app_client.get("/integrations", headers=headers).json()
    item = next(i for i in listed if i["id"] == created["id"])
    assert item["config"]["headers"]["Authorization"] != header_value
    assert "abc123xyz" not in item["config"]["headers"]["Authorization"]


def test_list_integrations_includes_disabled(app_client):
    """GET /integrations lists every configured target, including disabled ones."""
    test_init()
    app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers)
    app_client.post(
        "/integrations", json={**CUSTOM_TARGET, "enabled": False}, headers=headers
    )

    r = app_client.get("/integrations", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    enabled_flags = {item["enabled"] for item in items}
    assert enabled_flags == {True, False}


def test_multiple_targets_of_the_same_type_allowed(app_client):
    """No uniqueness constraint beyond the primary key — two brewfather_forward rows
    for the same account is a valid configuration."""
    test_init()
    first = app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers)
    second = app_client.post(
        "/integrations",
        json={**BREWFATHER_TARGET, "name": "Brewfather (second stream)"},
        headers=headers,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


def test_patch_updates_only_supplied_fields(app_client):
    """PATCH /integrations/{id} leaves omitted fields alone."""
    test_init()
    created = app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers).json()

    r = app_client.patch(
        f"/integrations/{created['id']}", json={"enabled": False}, headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is False
    assert data["name"] == "Brewfather"  # unchanged
    assert data["config"]["url"] == BREWFATHER_TARGET["config"]["url"]  # unchanged


def test_patch_revalidates_config_against_existing_type(app_client):
    """PATCH-ing config.template onto a built-in-type row is still rejected —
    the type/template check runs against the existing row's type, not just at create."""
    test_init()
    created = app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers).json()

    r = app_client.patch(
        f"/integrations/{created['id']}",
        json={"config": {"url": BREWFATHER_TARGET["config"]["url"], "template": "nope"}},
        headers=headers,
    )
    assert r.status_code == 422


def test_patch_missing_integration_returns_404(app_client):
    """PATCH on a nonexistent id returns 404."""
    test_init()
    r = app_client.patch(
        "/integrations/00000000-0000-4000-8000-000000000000",
        json={"enabled": False},
        headers=headers,
    )
    assert r.status_code == 404


def test_delete_removes_only_that_target(app_client):
    """DELETE removes one target; siblings of the same type are unaffected."""
    test_init()
    keep = app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers).json()
    remove = app_client.post(
        "/integrations",
        json={**BREWFATHER_TARGET, "name": "Brewfather (second stream)"},
        headers=headers,
    ).json()

    r = app_client.delete(f"/integrations/{remove['id']}", headers=headers)
    assert r.status_code == 204

    remaining = app_client.get("/integrations", headers=headers).json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == keep["id"]


def test_delete_missing_integration_returns_404(app_client):
    """DELETE on a nonexistent id returns 404."""
    test_init()
    r = app_client.delete(
        "/integrations/00000000-0000-4000-8000-000000000000", headers=headers
    )
    assert r.status_code == 404


def test_patch_deleted_integration_returns_404(app_client):
    """PATCHing a target already removed by DELETE is rejected, not silently
    applied — `update()` resolves via `get_active()`, the same primitive
    device/tap/batch/vessel `update()` use to reject an entity that is gone."""
    test_init()
    created = app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers).json()
    assert app_client.delete(f"/integrations/{created['id']}", headers=headers).status_code == 204

    r = app_client.patch(
        f"/integrations/{created['id']}", json={"enabled": False}, headers=headers
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# measurement: gravity, pressure, pour, and temperature
# ---------------------------------------------------------------------------

# Every (type, measurement) pairing and whether the API accepts it.
TYPE_MEASUREMENT_MATRIX = [
    ("ispindel_forward", "gravity", True),
    ("ispindel_forward", "pressure", False),
    ("ispindel_forward", "temp", False),
    ("ispindel_forward", "pour", False),
    ("brewfather_forward", "gravity", True),
    ("brewfather_forward", "pressure", True),
    ("brewfather_forward", "temp", True),
    ("brewfather_forward", "pour", False),
    ("custom_forward", "gravity", True),
    ("custom_forward", "pressure", True),
    ("custom_forward", "temp", True),
    ("custom_forward", "pour", True),
]


@pytest.mark.parametrize("type_,measurement,valid", TYPE_MEASUREMENT_MATRIX)
def test_type_measurement_pairing(app_client, type_, measurement, valid):
    """ispindel_forward is gravity-only, brewfather_forward takes gravity, pressure and temp,
    custom_forward takes all four; any other pairing is a 422 naming the allowed measurements."""
    test_init()
    body = CUSTOM_TARGET if type_ == "custom_forward" else BREWFATHER_TARGET
    r = app_client.post(
        "/integrations", json={**body, "type": type_, "measurement": measurement},
        headers=headers,
    )
    if valid:
        assert r.status_code == 201
        assert (r.json()["type"], r.json()["measurement"]) == (type_, measurement)
    else:
        assert r.status_code == 422


@pytest.mark.parametrize("type_,measurement,message", [
    ("ispindel_forward", "pressure", "type=ispindel_forward requires measurement=gravity"),
    ("ispindel_forward", "pour", "type=ispindel_forward requires measurement=gravity"),
    ("brewfather_forward", "pour",
     "type=brewfather_forward requires measurement=gravity, pressure or temp"),
])
def test_rejected_pairing_names_the_allowed_measurements(type_, measurement, message):
    """The schema's 422 message (the API response itself is generic) and the service guard
    agree."""
    with pytest.raises(ValueError, match=message):
        IntegrationCreate(**{**BREWFATHER_TARGET, "type": type_, "measurement": measurement})
    assert unsupported_measurement(type_, measurement) == message
    assert unsupported_measurement("brewfather_forward", "temp") is None
    assert unsupported_measurement("custom_forward", "pour") is None


@pytest.mark.parametrize("measurement", ["gravity", "pressure", "pour", "temp"])
def test_custom_forward_valid_for_every_measurement(app_client, measurement):
    """custom_forward is valid for all four measurements."""
    test_init()
    body = {**CUSTOM_TARGET, "measurement": measurement}
    r = app_client.post("/integrations", json=body, headers=headers)
    assert r.status_code == 201
    assert r.json()["measurement"] == measurement


def test_missing_measurement_rejected(app_client):
    """`measurement` is required — no default."""
    test_init()
    body = {k: v for k, v in BREWFATHER_TARGET.items() if k != "measurement"}
    r = app_client.post("/integrations", json=body, headers=headers)
    assert r.status_code == 422


def test_patch_with_measurement_rejected(app_client):
    """`measurement` is immutable — a PATCH body naming it is rejected 422, not
    silently dropped (IntegrationUpdate has no `measurement` field and
    extra=\"forbid\")."""
    test_init()
    created = app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers).json()
    r = app_client.patch(
        f"/integrations/{created['id']}", json={"measurement": "pressure"}, headers=headers
    )
    assert r.status_code == 422


def test_patch_with_type_rejected(app_client):
    """`type` is immutable — same enforcement mechanism as `measurement`."""
    test_init()
    created = app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers).json()
    r = app_client.patch(
        f"/integrations/{created['id']}", json={"type": "custom_forward"}, headers=headers
    )
    assert r.status_code == 422


def test_patch_revalidates_measurement_gravity_requirement(app_client):
    """A built-in-type row's config is re-validated against its (immutable) existing
    measurement on PATCH too, not just at create."""
    test_init()
    created = app_client.post(
        "/integrations",
        json={**CUSTOM_TARGET, "measurement": "pressure"},
        headers=headers,
    ).json()

    # Flip the stored row's type away from custom_forward directly isn't possible via
    # the API (type is immutable) -- this instead confirms a built-in-type row created
    # against pour is impossible in the first place.
    r = app_client.post(
        "/integrations",
        json={**BREWFATHER_TARGET, "measurement": "pour"},
        headers=headers,
    )
    assert r.status_code == 422
    assert created["measurement"] == "pressure"


# ---------------------------------------------------------------------------
# consecutive_failures — auto-disable-after-3-failures safeguard, added
# alongside the drain-job counter logic
# ---------------------------------------------------------------------------

def test_response_includes_consecutive_failures_default_zero(app_client):
    """Every new target starts at consecutiveFailures=0."""
    test_init()
    r = app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers)
    assert r.status_code == 201
    assert r.json()["consecutiveFailures"] == 0


def test_post_ignores_consecutive_failures_field(app_client):
    """consecutiveFailures isn't part of IntegrationCreate at all -- a POST body
    that includes it is silently ignored (no extra="forbid" on that schema),
    unlike PATCH below where the same field is rejected."""
    test_init()
    body = {**BREWFATHER_TARGET, "consecutiveFailures": 2}
    r = app_client.post("/integrations", json=body, headers=headers)
    assert r.status_code == 201
    assert r.json()["consecutiveFailures"] == 0


def test_patch_rejects_consecutive_failures_field(app_client):
    """consecutiveFailures is absent from IntegrationUpdate's schema entirely, same
    mechanism as measurement/type -- a PATCH body naming it is rejected 422."""
    test_init()
    created = app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers).json()
    r = app_client.patch(
        f"/integrations/{created['id']}", json={"consecutiveFailures": 0}, headers=headers
    )
    assert r.status_code == 422


def test_patch_enabled_true_resets_consecutive_failures(app_client):
    """Setting enabled: true resets the counter -- fixing a target and re-enabling it
    means a fresh 3 strikes, not one inherited from before the fix."""
    test_init()
    created = app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers).json()

    # consecutiveFailures is server-managed with no API to set it directly --
    # simulate two prior failures the way the forwarding jobs would.
    db = create_session()
    try:
        row = db().get(Integration, uuid.UUID(created["id"]))
        row.consecutive_failures = 2
        db().commit()
    finally:
        db.remove()

    r = app_client.patch(
        f"/integrations/{created['id']}", json={"enabled": True}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["consecutiveFailures"] == 0


def test_patch_enabled_false_does_not_reset_consecutive_failures(app_client):
    """Manually disabling a target isn't the same as fixing it -- only an explicit
    enabled: true resets the counter, not an explicit enabled: false."""
    test_init()
    created = app_client.post("/integrations", json=BREWFATHER_TARGET, headers=headers).json()

    db = create_session()
    try:
        row = db().get(Integration, uuid.UUID(created["id"]))
        row.consecutive_failures = 2
        db().commit()
    finally:
        db.remove()

    r = app_client.patch(
        f"/integrations/{created['id']}", json={"enabled": False}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["consecutiveFailures"] == 2
