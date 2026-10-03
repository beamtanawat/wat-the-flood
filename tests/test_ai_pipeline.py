import csv
import json
from pathlib import Path

import joblib

from ai.generate_dataset import FEATURE_NAMES, generate_dataset
from ai.train import train_model
from backend.analyzer import analyze_reading, extract_features
from config import load_settings


VALID_READING = {
    "water_level_cm": 14.2,
    "conductivity_ms_cm": 1.7,
    "north_rms_v": 0.12,
    "east_rms_v": 0.91,
    "south_rms_v": 0.10,
    "west_rms_v": 0.13,
}


def test_dataset_generation_is_reproducible_and_balanced(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = generate_dataset(first_dir, samples_per_class=10, seed=42)
    second = generate_dataset(second_dir, samples_per_class=10, seed=42)

    assert first["dataset"].read_bytes() == second["dataset"].read_bytes()
    assert first["metadata"].read_bytes() == second["metadata"].read_bytes()

    with first["dataset"].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    counts = {}
    for row in rows:
        counts[row["label"]] = counts.get(row["label"], 0) + 1
    assert counts == {"NORMAL": 10, "MONITOR": 10, "HIGH": 10, "CRITICAL": 10}
    assert list(rows[0]) == FEATURE_NAMES + ["label", "scenario", "sample_id"]


def test_dataset_rows_use_shared_runtime_features_and_envelopes(tmp_path):
    paths = generate_dataset(tmp_path, samples_per_class=4, seed=42)
    settings = load_settings()

    with paths["dataset"].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        payload = {name: float(row[name]) for name in FEATURE_NAMES[:6]}
        analysis = analyze_reading(settings, payload)
        expected_features = extract_features(payload, analysis)
        actual_features = tuple(float(row[name]) for name in FEATURE_NAMES)
        assert actual_features == expected_features
        assert row["label"] == analysis["rule_risk"]
        assert 0 <= payload["water_level_cm"] <= 100
        assert 0 <= payload["conductivity_ms_cm"] <= 10
        assert all(0 <= payload[name] <= 2 for name in FEATURE_NAMES[2:6])


def test_dataset_metadata_records_provenance(tmp_path):
    paths = generate_dataset(tmp_path, samples_per_class=1, seed=42)

    metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))

    assert metadata["seed"] == 42
    assert metadata["rule_version"] == "prototype-rules-v1"
    assert metadata["calibration_version"] == "demo-identity-v1"
    assert metadata["synthetic_only"] is True
    assert metadata["feature_names"] == FEATURE_NAMES


def test_training_exports_compatible_model_and_complete_evaluation(tmp_path):
    dataset_paths = generate_dataset(tmp_path / "data", samples_per_class=20, seed=42)
    outputs = train_model(
        dataset_paths["dataset"],
        tmp_path / "models",
        tmp_path / "reports",
        seed=42,
    )

    assert outputs["model"].exists()
    assert outputs["model_metadata"].exists()
    assert outputs["metrics"].exists()
    assert outputs["confusion_matrix"].exists()

    metadata = json.loads(outputs["model_metadata"].read_text(encoding="utf-8"))
    metrics = json.loads(outputs["metrics"].read_text(encoding="utf-8"))
    assert metadata["feature_names"] == FEATURE_NAMES
    assert metadata["labels"] == ["NORMAL", "MONITOR", "HIGH", "CRITICAL"]
    assert metadata["seed"] == 42
    assert set(metrics["per_class"]) == set(metadata["labels"])
    assert len(metrics["confusion_matrix"]) == 4
    assert metrics["duplicate_feature_rows_across_split"] == 0

    model = joblib.load(outputs["model"])
    with dataset_paths["dataset"].open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    features = [[float(row[name]) for name in FEATURE_NAMES]]
    prediction = model.predict(features)[0]
    probabilities = model.predict_proba(features)[0]
    assert prediction in metadata["labels"]
    assert probabilities[model.classes_.tolist().index(prediction)] == max(probabilities)


