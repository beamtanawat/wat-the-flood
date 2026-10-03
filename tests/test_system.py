import json
from urllib.parse import urlparse

from app import create_app
from simulator.mock_esp32 import build_payload, send_payload


class ClientResponse:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getcode(self):
        return self.response.status_code


def test_simulator_http_contract_reaches_database(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": str(tmp_path / "measurements.sqlite3"),
            "AI_MODEL_PATH": str(tmp_path / "missing-model.joblib"),
            "AI_MODEL_METADATA_PATH": str(tmp_path / "missing-model.json"),
        }
    )
    client = app.test_client()

    def opener(request, timeout):
        del timeout
        parsed = urlparse(request.full_url)
        response = client.open(
            parsed.path,
            method=request.method,
            data=request.data,
            content_type=request.get_header("Content-type"),
        )
        return ClientResponse(response)

    payload = build_payload("SOURCE_RIGHT", randomize=False)
    result = send_payload(
        "http://testserver/api/sensor",
        payload,
        opener=opener,
    )

    latest = client.get("/api/latest").get_json()["measurement"]
    assert result == {"ok": True, "status": 201}
    assert latest["direction"] == "EAST"
    assert latest["east_rms_v"] == 0.8
    assert latest["device_id"] == "esp32-01"


def test_dashboard_latest_exposes_current_state_after_simulator_post(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": str(tmp_path / "measurements.sqlite3"),
            "AI_MODEL_PATH": str(tmp_path / "missing-model.joblib"),
            "AI_MODEL_METADATA_PATH": str(tmp_path / "missing-model.json"),
        }
    )
    client = app.test_client()
    response = client.post("/api/sensor", json=build_payload("CRITICAL", randomize=False))

    assert response.status_code == 201
    latest = client.get("/api/latest").get_json()
    assert latest["measurement"]["rule_risk"] == "CRITICAL"
    assert latest["device"]["status"] == "ONLINE"
