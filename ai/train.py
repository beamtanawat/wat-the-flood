"""Train and export the specified synthetic Random Forest model."""

import csv
import argparse
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import platform
from typing import Any, Dict, Optional

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from ai.evaluate import LABELS, evaluate_model, save_confusion_matrix
from ai.generate_dataset import FEATURE_NAMES
from config import load_settings


MODEL_VERSION = "rf-synthetic-v1"
SEED = 42
HYPERPARAMETERS = {
    "n_estimators": 200,
    "max_depth": 12,
    "min_samples_leaf": 2,
    "random_state": 42,
    "n_jobs": 1,
}


def train_model(
    dataset_path: Path,
    model_dir: Path,
    reports_dir: Path,
    *,
    seed: int = SEED,
    settings: Optional[Any] = None,
) -> Dict[str, Path]:
    rows = _read_rows(Path(dataset_path))
    x = [[float(row[name]) for name in FEATURE_NAMES] for row in rows]
    y = [row["label"] for row in rows]
    if set(y) != set(LABELS):
        raise ValueError("Dataset must contain all four risk labels")

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=seed,
        stratify=y,
    )
    duplicate_count = len(set(map(tuple, x_train)).intersection(map(tuple, x_test)))
    if duplicate_count:
        raise ValueError(
            f"Found {duplicate_count} duplicate feature rows across train/test split"
        )

    model = RandomForestClassifier(**HYPERPARAMETERS)
    model.fit(x_train, y_train)
    metrics = evaluate_model(
        model,
        x_train,
        y_train,
        x_test,
        y_test,
        FEATURE_NAMES,
        duplicate_count,
    )

    settings = settings or load_settings()
    model_dir = Path(model_dir)
    reports_dir = Path(reports_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "model.joblib"
    metadata_path = model_dir / "model_metadata.json"
    metrics_path = reports_dir / "metrics.json"
    confusion_path = reports_dir / "confusion_matrix.png"

    joblib.dump(model, model_path)
    metadata_path.write_text(
        json.dumps(
            {
                "model_version": MODEL_VERSION,
                "algorithm": "RandomForestClassifier",
                "feature_names": FEATURE_NAMES,
                "labels": list(LABELS),
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
                "seed": seed,
                "hyperparameters": HYPERPARAMETERS,
                "dependency_versions": {
                    "python": platform.python_version(),
                    "scikit-learn": _package_version("scikit-learn"),
                    "joblib": _package_version("joblib"),
                },
                "synthetic_only": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    save_confusion_matrix(metrics, confusion_path)
    return {
        "model": model_path,
        "model_metadata": metadata_path,
        "metrics": metrics_path,
        "confusion_matrix": confusion_path,
    }


def _read_rows(dataset_path: Path):
    with dataset_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = FEATURE_NAMES + ["label", "scenario", "sample_id"]
        if reader.fieldnames != expected:
            raise ValueError("Dataset fields do not match the runtime contract")
        rows = list(reader)
    if not rows:
        raise ValueError("Dataset is empty")
    return rows


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train WAT THE FLOOD Random Forest")
    parser.add_argument("--dataset", default="ai/dataset.csv")
    parser.add_argument("--model-dir", default="ai/models")
    parser.add_argument("--reports-dir", default="ai/reports")
    parser.add_argument("--seed", type=int, default=SEED)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    outputs = train_model(
        Path(args.dataset),
        Path(args.model_dir),
        Path(args.reports_dir),
        seed=args.seed,
    )
    for name, path in outputs.items():
        print(f"Wrote {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
