"""Generate simulator readings and send them through the permanent HTTP API."""

import argparse
import json
import random
import time
from typing import Callable, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_URL = "http://127.0.0.1:5000/api/sensor"
DEFAULT_INTERVAL = 1.0
DEFAULT_SEED = 42
SCENARIOS = (
    "NORMAL",
    "SOURCE_LEFT",
    "SOURCE_RIGHT",
    "SOURCE_NORTH",
    "SOURCE_SOUTH",
    "HIGH_CONDUCTIVITY",
    "HIGH_WATER",
    "CRITICAL",
)


def build_payload(
    scenario: str,
    *,
    seed: Optional[int] = None,
    rng: Optional[random.Random] = None,
    randomize: bool = True,
) -> Dict[str, object]:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown simulator scenario: {scenario}")

    random_source = rng or random.Random(seed)
    payload = {
        "water_level_cm": 5.0,
        "conductivity_ms_cm": 0.5,
        "north_rms_v": 0.05,
        "east_rms_v": 0.05,
        "south_rms_v": 0.05,
        "west_rms_v": 0.05,
        "device_id": "esp32-01",
        "calibration_version": "demo-identity-v1",
    }

    if scenario == "SOURCE_LEFT":
        payload["west_rms_v"] = 0.8
    elif scenario == "SOURCE_RIGHT":
        payload["east_rms_v"] = 0.8
    elif scenario == "SOURCE_NORTH":
        payload["north_rms_v"] = 0.8
    elif scenario == "SOURCE_SOUTH":
        payload["south_rms_v"] = 0.8
    elif scenario == "HIGH_CONDUCTIVITY":
        payload["conductivity_ms_cm"] = 3.0
    elif scenario == "HIGH_WATER":
        payload["water_level_cm"] = 30.0
    elif scenario == "CRITICAL":
        payload["east_rms_v"] = 1.2

    if randomize:
        payload["water_level_cm"] = _bounded(
            float(payload["water_level_cm"]) + random_source.uniform(-0.25, 0.25),
            0,
            100,
        )
        payload["conductivity_ms_cm"] = _bounded(
            float(payload["conductivity_ms_cm"])
            + random_source.uniform(-0.03, 0.03),
            0,
            10,
        )
        for field in (
            "north_rms_v",
            "east_rms_v",
            "south_rms_v",
            "west_rms_v",
        ):
            payload[field] = _bounded(
                float(payload[field]) + random_source.uniform(-0.01, 0.01),
                0,
                2,
            )

    return payload


def send_payload(
    url: str,
    payload: Dict[str, object],
    *,
    opener: Callable = urlopen,
    timeout: float = 5.0,
) -> Dict[str, object]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with opener(request, timeout=timeout) as response:
            status = response.getcode()
    except HTTPError as error:
        return {"ok": False, "status": error.code, "message": str(error)}
    except (URLError, TimeoutError, OSError) as error:
        return {"ok": False, "status": None, "message": str(error)}

    if 200 <= status < 300:
        return {"ok": True, "status": status}
    return {"ok": False, "status": status, "message": f"HTTP {status}"}


def run_simulator(
    *,
    url: str = DEFAULT_URL,
    scenario: str = "NORMAL",
    interval: float = DEFAULT_INTERVAL,
    count: Optional[int] = None,
    seed: int = DEFAULT_SEED,
    randomize: bool = True,
    opener: Callable = urlopen,
    sleep_fn: Callable[[float], None] = time.sleep,
    output: Callable[[str], None] = print,
    timeout: float = 5.0,
) -> int:
    if count is not None and count < 1:
        raise ValueError("count must be positive")
    if interval < 0:
        raise ValueError("interval must be nonnegative")

    random_source = random.Random(seed)
    sent = 0
    try:
        while count is None or sent < count:
            payload = build_payload(
                scenario,
                rng=random_source,
                randomize=randomize,
            )
            try:
                result = send_payload(
                    url,
                    payload,
                    opener=opener,
                    timeout=timeout,
                )
            except Exception as error:  # Network client must not stop the stream.
                result = {"ok": False, "status": None, "message": str(error)}

            if result["ok"]:
                output(f"POST {result['status']}")
            else:
                output(f"POST failed: {result['message']}")

            sent += 1
            if count is not None and sent >= count:
                break
            sleep_fn(interval)
    except KeyboardInterrupt:
        output("Simulator stopped")

    return 0


def _bounded(value: float, lower: float, upper: float) -> float:
    return round(max(lower, min(upper, value)), 6)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mock ESP32 HTTP sensor simulator")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--scenario", choices=SCENARIOS, default="NORMAL")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    parser.add_argument("--count", type=int)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="send exact scenario fixtures without randomization",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return run_simulator(
        url=args.url,
        scenario=args.scenario,
        interval=args.interval,
        count=args.count,
        seed=args.seed,
        randomize=not args.deterministic,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
