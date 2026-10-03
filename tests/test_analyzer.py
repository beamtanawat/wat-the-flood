import math

import pytest

from backend.analyzer import analyze_reading, extract_features
from config import load_settings


@pytest.fixture()
def settings():
    return load_settings()


def reading(**overrides):
    payload = {
        "water_level_cm": 5.0,
        "conductivity_ms_cm": 0.5,
        "north_rms_v": 0.05,
        "east_rms_v": 0.05,
        "south_rms_v": 0.05,
        "west_rms_v": 0.05,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("field", "expected_direction"),
    [
        ("east_rms_v", "EAST"),
        ("west_rms_v", "WEST"),
        ("north_rms_v", "NORTH"),
        ("south_rms_v", "SOUTH"),
    ],
)
def test_dominant_axis_returns_cardinal_direction(settings, field, expected_direction):
    result = analyze_reading(settings, reading(**{field: 0.8}))

    assert result["direction"] == expected_direction
    assert result["direction_reason"] == "DOMINANT_AXIS"


def test_low_signal_has_no_direction(settings):
    result = analyze_reading(settings, reading())

    assert result["direction"] is None
    assert result["direction_reason"] == "LOW_SIGNAL"
    assert result["gradient_v"] == 0.0


def test_equal_axes_are_ambiguous(settings):
    result = analyze_reading(
        settings,
        reading(north_rms_v=0.5, east_rms_v=0.5),
    )

    assert result["direction"] is None
    assert result["direction_reason"] == "AMBIGUOUS"


def test_axis_difference_at_tolerance_is_ambiguous(settings):
    result = analyze_reading(
        settings,
        reading(north_rms_v=0.49, east_rms_v=0.5),
    )

    assert result["direction"] is None
    assert result["direction_reason"] == "AMBIGUOUS"


def test_gradient_at_low_signal_boundary_is_not_low_signal(settings):
    result = analyze_reading(settings, reading(east_rms_v=0.06))

    assert result["gradient_v"] == pytest.approx(0.01)
    assert result["direction_reason"] == "AMBIGUOUS"


@pytest.mark.parametrize(
    ("overrides", "expected_risk"),
    [
        ({}, "NORMAL"),
        ({"conductivity_ms_cm": 2.0}, "MONITOR"),
        ({"water_level_cm": 20.0}, "MONITOR"),
        ({"east_rms_v": 0.2}, "MONITOR"),
        ({"east_rms_v": 0.2, "water_level_cm": 20.0}, "HIGH"),
        ({"east_rms_v": 0.5}, "HIGH"),
        ({"east_rms_v": 1.0}, "CRITICAL"),
        (
            {"east_rms_v": 0.5, "water_level_cm": 20.0, "conductivity_ms_cm": 2.0},
            "CRITICAL",
        ),
        ({"east_rms_v": 0.8, "west_rms_v": 0.8}, "HIGH"),
    ],
)
def test_prototype_rules_apply_in_descending_severity(settings, overrides, expected_risk):
    result = analyze_reading(settings, reading(**overrides))

    assert result["rule_risk"] == expected_risk
    assert result["analysis_source"] == "RULE"
    assert result["rule_version"] == "prototype-rules-v1"


def test_feature_order_matches_runtime_contract(settings):
    payload = reading(
        water_level_cm=14.2,
        conductivity_ms_cm=1.7,
        north_rms_v=0.12,
        east_rms_v=0.91,
        south_rms_v=0.10,
        west_rms_v=0.13,
    )
    result = analyze_reading(settings, payload)

    assert extract_features(payload, result) == pytest.approx(
        (
            14.2,
            1.7,
            0.12,
            0.91,
            0.10,
            0.13,
            0.78,
            0.02,
            math.sqrt(0.78**2 + 0.02**2),
        )
    )