def test_ai_prediction_is_stored_separately_from_rule_risk(tmp_path):
    from app import create_app

    dataset_paths = generate_dataset(tmp_path / "data", samples_per_class=5, seed=42)
    outputs = train_model(
        dataset_paths["dataset"],
        tmp_path / "models",
        tmp_path / "reports",
        seed=42,
    )
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": str(tmp_path / "measurements.sqlite3"),
            "AI_MODEL_PATH": str(outputs["model"]),
            "AI_MODEL_METADATA_PATH": str(outputs["model_metadata"]),
        }
    )

    response = app.test_client().post("/api/sensor", json=VALID_READING)

    measurement = response.get_json()["measurement"]
    assert response.status_code == 201
    assert measurement["rule_risk"] == "HIGH"
    assert measurement["analysis_source"] == "RULE"
    assert measurement["ai_status"] == "OK"
    assert measurement["ai_risk"] in {"NORMAL", "MONITOR", "HIGH", "CRITICAL"}
    assert 0 <= measurement["ai_confidence"] <= 1
    assert measurement["model_version"] == "rf-synthetic-v1"


def test_incompatible_model_does_not_block_rule_storage(tmp_path):
    from app import create_app

    dataset_paths = generate_dataset(tmp_path / "data", samples_per_class=5, seed=42)
    outputs = train_model(
        dataset_paths["dataset"],
        tmp_path / "models",
        tmp_path / "reports",
        seed=42,
    )
    metadata = json.loads(outputs["model_metadata"].read_text(encoding="utf-8"))
    metadata["rule_version"] = "different-rules"
    incompatible_metadata = tmp_path / "incompatible.json"
    incompatible_metadata.write_text(json.dumps(metadata), encoding="utf-8")
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": str(tmp_path / "measurements.sqlite3"),
            "AI_MODEL_PATH": str(outputs["model"]),
            "AI_MODEL_METADATA_PATH": str(incompatible_metadata),
        }
    )

    health = app.test_client().get("/api/health")
    response = app.test_client().post("/api/sensor", json=VALID_READING)

    assert health.status_code == 200
    assert health.get_json()["model"] == "INCOMPATIBLE"
    assert response.status_code == 201
    assert response.get_json()["measurement"]["ai_status"] == "INCOMPATIBLE"
    assert response.get_json()["measurement"]["ai_risk"] is None


def test_corrupt_model_does_not_block_rule_storage(tmp_path):
    from app import create_app

    dataset_paths = generate_dataset(tmp_path / "data", samples_per_class=5, seed=42)
    outputs = train_model(
        dataset_paths["dataset"],
        tmp_path / "models",
        tmp_path / "reports",
        seed=42,
    )
    outputs["model"].write_bytes(b"not a joblib artifact")
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": str(tmp_path / "measurements.sqlite3"),
            "AI_MODEL_PATH": str(outputs["model"]),
            "AI_MODEL_METADATA_PATH": str(outputs["model_metadata"]),
        }
    )

    response = app.test_client().post("/api/sensor", json=VALID_READING)

    assert response.status_code == 201
    assert response.get_json()["measurement"]["ai_status"] == "ERROR"
    assert response.get_json()["measurement"]["ai_risk"] is None


class DisagreeingModel:
    classes_ = ["NORMAL", "MONITOR", "HIGH", "CRITICAL"]

    def predict(self, rows):
        return ["NORMAL" for _ in rows]

    def predict_proba(self, rows):
        return [[1.0, 0.0, 0.0, 0.0] for _ in rows]


def test_disagreeing_ai_never_overrides_primary_rule(tmp_path):
    from app import create_app

    dataset_paths = generate_dataset(tmp_path / "data", samples_per_class=5, seed=42)
    outputs = train_model(
        dataset_paths["dataset"],
        tmp_path / "models",
        tmp_path / "reports",
        seed=42,
    )
    joblib.dump(DisagreeingModel(), outputs["model"])
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": str(tmp_path / "measurements.sqlite3"),
            "AI_MODEL_PATH": str(outputs["model"]),
            "AI_MODEL_METADATA_PATH": str(outputs["model_metadata"]),
        }
    )

    measurement = app.test_client().post("/api/sensor", json=VALID_READING).get_json()[
        "measurement"
    ]

    assert measurement["rule_risk"] == "HIGH"
    assert measurement["ai_risk"] == "NORMAL"
    assert measurement["analysis_source"] == "RULE"
