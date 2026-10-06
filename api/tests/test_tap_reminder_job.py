# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for oss/jobs/tap_reminder.py — tap-line cleaning reminder."""
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from core.config import get_settings
from oss.jobs.tap_reminder import task_tap_line_reminder
from tests.conftest import truncate_database

headers = {
    "Authorization": "Bearer " + get_settings().api_key.get_secret_value(),
    "Content-Type": "application/json",
}


def _create_tap(app_client, name: str = "Left Tap") -> str:
    return app_client.post(
        "/taps", json={"name": name, "tapNumber": 1}, headers=headers
    ).json()["id"]


def _set_last_cleaned(app_client, tap_id: str, days_ago: int) -> None:
    when = datetime.now(UTC) - timedelta(days=days_ago)
    app_client.patch(
        f"/taps/{tap_id}", json={"lastCleanedAt": when.isoformat()}, headers=headers
    )


@pytest.mark.asyncio
async def test_no_taps_runs_cleanly(app_client):  # pylint: disable=unused-argument
    """No taps at all -> the job runs cleanly, no reminders logged."""
    truncate_database()
    await task_tap_line_reminder()  # must not raise


@pytest.mark.asyncio
async def test_logs_reminder_for_overdue_tap(app_client):
    """A tap last cleaned more than 14 days ago logs a reminder."""
    truncate_database()
    tap_id = _create_tap(app_client)
    _set_last_cleaned(app_client, tap_id, days_ago=20)

    with patch("oss.jobs.tap_reminder.system_log_scheduler") as mock_log:
        await task_tap_line_reminder()

    mock_log.assert_called_once()
    message = mock_log.call_args.args[0]
    assert "Left Tap" in message
    assert "20 days" in message


@pytest.mark.asyncio
async def test_skips_recently_cleaned_tap(app_client):
    """A tap cleaned within the last 14 days does not log a reminder."""
    truncate_database()
    tap_id = _create_tap(app_client)
    _set_last_cleaned(app_client, tap_id, days_ago=5)

    with patch("oss.jobs.tap_reminder.system_log_scheduler") as mock_log:
        await task_tap_line_reminder()

    mock_log.assert_not_called()


@pytest.mark.asyncio
async def test_skips_never_cleaned_recently_created_tap(app_client):
    """A tap that has never been cleaned but was just created falls back to
    created_at, which is recent -> no reminder."""
    truncate_database()
    _create_tap(app_client)

    with patch("oss.jobs.tap_reminder.system_log_scheduler") as mock_log:
        await task_tap_line_reminder()

    mock_log.assert_not_called()
