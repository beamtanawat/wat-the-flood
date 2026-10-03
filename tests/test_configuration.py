import json
import math
from pathlib import Path

import pytest

from config import load_settings


def test_simulator_profile_declares_unit_contract():
    profile_path = Path(__file__).parents[1] / "configuration" / "prototype.json"
    profile = json.loads(profile_path.read_text())

    assert profile["mode"] == "simulator"
    assert profile["device_id"] == "esp32-01"
    assert profile["calibration_version"] == "demo-identity-v1"
    assert profile["input_envelopes"] == {
        "water_level_cm": [0, 100],
        "conductivity_ms_cm": [0, 10],
        "directional_rms_v": [0, 2],
    }


def profile_copy(tmp_path, **changes):
    source = Path(__file__).parents[1] / "configuration" / "prototype.json"
    profile = json.loads(source.read_text())
    profile.update(changes)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "changes",
    [
        {"direction_tolerance_v": -0.1},
        {"direction_tolerance_v": math.nan},
        {"max_body_bytes": 0},
        {
            "rule_thresholds": {
                "critical_voltage_v": 0.5,
                "high_voltage_v": 0.5,
                "monitor_voltage_v": 0.2,
                "water_level_cm": 20,
                "conductivity_ms_cm": 2,
            }
        },
    ],
)
def test_invalid_profile_settings_fail_startup(tmp_path, changes):
    path = profile_copy(tmp_path, **changes)

    with pytest.raises(ValueError):
        load_settings(path)


def test_hardware_mode_requires_validated_profile(tmp_path):
    path = profile_copy(
        tmp_path,
        mode="hardware",
        profile_validated=False,
        calibration_version="hardware-v1",
    )

    with pytest.raises(ValueError, match="validated hardware profile"):
        load_settings(path)


def test_validated_hardware_profile_has_explicit_provenance(tmp_path):
    path = profile_copy(
        tmp_path,
        mode="hardware",
        profile_validated=True,
        calibration_version="hardware-v1",
    )

    settings = load_settings(path)

    assert settings.mode == "hardware"
    assert settings.calibration_version == "hardware-v1"
    assert settings.profile_validated is True


def test_validation_preserves_engineering_units_without_calibration(tmp_path):
    from backend.validation import validate_sensor_payload

    settings = load_settings()
    payload = {
        "water_level_cm": 14.2,
        "conductivity_ms_cm": 1.7,
        "north_rms_v": 0.12,
        "east_rms_v": 0.91,
        "south_rms_v": 0.10,
        "west_rms_v": 0.13,
    }

    normalized = validate_sensor_payload(payload, settings)

    assert {key: normalized[key] for key in payload} == payload
