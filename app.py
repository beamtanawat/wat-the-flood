"""Flask application entrypoint."""

from datetime import datetime, timezone
import os
import sqlite3
from typing import Any, Mapping, Optional

from flask import Flask, current_app, jsonify, render_template, request
from werkzeug.exceptions import (
    BadRequest,
    HTTPException,
    RequestEntityTooLarge,
    UnsupportedMediaType,
)

from backend.analyzer import analyze_reading
from backend.ai_service import AIService
from backend.database import (
    fetch_history,
    fetch_latest,
    initialize_database,
    insert_measurement,
)
from backend.device_health import calculate_device_status, utc_timestamp
from backend.validation import ValidationError, validate_sensor_payload
from config import load_settings


def create_app(test_config: Optional[Mapping[str, Any]] = None) -> Flask:
    test_config = test_config or {}
    settings = load_settings(
        profile_path=test_config.get("PROFILE_PATH")
        or os.getenv("WAT_THE_FLOOD_PROFILE"),
        overrides=test_config,
    )
    app = Flask(__name__)
    app.config.from_mapping(
        TESTING=False,
        MAX_CONTENT_LENGTH=settings.max_body_bytes,
        SETTINGS=settings,
        DATABASE_PATH=str(settings.database_path),
    )
    if test_config:
        app.config.update(test_config)
    app.config.setdefault("CLOCK", lambda: datetime.now(timezone.utc))
    app.config["SETTINGS"] = settings
    app.config["DATABASE_PATH"] = str(settings.database_path)
    app.config["AI_SERVICE"] = AIService(settings)
    try:
        initialize_database(settings.database_path)
    except (OSError, RuntimeError, sqlite3.Error):
        app.config["STORAGE_READY"] = False
    else:
        app.config["STORAGE_READY"] = True

    @app.errorhandler(BadRequest)
    def handle_bad_request(error):
        del error
        return _error_response(
            "INVALID_JSON", "Request body must contain valid JSON", 400
        )

    @app.errorhandler(RequestEntityTooLarge)
    def handle_oversized_body(error):
        del error
        return _error_response(
            "PAYLOAD_TOO_LARGE",
            f"Request body must not exceed {app.config['MAX_CONTENT_LENGTH']} bytes",
            413,
        )

    @app.errorhandler(UnsupportedMediaType)
    def handle_unsupported_media_type(error):
        del error
        return _error_response(
            "UNSUPPORTED_MEDIA_TYPE",
            "Content-Type must be application/json",
            415,
        )

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return _error_response(error.code, error.message, 422, error.field)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        app.logger.exception("Unexpected application error", exc_info=error)
        return _error_response("INTERNAL_ERROR", "Internal server error", 500)

    @app.get("/api/health")
    def health():
        if not app.config["STORAGE_READY"]:
            return (
                jsonify(
                    {
                        "status": "degraded",
                        "prototype": True,
                        "database": "UNAVAILABLE",
                        "model": app.config["AI_SERVICE"].status,
                    }
                ),
                503,
            )
        return (
            jsonify(
                {
                    "status": "ok",
                    "prototype": True,
                    "database": "READY",
                    "model": app.config["AI_SERVICE"].status,
                }
            ),
            200,
        )

    @app.get("/")
    def dashboard():
        return render_template("index.html")

    @app.post("/api/sensor")
    def receive_sensor_reading():
        if request.mimetype != "application/json":
            raise UnsupportedMediaType()

        payload = request.get_json()
        normalized = validate_sensor_payload(payload, app.config["SETTINGS"])
        if not app.config["STORAGE_READY"]:
            return _error_response(
                "STORAGE_UNAVAILABLE", "Measurement storage is unavailable", 503
            )

        analysis = analyze_reading(app.config["SETTINGS"], normalized)
        ai_result = app.config["AI_SERVICE"].predict(normalized, analysis)
        measurement = {
            **normalized,
            **analysis,
            **ai_result,
        }
        try:
            saved = insert_measurement(
                app.config["SETTINGS"].database_path,
                measurement,
                timestamp=utc_timestamp(app.config["CLOCK"]()),
            )
        except (OSError, sqlite3.Error):
            app.config["STORAGE_READY"] = False
            return _error_response(
                "STORAGE_UNAVAILABLE", "Measurement storage is unavailable", 503
            )
        return jsonify({"measurement": saved}), 201

    @app.get("/api/latest")
    def latest():
        if not app.config["STORAGE_READY"]:
            return _error_response(
                "STORAGE_UNAVAILABLE", "Measurement storage is unavailable", 503
            )
        try:
            measurement = fetch_latest(app.config["SETTINGS"].database_path)
        except (OSError, sqlite3.Error):
            return _error_response(
                "STORAGE_UNAVAILABLE", "Measurement storage is unavailable", 503
            )
        return jsonify(
            {
                "measurement": measurement,
                "device": _device_summary(
                    app.config["SETTINGS"].device_id,
                    measurement,
                ),
            }
        )

    @app.get("/api/history")
    def history():
        try:
            limit = _query_integer("limit", default=100)
            before_id = _query_integer("before_id", default=None)
            if not 1 <= limit <= 1000:
                raise ValueError("limit must be between 1 and 1000")
            if before_id is not None and before_id < 1:
                raise ValueError("before_id must be a positive integer")
        except ValueError as error:
            return _error_response("INVALID_QUERY", str(error), 400)

        if not app.config["STORAGE_READY"]:
            return _error_response(
                "STORAGE_UNAVAILABLE", "Measurement storage is unavailable", 503
            )
        try:
            measurements, next_before_id = fetch_history(
                app.config["SETTINGS"].database_path,
                limit,
                before_id,
            )
        except (OSError, sqlite3.Error):
            return _error_response(
                "STORAGE_UNAVAILABLE", "Measurement storage is unavailable", 503
            )
        return jsonify(
            {
                "measurements": measurements,
                "next_before_id": next_before_id,
            }
        )

    @app.get("/api/status")
    def status():
        if not app.config["STORAGE_READY"]:
            return _error_response(
                "STORAGE_UNAVAILABLE", "Measurement storage is unavailable", 503
            )
        try:
            measurement = fetch_latest(app.config["SETTINGS"].database_path)
        except (OSError, sqlite3.Error):
            return _error_response(
                "STORAGE_UNAVAILABLE", "Measurement storage is unavailable", 503
            )
        return jsonify(
            {
                "device": _device_summary(
                    app.config["SETTINGS"].device_id,
                    measurement,
                )
            }
        )

    return app


def _error_response(code: str, message: str, status: int, field: str = ""):
    error = {"code": code, "message": message}
    if field:
        error["field"] = field
    return jsonify({"error": error}), status


def _query_integer(name: str, default: Optional[int]) -> Optional[int]:
    value = request.args.get(name)
    if value is None:
        return default
    if not value.isdigit():
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _device_summary(device_id: str, measurement: Optional[Mapping[str, Any]]):
    clock = current_app.config["CLOCK"]
    return calculate_device_status(
        device_id,
        measurement["timestamp"] if measurement else None,
        clock(),
        online_max_age_seconds=current_app.config["SETTINGS"].online_max_age_seconds,
        stale_max_age_seconds=current_app.config["SETTINGS"].stale_max_age_seconds,
    )


if __name__ == "__main__":
    create_app().run()
