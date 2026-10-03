from datetime import datetime, timedelta, timezone

import pytest

from backend.device_health import calculate_device_status


def timestamp(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@pytest.mark.parametrize(
    ("age", "expected_status"),
    [
        (0, "ONLINE"),
        (5, "ONLINE"),
        (5.001, "STALE"),
        (30, "STALE"),
        (30.001, "OFFLINE"),
    ],
)
def test_status_boundaries_use_last_receipt_age(age, expected_status):
    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    result = calculate_device_status(
        "esp32-01",
        timestamp(now - timedelta(seconds=age)),
        now,
    )

    assert result["status"] == expected_status
    assert result["age_seconds"] == pytest.approx(age, abs=0.001)


def test_future_timestamp_clamps_age_to_zero():
    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)

    result = calculate_device_status(
        "esp32-01",
        timestamp(now + timedelta(seconds=10)),
        now,
    )

    assert result["status"] == "ONLINE"
    assert result["age_seconds"] == 0


def test_no_reading_is_offline():
    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)

    assert calculate_device_status("esp32-01", None, now) == {
        "device_id": "esp32-01",
        "status": "OFFLINE",
        "last_received_at": None,
        "age_seconds": None,
    }
