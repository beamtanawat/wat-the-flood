"""SQLite persistence for complete measurements."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Dict, Mapping, Optional, Tuple


SCHEMA_VERSION = 1
RISK_VALUES = ("NORMAL", "MONITOR", "HIGH", "CRITICAL")


def connect_database(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database_path), timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_database(database_path: Path) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect_database(path)
    try:
        current_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if current_version not in (0, SCHEMA_VERSION):
            raise RuntimeError(f"Unsupported database schema version: {current_version}")
        if current_version == 0:
            connection.executescript(
                """
                CREATE TABLE measurements (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    calibration_version TEXT NOT NULL,
                    water_level_cm REAL NOT NULL CHECK (water_level_cm >= 0),
                    conductivity_ms_cm REAL NOT NULL CHECK (conductivity_ms_cm >= 0),
                    north_rms_v REAL NOT NULL CHECK (north_rms_v >= 0),
                    east_rms_v REAL NOT NULL CHECK (east_rms_v >= 0),
                    south_rms_v REAL NOT NULL CHECK (south_rms_v >= 0),
                    west_rms_v REAL NOT NULL CHECK (west_rms_v >= 0),
                    vx_v REAL NOT NULL,
                    vy_v REAL NOT NULL,
                    gradient_v REAL NOT NULL CHECK (gradient_v >= 0),
                    direction TEXT CHECK (
                        direction IS NULL OR direction IN ('NORTH', 'EAST', 'SOUTH', 'WEST')
                    ),
                    direction_reason TEXT NOT NULL CHECK (
                        direction_reason IN ('LOW_SIGNAL', 'AMBIGUOUS', 'DOMINANT_AXIS')
                    ),
                    rule_risk TEXT NOT NULL CHECK (
                        rule_risk IN ('NORMAL', 'MONITOR', 'HIGH', 'CRITICAL')
                    ),
                    rule_version TEXT NOT NULL,
                    analysis_source TEXT NOT NULL CHECK (analysis_source IN ('RULE', 'AI')),
                    ai_risk TEXT CHECK (
                        ai_risk IS NULL OR ai_risk IN ('NORMAL', 'MONITOR', 'HIGH', 'CRITICAL')
                    ),
                    ai_confidence REAL CHECK (
                        ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 1)
                    ),
                    ai_status TEXT NOT NULL DEFAULT 'UNAVAILABLE' CHECK (
                        ai_status IN ('OK', 'UNAVAILABLE', 'INCOMPATIBLE', 'ERROR')
                    ),
                    model_version TEXT
                );
                CREATE INDEX idx_measurements_device_id_id
                    ON measurements (device_id, id);
                PRAGMA user_version = 1;
                """
            )
        connection.commit()
    finally:
        connection.close()


def insert_measurement(
    database_path: Path,
    measurement: Mapping[str, Any],
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    received_at = timestamp or _utc_timestamp()
    connection = connect_database(Path(database_path))
    try:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO measurements (
                    timestamp, device_id, calibration_version,
                    water_level_cm, conductivity_ms_cm,
                    north_rms_v, east_rms_v, south_rms_v, west_rms_v,
                    vx_v, vy_v, gradient_v, direction, direction_reason,
                    rule_risk, rule_version, analysis_source,
                    ai_risk, ai_confidence, ai_status, model_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    received_at,
                    measurement["device_id"],
                    measurement["calibration_version"],
                    measurement["water_level_cm"],
                    measurement["conductivity_ms_cm"],
                    measurement["north_rms_v"],
                    measurement["east_rms_v"],
                    measurement["south_rms_v"],
                    measurement["west_rms_v"],
                    measurement["vx_v"],
                    measurement["vy_v"],
                    measurement["gradient_v"],
                    measurement["direction"],
                    measurement["direction_reason"],
                    measurement["rule_risk"],
                    measurement["rule_version"],
                    measurement["analysis_source"],
                    measurement.get("ai_risk"),
                    measurement.get("ai_confidence"),
                    measurement.get("ai_status", "UNAVAILABLE"),
                    measurement.get("model_version"),
                ),
            )
            row = connection.execute(
                "SELECT * FROM measurements WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return dict(row)
    finally:
        connection.close()


def fetch_latest(database_path: Path) -> Optional[Dict[str, Any]]:
    connection = connect_database(Path(database_path))
    try:
        row = connection.execute(
            "SELECT * FROM measurements ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def fetch_history(
    database_path: Path,
    limit: int,
    before_id: Optional[int] = None,
) -> Tuple[list, Optional[int]]:
    connection = connect_database(Path(database_path))
    try:
        if before_id is None:
            rows = connection.execute(
                "SELECT * FROM measurements ORDER BY id DESC LIMIT ?", (limit + 1,)
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM measurements
                WHERE id < ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (before_id, limit + 1),
            ).fetchall()
        has_more = len(rows) > limit
        page = [dict(row) for row in rows[:limit]]
        next_before_id = page[-1]["id"] if has_more and page else None
        return page, next_before_id
    finally:
        connection.close()


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
