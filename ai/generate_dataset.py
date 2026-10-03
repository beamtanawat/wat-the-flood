"""Generate reproducible synthetic rows for ML pipeline development."""

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any, Dict, Optional

from backend.analyzer import analyze_reading, extract_features
from config import load_settings


FEATURE_NAMES = [
    "water_level_cm",
    "conductivity_ms_cm",
    "north_rms_v",
    "east_rms_v",
    "south_rms_v",
    "west_rms_v",
    "vx_v",
    "vy_v",
    "gradient_v",
]
LABELS = ("NORMAL", "MONITOR", "HIGH", "CRITICAL")
GENERATOR_VERSION = "synthetic-v1"


def generate_dataset(
    output_dir: Path,
    *,
    samples_per_class: int = 2500,
    seed: int = 42,
    settings: Optional[Any] = None,
) -> Dict[str, Path]:
    if samples_per_class < 1:
        raise ValueError("samples_per_class must be positive")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    settings = settings or load_settings()
    rng = random.Random(seed)
    rows = []

    for label in LABELS:
        class_rows = []
        attempts = 0
        max_attempts = max(100, samples_per_class * 100)
        while len(class_rows) < samples_per_class and attempts < max_attempts:
            attempts += 1
            payload, scenario = _candidate(label, rng)
            analysis = analyze_reading(settings, payload)
            if analysis["rule_risk"] != label:
                continue
            features = extract_features(payload, analysis)
            row = dict(zip(FEATURE_NAMES, features))
            row.update(
                {
                    "label": label,
                    "scenario": scenario,
                    "sample_id": f"sample-{len(rows) + len(class_rows) + 1:05d}",
                }
            )
            class_rows.append(row)
        if len(class_rows) != samples_per_class:
            raise RuntimeError(
                f"Could not fill {label} quota after {max_attempts} attempts"
            )
        rows.extend(class_rows)

    dataset_path = output_dir / "dataset.csv"
    with dataset_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=FEATURE_NAMES + ["label", "scenario", "sample_id"],
        )
        writer.writeheader()
        writer.writerows(rows)

    metadata_path = output_dir / "dataset_metadata.json"
    metadata = {
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "samples_per_class": samples_per_class,
        "total_rows": len(rows),
        "feature_names": FEATURE_NAMES,
        "units": {
            "water_level_cm": "cm",
            "conductivity_ms_cm": "mS/cm",
            "north_rms_v": "V RMS",
            "east_rms_v": "V RMS",
            "south_rms_v": "V RMS",
            "west_rms_v": "V RMS",
            "vx_v": "V",
            "vy_v": "V",
            "gradient_v": "V",
        },
        "rule_version": settings.rule_version,
        "calibration_version": settings.calibration_version,
        "mode": settings.mode,
        "synthetic_only": True,
        "label_source": "prototype rule labels",
        "excluded_model_fields": ["scenario", "sample_id", "label"],
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"dataset": dataset_path, "metadata": metadata_path}


def _candidate(label: str, rng: random.Random):
    directions = {
        "north_rms_v": 0.05,
        "east_rms_v": 0.05,
        "south_rms_v": 0.05,
        "west_rms_v": 0.05,
    }
    channel_names = tuple(directions)
    variant = rng.randrange(4)

    if label == "NORMAL":
        water = rng.uniform(0, 19.9)
        conductivity = rng.uniform(0, 1.9)
        tied_value = rng.uniform(0.01, 0.15)
        for channel in channel_names:
            directions[channel] = tied_value
        scenario = "NORMAL_TIED_LOW_SIGNAL"
        if variant:
            selected = channel_names[variant % len(channel_names)]
            directions[selected] = rng.uniform(0.0, 0.19)
            scenario = "NORMAL_DIRECTIONAL_BALANCE"
        return _payload(water, conductivity, directions), scenario

    if label == "MONITOR":
        if variant == 0:
            directions[channel_names[0]] = 0.2
            scenario = "MONITOR_VOLTAGE_BOUNDARY"
            return _payload(rng.uniform(0, 19.9), rng.uniform(0, 1.9), directions), scenario
        if variant == 1:
            scenario = "MONITOR_HIGH_WATER"
            return _payload(rng.uniform(20, 40), rng.uniform(0, 1.9), directions), scenario
        if variant == 2:
            scenario = "MONITOR_HIGH_CONDUCTIVITY"
            return _payload(rng.uniform(0, 19.9), rng.uniform(2, 4), directions), scenario
        directions[channel_names[1]] = rng.uniform(0.2, 0.25)
        return _payload(rng.uniform(0, 19.9), rng.uniform(0, 1.9), directions), "MONITOR_LOW_VOLTAGE"

    if label == "HIGH":
        if variant == 0:
            directions[channel_names[1]] = 0.5
            scenario = "HIGH_VOLTAGE_BOUNDARY"
            return _payload(rng.uniform(0, 19.9), rng.uniform(0, 1.9), directions), scenario
        if variant == 1:
            directions[channel_names[2]] = rng.uniform(0.2, 0.49)
            scenario = "HIGH_WATER_COMBINATION"
            return _payload(rng.uniform(20, 40), rng.uniform(0, 1.9), directions), scenario
        if variant == 2:
            directions[channel_names[3]] = rng.uniform(0.2, 0.49)
            scenario = "HIGH_CONDUCTIVITY_COMBINATION"
            return _payload(rng.uniform(0, 19.9), rng.uniform(2, 4), directions), scenario
        elevated = rng.uniform(0.5, 0.7)
        for channel in channel_names:
            directions[channel] = elevated
        return _payload(rng.uniform(0, 19.9), rng.uniform(0, 1.9), directions), "HIGH_UNIFORM_ELEVATED"

    if variant == 0:
        directions[channel_names[1]] = 1.0
        return _payload(rng.uniform(0, 19.9), rng.uniform(0, 1.9), directions), "CRITICAL_VOLTAGE_BOUNDARY"
    if variant == 1:
        directions[channel_names[2]] = 0.5
        return _payload(
            20.0 + rng.uniform(0, 0.05),
            2.0 + rng.uniform(0, 0.05),
            directions,
        ), "CRITICAL_COMBINED_BOUNDARY"
    directions[channel_names[0]] = rng.uniform(1.0, 1.3)
    return _payload(rng.uniform(20, 60), rng.uniform(2, 6), directions), "CRITICAL_JOINT_ELEVATION"


def _payload(water, conductivity, directions):
    return {
        "water_level_cm": round(water, 6),
        "conductivity_ms_cm": round(conductivity, 6),
        **{key: round(value, 6) for key, value in directions.items()},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate WAT THE FLOOD synthetic data")
    parser.add_argument("--output-dir", default="ai")
    parser.add_argument("--samples-per-class", type=int, default=2500)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    paths = generate_dataset(
        Path(args.output_dir),
        samples_per_class=args.samples_per_class,
        seed=args.seed,
    )
    print(f"Wrote {paths['dataset']}")
    print(f"Wrote {paths['metadata']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
