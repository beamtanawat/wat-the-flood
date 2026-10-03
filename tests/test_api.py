from datetime import datetime, timedelta, timezone

import pytest


VALID_READING = {
    "water_level_cm": 14.2,
    "conductivity_ms_cm": 1.7,
    "north_rms_v": 0.12,
    "east_rms_v": 0.91,
    "south_rms_v": 0.10,
    "west_rms_v": 0.13,
}


def test_health_reports_prototype_and_ready_storage(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "prototype": True,
        "database": "READY",
        "model": "UNAVAILABLE",
    }


def test_health_does_not_expose_server_paths(client):
    response = client.get("/api/health")

    assert "DATABASE_PATH" not in response.get_data(as_text=True)
    assert "/Users/" not in response.get_data(as_text=True)


def test_sensor_post_persists_complete_measurement(client):
    response = client.post("/api/sensor", json=VALID_READING)

    assert response.status_code == 201
    measurement = response.get_json()["measurement"]
    assert measurement["id"] == 1
    assert measurement["device_id"] == "esp32-01"
    assert measurement["calibration_version"] == "demo-identity-v1"
    assert measurement["vx_v"] == 0.78
    assert measurement["vy_v"] == pytest.approx(0.02)
    assert measurement["direction"] == "EAST"
    assert measurement["direction_reason"] == "DOMINANT_AXIS"
    assert measurement["rule_risk"] == "HIGH"
    assert measurement["analysis_source"] == "RULE"
    assert measurement["ai_risk"] is None
    assert measurement["ai_confidence"] is None
    assert measurement["ai_status"] == "UNAVAILABLE"
    assert measurement["model_version"] is None
    assert measurement["timestamp"].endswith("Z")


def test_latest_before_first_reading_returns_empty_measurement(client):
    response = client.get("/api/latest")

    assert response.status_code == 200
    assert response.get_json() == {
        "measurement": None,
        "device": {
            "device_id": "esp32-01",
            "status": "OFFLINE",
            "last_received_at": None,
            "age_seconds": None,
        },
    }


def test_latest_returns_newest_measurement(client):
    client.post("/api/sensor", json=VALID_READING)
    newer = dict(VALID_READING, water_level_cm=30.0)
    client.post("/api/sensor", json=newer)

    response = client.get("/api/latest")

    assert response.status_code == 200
    assert response.get_json()["measurement"]["id"] == 2
    assert response.get_json()["measurement"]["water_level_cm"] == 30.0
    assert response.get_json()["device"]["status"] == "ONLINE"


def test_measurement_survives_application_restart(tmp_path):
    from app import create_app

    config = {
        "TESTING": True,
        "DATABASE_PATH": str(tmp_path / "measurements.sqlite3"),
        "AI_MODEL_PATH": str(tmp_path / "missing-model.joblib"),
        "AI_MODEL_METADATA_PATH": str(tmp_path / "missing-model.json"),
    }
    first_app = create_app(config)
    first_app.test_client().post("/api/sensor", json=VALID_READING)

    restarted_app = create_app(config)
    latest = restarted_app.test_client().get("/api/latest")

    assert latest.status_code == 200
    assert latest.get_json()["measurement"]["id"] == 1


def test_history_is_newest_first_and_returns_cursor(client):
    for water_level in (5.0, 20.0, 30.0):
        client.post(
            "/api/sensor",
            json=dict(VALID_READING, water_level_cm=water_level),
        )

    first_page = client.get("/api/history?limit=2")
    second_page = client.get(
        "/api/history?limit=2&before_id="
        + str(first_page.get_json()["next_before_id"])
    )

    assert [item["id"] for item in first_page.get_json()["measurements"]] == [3, 2]
    assert first_page.get_json()["next_before_id"] == 2
    assert [item["id"] for item in second_page.get_json()["measurements"]] == [1]
    assert second_page.get_json()["next_before_id"] is None


def test_history_rejects_invalid_bounds(client):
    for query in ("limit=0", "limit=1001", "limit=abc", "before_id=0", "before_id=abc"):
        response = client.get("/api/history?" + query)

        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "INVALID_QUERY"


def test_storage_failure_never_returns_success(tmp_path):
    storage_path = tmp_path / "storage-parent"
    storage_path.write_text("not a directory", encoding="utf-8")

    from app import create_app

    app = create_app({"TESTING": True, "DATABASE_PATH": str(storage_path)})
    response = app.test_client().post("/api/sensor", json=VALID_READING)

    assert response.status_code == 503
    assert response.get_json() == {
        "error": {
            "code": "STORAGE_UNAVAILABLE",
            "message": "Measurement storage is unavailable",
        }
    }


def test_rejected_request_does_not_refresh_device_status(tmp_path):
    from app import create_app

    current_time = [datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)]
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": str(tmp_path / "measurements.sqlite3"),
            "AI_MODEL_PATH": str(tmp_path / "missing-model.joblib"),
            "AI_MODEL_METADATA_PATH": str(tmp_path / "missing-model.json"),
            "CLOCK": lambda: current_time[0],
        }
    )
    client = app.test_client()
    assert client.post("/api/sensor", json={}).status_code == 422
    current_time[0] = current_time[0] + timedelta(seconds=6)

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.get_json()["device"]["status"] == "OFFLINE"
