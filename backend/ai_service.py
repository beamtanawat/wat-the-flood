"""Trusted local model loading and isolated AI comparison inference."""

import math
import json
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Dict, Mapping

from ai.generate_dataset import FEATURE_NAMES
from backend.analyzer import extract_features


LABELS = ("NORMAL", "MONITOR", "HIGH", "CRITICAL")


EXPECTED_UNITS = {
    "water_level_cm": "cm",
    "conductivity_ms_cm": "mS/cm",
    "north_rms_v": "V RMS",
    "east_rms_v": "V RMS",
    "south_rms_v": "V RMS",
    "west_rms_v": "V RMS",
    "vx_v": "V",
    "vy_v": "V",
    "gradient_v": "V",
}


class IncompatibleModel(Exception):
    """Model metadata does not match active runtime contract."""


class AIService:
    def __init__(self, settings: Any) -> None:
        self.status = "UNAVAILABLE"
        self.model_version = None
        self._model = None
        self._load(settings)

    def predict(
        self,
        payload: Mapping[str, float],
        analysis: Mapping[str, float],
    ) -> Dict[str, Any]:
        if self.status != "OK":
            return {
                "ai_risk": None,
                "ai_confidence": None,
                "ai_status": self.status,
                "model_version": None,
            }

        try:
            features = extract_features(payload, analysis)
            prediction = str(self._model.predict([features])[0])
            classes = [str(value) for value in self._model.classes_]
            probabilities = [float(value) for value in self._model.predict_proba([features])[0]]
            if prediction not in LABELS or prediction not in classes:
                raise ValueError("Model returned unsupported risk label")
            if len(classes) != len(probabilities):
                raise ValueError("Model probability output does not match classes")
            confidence = probabilities[classes.index(prediction)]
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("Model returned invalid confidence")
            return {
                "ai_risk": prediction,
                "ai_confidence": confidence,
                "ai_status": "OK",
                "model_version": self.model_version,
            }
        except Exception:
            self.status = "ERROR"
            return {
                "ai_risk": None,
                "ai_confidence": None,
                "ai_status": "ERROR",
                "model_version": None,
            }

    def _load(self, settings: Any) -> None:
        model_path = settings.ai_model_path
        metadata_path = settings.ai_metadata_path
        if not model_path.is_file() or not metadata_path.is_file():
            return
        try:
            import joblib

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self._validate_metadata(metadata, settings)
            model = joblib.load(model_path)
            if not hasattr(model, "predict") or not hasattr(model, "predict_proba"):
                raise ValueError("Model artifact lacks prediction methods")
            if not hasattr(model, "classes_"):
                raise ValueError("Model artifact lacks classes")
            if {str(value) for value in model.classes_} != set(LABELS):
                raise IncompatibleModel("Model classes do not match labels")
            self._model = model
            self.model_version = metadata["model_version"]
            self.status = "OK"
        except IncompatibleModel:
            self.status = "INCOMPATIBLE"
        except ModuleNotFoundError as error:
            if error.name in {"joblib", "numpy", "scipy", "sklearn"}:
                self.status = "UNAVAILABLE"
            else:
                self.status = "ERROR"
        except Exception:
            self.status = "ERROR"

    @staticmethod
    def _validate_metadata(metadata: Mapping[str, Any], settings: Any) -> None:
        if metadata.get("feature_names") != FEATURE_NAMES:
            raise IncompatibleModel("Feature order mismatch")
        if metadata.get("labels") != list(LABELS):
            raise IncompatibleModel("Label order mismatch")
        if metadata.get("units") != EXPECTED_UNITS:
            raise IncompatibleModel("Unit metadata mismatch")
        if metadata.get("rule_version") != settings.rule_version:
            raise IncompatibleModel("Rule version mismatch")
        if metadata.get("calibration_version") != settings.calibration_version:
            raise IncompatibleModel("Calibration version mismatch")
        if metadata.get("mode") != settings.mode:
            raise IncompatibleModel("Configuration mode mismatch")
        dependencies = metadata.get("dependency_versions", {})
        if dependencies.get("scikit-learn") != _package_version("scikit-learn"):
            raise IncompatibleModel("scikit-learn version mismatch")
        if dependencies.get("joblib") != _package_version("joblib"):
            raise IncompatibleModel("joblib version mismatch")
        if not metadata.get("model_version"):
            raise IncompatibleModel("Model version is required")


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"
