import json
import math

import pytest


VALID_READING = {
    "water_level_cm": 14.2,
    "conductivity_ms_cm": 1.7,
    "north_rms_v": 0.12,
    "east_rms_v": 0.91,
    "south_rms_v": 0.10,
    "west_rms_v": 0.13,
}


def error_body(response):
    return response.get_json()["error"]


def test_valid_reading_is_accepted_after_storage_phase(client):
    response = client.post("/api/sensor", json=VALID_READING)

    assert response.status_code == 201
    assert response.get_json()["measurement"]["id"] == 1


def test_missing_required_field_returns_field_error(client):
    payload = dict(VALID_READING)
    del payload["north_rms_v"]

    response = client.post("/api/sensor", json=payload)

    assert response.status_code == 422
    assert error_body(response) == {
        "code": "INVALID_READING",
        "message": "north_rms_v is required",
        "field": "north_rms_v",
    }


def test_legacy_field_name_is_rejected(client):
    payload = dict(VALID_READING)
    payload["north"] = payload.pop("north_rms_v")

    response = client.post("/api/sensor", json=payload)

    assert response.status_code == 422
    assert error_body(response) == {
        "code": "INVALID_READING",
        "message": "north is not a supported field",
        "field": "north",
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("north_rms_v", -0.01, "north_rms_v must be a finite nonnegative number"),
        ("north_rms_v", "0.1", "north_rms_v must be a finite nonnegative number"),
        ("north_rms_v", True, "north_rms_v must be a finite nonnegative number"),
        ("north_rms_v", None, "north_rms_v must be a finite nonnegative number"),
        ("north_rms_v", math.nan, "north_rms_v must be a finite nonnegative number"),
        ("north_rms_v", math.inf, "north_rms_v must be a finite nonnegative number"),
        ("water_level_cm", 100.1, "water_level_cm exceeds simulator envelope 100"),
        (
            "conductivity_ms_cm",
            10.1,
            "conductivity_ms_cm exceeds simulator envelope 10",
        ),
        ("east_rms_v", 2.1, "east_rms_v exceeds simulator envelope 2"),
    ],
)
def test_invalid_reading_value_returns_field_error(client, field, value, message):
    payload = dict(VALID_READING)
    payload[field] = value

    response = client.post("/api/sensor", json=payload)

    assert response.status_code == 422
    assert error_body(response) == {
        "code": "INVALID_READING",
        "message": message,
        "field": field,
    }


def test_invalid_device_id_is_rejected(client):
    payload = dict(VALID_READING, device_id="esp32-other")

    response = client.post("/api/sensor", json=payload)

    assert response.status_code == 422
    assert error_body(response) == {
        "code": "INVALID_READING",
        "message": "device_id must match configured device",
        "field": "device_id",
    }


def test_invalid_calibration_version_is_rejected(client):
    payload = dict(VALID_READING, calibration_version="unknown-v1")

    response = client.post("/api/sensor", json=payload)

    assert response.status_code == 422
    assert error_body(response) == {
        "code": "INVALID_READING",
        "message": "calibration_version must match configured profile",
        "field": "calibration_version",
    }


def test_malformed_json_returns_structured_400(client):
    response = client.post(
        "/api/sensor",
        data='{"water_level_cm":',
        content_type="application/json",
    )

    assert response.status_code == 400
    assert error_body(response) == {
        "code": "INVALID_JSON",
        "message": "Request body must contain valid JSON",
    }


def test_non_object_json_returns_structured_422(client):
    response = client.post(
        "/api/sensor",
        data=json.dumps([VALID_READING]),
        content_type="application/json",
    )

    assert response.status_code == 422
    assert error_body(response) == {
        "code": "INVALID_READING",
        "message": "Request body must be a JSON object",
    }


def test_unsupported_content_type_returns_structured_415(client):
    response = client.post(
        "/api/sensor",
        data=json.dumps(VALID_READING),
        content_type="text/plain",
    )

    assert response.status_code == 415
    assert error_body(response) == {
        "code": "UNSUPPORTED_MEDIA_TYPE",
        "message": "Content-Type must be application/json",
    }


def test_oversized_body_returns_structured_413(client):
    response = client.post(
        "/api/sensor",
        data=json.dumps({"padding": "x" * 5000}),
        content_type="application/json",
    )

    assert response.status_code == 413
    assert error_body(response) == {
        "code": "PAYLOAD_TOO_LARGE",
        "message": "Request body must not exceed 4096 bytes",
    }
