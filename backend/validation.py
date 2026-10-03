"""Validation for the permanent HTTP sensor contract."""

import math
from typing import Any, Dict


REQUIRED_FIELDS = (
    "water_level_cm",
    "conductivity_ms_cm",
    "north_rms_v",
    "east_rms_v",
    "south_rms_v",
    "west_rms_v",
)
OPTIONAL_FIELDS = ("device_id", "calibration_version")
ALLOWED_FIELDS = frozenset(REQUIRED_FIELDS + OPTIONAL_FIELDS)


class ValidationError(Exception):
    """Expected request validation failure."""

    def __init__(self, message: str, field: str = "") -> None:
        self.code = "INVALID_READING"
        self.message = message
        self.field = field
        super().__init__(message)


def validate_sensor_payload(payload: Any, settings: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")

    for field in sorted(payload):
        if field not in ALLOWED_FIELDS:
            raise ValidationError(f"{field} is not a supported field", field)

    for field in REQUIRED_FIELDS:
        if field not in payload:
            raise ValidationError(f"{field} is required", field)

    normalized = dict(payload)
    normalized["device_id"] = payload.get("device_id", settings.device_id)
    normalized["calibration_version"] = payload.get(
        "calibration_version", settings.calibration_version
    )

    if normalized["device_id"] != settings.device_id:
        raise ValidationError("device_id must match configured device", "device_id")
    if normalized["calibration_version"] != settings.calibration_version:
        raise ValidationError(
            "calibration_version must match configured profile", "calibration_version"
        )

    for field in REQUIRED_FIELDS:
        value = normalized[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(
                f"{field} must be a finite nonnegative number", field
            )
        if not math.isfinite(value) or value < 0:
            raise ValidationError(
                f"{field} must be a finite nonnegative number", field
            )

        upper_bound = _upper_bound(field, settings)
        if value > upper_bound:
            raise ValidationError(
                f"{field} exceeds simulator envelope {upper_bound:g}", field
            )

    return normalized


def _upper_bound(field: str, settings: Any) -> float:
    if field in ("north_rms_v", "east_rms_v", "south_rms_v", "west_rms_v"):
        return settings.input_envelopes["directional_rms_v"][1]
    return settings.input_envelopes[field][1]
