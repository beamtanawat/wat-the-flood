"""Device status derived from last successfully persisted receipt time."""

from datetime import datetime, timezone
from typing import Optional


ONLINE_MAX_AGE_SECONDS = 5.0
STALE_MAX_AGE_SECONDS = 30.0


def calculate_device_status(
    device_id: str,
    last_received_at: Optional[str],
    now: datetime,
    online_max_age_seconds: float = ONLINE_MAX_AGE_SECONDS,
    stale_max_age_seconds: float = STALE_MAX_AGE_SECONDS,
):
    if last_received_at is None:
        return {
            "device_id": device_id,
            "status": "OFFLINE",
            "last_received_at": None,
            "age_seconds": None,
        }

    received_at = datetime.fromisoformat(last_received_at.replace("Z", "+00:00"))
    age_seconds = max(0.0, (now - received_at).total_seconds())
    if age_seconds <= online_max_age_seconds:
        status = "ONLINE"
    elif age_seconds <= stale_max_age_seconds:
        status = "STALE"
    else:
        status = "OFFLINE"
    return {
        "device_id": device_id,
        "status": status,
        "last_received_at": last_received_at,
        "age_seconds": age_seconds,
    }


def utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
