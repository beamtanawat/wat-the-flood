"""Deterministic direction and prototype rule analysis."""

import math
from typing import Any, Dict, Mapping, Tuple


def analyze_reading(settings: Any, payload: Mapping[str, float]) -> Dict[str, Any]:
    vx_v = payload["east_rms_v"] - payload["west_rms_v"]
    vy_v = payload["north_rms_v"] - payload["south_rms_v"]
    gradient_v = math.sqrt(vx_v**2 + vy_v**2)

    direction, direction_reason = _direction(
        settings,
        vx_v=vx_v,
        vy_v=vy_v,
        gradient_v=gradient_v,
    )
    rule_risk = _rule_risk(settings, payload)

    return {
        "vx_v": vx_v,
        "vy_v": vy_v,
        "gradient_v": gradient_v,
        "direction": direction,
        "direction_reason": direction_reason,
        "rule_risk": rule_risk,
        "rule_version": settings.rule_version,
        "analysis_source": "RULE",
    }


def extract_features(
    payload: Mapping[str, float], analysis: Mapping[str, float]
) -> Tuple[float, ...]:
    """Return model features in the permanent training/runtime order."""

    return (
        payload["water_level_cm"],
        payload["conductivity_ms_cm"],
        payload["north_rms_v"],
        payload["east_rms_v"],
        payload["south_rms_v"],
        payload["west_rms_v"],
        analysis["vx_v"],
        analysis["vy_v"],
        analysis["gradient_v"],
    )


def _direction(settings: Any, *, vx_v: float, vy_v: float, gradient_v: float):
    at_low_signal_boundary = math.isclose(
        gradient_v,
        settings.low_signal_threshold_v,
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    if gradient_v < settings.low_signal_threshold_v and not at_low_signal_boundary:
        return None, "LOW_SIGNAL"

    axis_difference = abs(abs(vx_v) - abs(vy_v))
    if axis_difference <= settings.direction_tolerance_v or math.isclose(
        axis_difference,
        settings.direction_tolerance_v,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        return None, "AMBIGUOUS"

    if abs(vx_v) > abs(vy_v):
        return ("EAST" if vx_v > 0 else "WEST"), "DOMINANT_AXIS"
    return ("NORTH" if vy_v > 0 else "SOUTH"), "DOMINANT_AXIS"


def _rule_risk(settings: Any, payload: Mapping[str, float]) -> str:
    thresholds = settings.rule_thresholds
    maximum_voltage = max(
        payload["north_rms_v"],
        payload["east_rms_v"],
        payload["south_rms_v"],
        payload["west_rms_v"],
    )
    high_water = payload["water_level_cm"] >= thresholds["water_level_cm"]
    high_conductivity = (
        payload["conductivity_ms_cm"] >= thresholds["conductivity_ms_cm"]
    )

    if maximum_voltage >= thresholds["critical_voltage_v"] or (
        maximum_voltage >= thresholds["high_voltage_v"]
        and high_water
        and high_conductivity
    ):
        return "CRITICAL"
    if maximum_voltage >= thresholds["high_voltage_v"] or (
        maximum_voltage >= thresholds["monitor_voltage_v"]
        and (high_water or high_conductivity)
    ):
        return "HIGH"
    if maximum_voltage >= thresholds["monitor_voltage_v"] or high_water or high_conductivity:
        return "MONITOR"
    return "NORMAL"
