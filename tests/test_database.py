import sqlite3

from backend.database import initialize_database


def test_initialize_database_creates_versioned_measurements_schema(tmp_path):
    database_path = tmp_path / "measurements.sqlite3"

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(measurements)")
        }
        assert {
            "id",
            "timestamp",
            "device_id",
            "calibration_version",
            "water_level_cm",
            "conductivity_ms_cm",
            "north_rms_v",
            "east_rms_v",
            "south_rms_v",
            "west_rms_v",
            "vx_v",
            "vy_v",
            "gradient_v",
            "direction",
            "direction_reason",
            "rule_risk",
            "rule_version",
            "analysis_source",
            "ai_risk",
            "ai_confidence",
            "ai_status",
            "model_version",
        } <= columns


def test_initialize_database_is_idempotent(tmp_path):
    database_path = tmp_path / "measurements.sqlite3"

    initialize_database(database_path)
    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM measurements").fetchone()[0] == 0
