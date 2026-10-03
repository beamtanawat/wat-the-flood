"""Application configuration for the simulator profile."""

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_PROFILE_PATH = PROJECT_ROOT / "configuration" / "prototype.json"


@dataclass(frozen=True)
class Settings:
    mode: str
    profile_validated: bool
    device_id: str
    calibration_version: str
    max_body_bytes: int
    input_envelopes: Dict[str, tuple]
    direction_tolerance_v: float
    low_signal_threshold_v: float
    rule_thresholds: Dict[str, float]
    ai_model_path: Path
    ai_metadata_path: Path
    receipt_interval_seconds: float
    online_max_age_seconds: float
    stale_max_age_seconds: float
    rule_version: str
    database_path: Path


def load_settings(
    profile_path: Optional[Path] = None,
    overrides: Optional[Mapping[str, Any]] = None,
) -> Settings:
    path = Path(profile_path or DEFAULT_PROFILE_PATH)
    raw = json.loads(path.read_text(encoding="utf-8"))
    overrides = overrides or {}

    mode = overrides.get("MODE", raw["mode"])
    device_id = overrides.get("DEVICE_ID", raw["device_id"])
    calibration_version = overrides.get(
        "CALIBRATION_VERSION", raw["calibration_version"]
    )
    max_body_bytes = int(overrides.get("MAX_BODY_BYTES", raw["max_body_bytes"]))
    input_envelopes = raw["input_envelopes"]

    if mode not in ("simulator", "hardware"):
        raise ValueError("mode must be simulator or hardware")
    profile_validated = raw.get("profile_validated", False)
    if not isinstance(profile_validated, bool):
        raise ValueError("profile_validated must be boolean")
    if mode == "hardware" and profile_validated is not True:
        raise ValueError("Hardware mode requires validated hardware profile")
    if not device_id or not calibration_version:
        raise ValueError("Device and calibration identifiers are required")
    if max_body_bytes <= 0:
        raise ValueError("max_body_bytes must be positive")

    direction_tolerance_v = _finite_nonnegative(
        "direction_tolerance_v", raw["direction_tolerance_v"]
    )
    low_signal_threshold_v = _finite_nonnegative(
        "low_signal_threshold_v", raw["low_signal_threshold_v"]
    )
    raw_rule_thresholds = raw.get("rule_thresholds")
    required_thresholds = {
        "critical_voltage_v",
        "high_voltage_v",
        "monitor_voltage_v",
        "water_level_cm",
        "conductivity_ms_cm",
    }
    if not isinstance(raw_rule_thresholds, dict) or not required_thresholds <= set(
        raw_rule_thresholds
    ):
        raise ValueError("rule_thresholds must define all prototype thresholds")
    rule_thresholds = {
        key: _finite_nonnegative(key, value)
        for key, value in raw_rule_thresholds.items()
    }
    if not (
        rule_thresholds["monitor_voltage_v"]
        < rule_thresholds["high_voltage_v"]
        < rule_thresholds["critical_voltage_v"]
    ):
        raise ValueError("Voltage rule thresholds must increase by severity")
    try:
        receipt_interval_seconds = _finite_positive(
            "receipt_interval_seconds", raw["receipt_interval_seconds"]
        )
        online_max_age_seconds = _finite_nonnegative(
            "online_max_age_seconds", raw["online_max_age_seconds"]
        )
        stale_max_age_seconds = _finite_nonnegative(
            "stale_max_age_seconds", raw["stale_max_age_seconds"]
        )
    except KeyError as error:
        raise ValueError(f"Missing required profile setting: {error.args[0]}") from error
    if online_max_age_seconds >= stale_max_age_seconds:
        raise ValueError("online_max_age_seconds must be less than stale_max_age_seconds")
    for name, bounds in input_envelopes.items():
        if len(bounds) != 2:
            raise ValueError(f"{name} envelope must have lower and upper bounds")
        lower = _finite_nonnegative(f"{name} lower bound", bounds[0])
        upper = _finite_nonnegative(f"{name} upper bound", bounds[1])
        if lower > upper:
            raise ValueError(f"{name} envelope lower bound exceeds upper bound")

    return Settings(
        mode=mode,
        profile_validated=profile_validated,
        device_id=device_id,
        calibration_version=calibration_version,
        max_body_bytes=max_body_bytes,
        input_envelopes={
            key: (float(bounds[0]), float(bounds[1]))
            for key, bounds in input_envelopes.items()
        },
        direction_tolerance_v=direction_tolerance_v,
        low_signal_threshold_v=low_signal_threshold_v,
        rule_thresholds=rule_thresholds,
        ai_model_path=_resolve_path(
            _configured_value(
                overrides,
                "AI_MODEL_PATH",
                "WAT_THE_FLOOD_MODEL",
                raw["ai_model_path"],
            )
        ),
        ai_metadata_path=_resolve_path(
            _configured_value(
                overrides,
                "AI_MODEL_METADATA_PATH",
                "WAT_THE_FLOOD_MODEL_METADATA",
                raw["ai_metadata_path"],
            )
        ),
        receipt_interval_seconds=receipt_interval_seconds,
        online_max_age_seconds=online_max_age_seconds,
        stale_max_age_seconds=stale_max_age_seconds,
        rule_version=raw["rule_version"],
        database_path=_resolve_path(
            _configured_value(
                overrides,
                "DATABASE_PATH",
                "WAT_THE_FLOOD_DATABASE",
                PROJECT_ROOT / "data" / "wat-the-flood.sqlite3",
            )
        ),
    )


def _resolve_path(value: Any) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _configured_value(
    overrides: Mapping[str, Any], key: str, environment_key: str, default: Any
) -> Any:
    if overrides.get(key) is not None:
        return overrides[key]
    return os.getenv(environment_key, default)


def _finite_nonnegative(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite nonnegative number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return float(value)


def _finite_positive(name: str, value: Any) -> float:
    number = _finite_nonnegative(name, value)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number
