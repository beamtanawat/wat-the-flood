import json
from urllib.error import URLError

from simulator.mock_esp32 import (
    DEFAULT_URL,
    build_payload,
    run_simulator,
    send_payload,
)


def test_source_scenarios_use_unit_qualified_direction_fields():
    assert build_payload("SOURCE_LEFT", randomize=False)["west_rms_v"] == 0.8
    assert build_payload("SOURCE_RIGHT", randomize=False)["east_rms_v"] == 0.8
    assert build_payload("SOURCE_NORTH", randomize=False)["north_rms_v"] == 0.8
    assert build_payload("SOURCE_SOUTH", randomize=False)["south_rms_v"] == 0.8


def test_deterministic_payload_contains_phase_one_metadata():
    payload = build_payload("NORMAL", randomize=False)

    assert payload == {
        "water_level_cm": 5.0,
        "conductivity_ms_cm": 0.5,
        "north_rms_v": 0.05,
        "east_rms_v": 0.05,
        "south_rms_v": 0.05,
        "west_rms_v": 0.05,
        "device_id": "esp32-01",
        "calibration_version": "demo-identity-v1",
    }


def test_seeded_random_payloads_are_reproducible():
    first = build_payload("NORMAL", seed=42)
    second = build_payload("NORMAL", seed=42)

    assert first == second


def test_send_payload_posts_json_and_returns_status():
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getcode(self):
            return 201

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["content_type"] = request.get_header("Content-type")
        captured["timeout"] = timeout
        return Response()

    payload = build_payload("NORMAL", randomize=False)
    result = send_payload(DEFAULT_URL, payload, opener=opener, timeout=5)

    assert result == {"ok": True, "status": 201}
    assert captured["url"] == DEFAULT_URL
    assert captured["body"] == payload
    assert captured["content_type"] == "application/json"
    assert captured["timeout"] == 5


def test_failed_posts_send_next_sample_without_retrying_same_sample():
    attempted_payloads = []
    messages = []

    def opener(request, timeout):
        del timeout
        attempted_payloads.append(json.loads(request.data.decode("utf-8")))
        raise URLError("backend unavailable")

    exit_code = run_simulator(
        url=DEFAULT_URL,
        scenario="NORMAL",
        interval=0,
        count=2,
        seed=42,
        opener=opener,
        sleep_fn=lambda seconds: None,
        output=messages.append,
    )

    assert exit_code == 0
    assert len(attempted_payloads) == 2
    assert attempted_payloads[0] != attempted_payloads[1]
    assert all("backend unavailable" in message for message in messages)


def test_keyboard_interrupt_exits_cleanly():
    messages = []

    def sleep(_seconds):
        raise KeyboardInterrupt

    exit_code = run_simulator(
        url=DEFAULT_URL,
        scenario="NORMAL",
        interval=1,
        count=None,
        seed=42,
        opener=lambda request, timeout: None,
        sleep_fn=sleep,
        output=messages.append,
    )

    assert exit_code == 0
    assert messages[-1] == "Simulator stopped"
