# WAT THE FLOOD — Implementation Plan

Finalized: 2026-10-03 (Asia/Bangkok).

This document plans implementation only. Creating it does not authorize starting application development. No application code, dataset, or model is created by this planning task.

## 1. Project Goal

Build a university prototype that receives sensor measurements over HTTP, calculates directional signal differences, classifies anomalies, stores readings, and presents current and historical results.

Develop with a Mock ESP32 on Mac. Later replace the simulator with physical hardware connected to a Raspberry Pi while preserving the HTTP contract and application architecture.

Confirmed constraints:

- MQTT must not be used anywhere in this project.
- The permanent device transport is ESP32 → HTTP POST JSON → Raspberry Pi / Flask.
- Use SQLite and a dashboard built with HTML, CSS, and vanilla JavaScript.
- Directional readings represent calibrated RMS volts, with explicit units in API field names.
- Direction analysis is deterministic and separate from AI.
- The displayed primary risk is `rule_risk`, produced by prototype rules.
- A synthetic-trained Random Forest produces a separate `ai_risk` for comparison. It never overrides `rule_risk`.
- Synthetic results are development evidence only, not real electrical safety validation.

## 2. Current Repository State

Initial inspection and the pre-write recheck found an initialized Git repository on `main`, with no commits and no project files outside Git metadata. There is no existing application, documentation, dependency setup, test suite, or reusable component to preserve. No architectural conflicts were found.

`PLAN.md` is the first project document. Before future implementation, reinspect the repository and preserve any work added since this plan.

## 3. Final Architecture

```text
Mock ESP32 / Future ESP32
          |
     HTTP POST JSON
     calibrated units
          |
    Flask validation
          |
  Deterministic direction
          |
  Prototype rule risk
          |
  Optional AI comparison
          |
    SQLite transaction
          |
   JSON response / REST API
          |
 HTML/CSS/JavaScript dashboard
```

Serve the dashboard and API from one Flask application. Keep validation, analysis, persistence, and model loading separate. Share pure feature-extraction and analysis functions between training and runtime inference.

Selected stack:

- Python 3.12 as the initial development target, subject to verification on the target Pi.
- Flask and Python's built-in `sqlite3`.
- HTML, CSS, and vanilla JavaScript with native SVG charts.
- Python standard-library HTTP client for the simulator.
- pandas, scikit-learn, joblib, and matplotlib for offline ML work.
- pytest for tests.
- Waitress for Raspberry Pi deployment.

Use a virtual environment and pin tested dependency versions during implementation. Do not introduce an ORM, frontend framework, broker, task queue, or container requirement. Flask's development server is for development; use a deployment server on the Pi. See [Flask deployment documentation](https://flask.palletsprojects.com/en/stable/deploying/waitress/).

## 4. File Structure

```text
wat-the-flood/
├── PLAN.md
├── README.md
├── .gitignore
├── app.py
├── config.py
├── requirements.txt
├── requirements-ai.txt
├── requirements-dev.txt
├── backend/
│   ├── __init__.py
│   ├── validation.py
│   ├── analyzer.py
│   ├── database.py
│   ├── ai_service.py
│   └── device_health.py
├── simulator/
│   ├── __init__.py
│   └── mock_esp32.py
├── ai/
│   ├── __init__.py
│   ├── generate_dataset.py
│   ├── train.py
│   ├── evaluate.py
│   ├── dataset.csv                 # Generated later; ignored by Git
│   ├── models/                     # Generated later; ignored by Git
│   └── reports/                    # Generated later; ignored by Git
├── configuration/
│   └── prototype.json
├── templates/
│   └── index.html
├── static/
│   ├── css/dashboard.css
│   └── js/dashboard.js
├── tests/
│   ├── conftest.py
│   ├── test_validation.py
│   ├── test_analyzer.py
│   ├── test_database.py
│   ├── test_api.py
│   ├── test_simulator.py
│   ├── test_ai_pipeline.py
│   ├── test_device_health.py
│   └── test_configuration.py
├── data/                          # Runtime SQLite database; ignored
└── deployment/
    └── wat-the-flood.service
```

Responsibilities:

- `app.py`: application factory, routes, and request orchestration.
- `config.py`: environment settings, paths, configuration validation, and active profile metadata.
- `validation.py`: sensor payload and query validation.
- `analyzer.py`: direction calculations, prototype rules, and shared ML feature extraction.
- `database.py`: schema initialization, transactions, and bounded queries.
- `ai_service.py`: trusted model loading, compatibility checks, and prediction.
- `device_health.py`: timestamp-based connectivity status.

Calibration conversion belongs before the HTTP boundary: the simulator emits engineering-unit fixtures, and the future ESP32 acquisition adapter converts hardware measurements to the same units. The backend must not apply the same calibration a second time. A later hardware design may relocate that adapter only through an explicit design review that preserves the public engineering-unit contract.

## 5. Data Contract

### Request

`POST /api/sensor`, with `Content-Type: application/json`:

```json
{
  "water_level_cm": 14.2,
  "conductivity_ms_cm": 1.7,
  "north_rms_v": 0.12,
  "east_rms_v": 0.91,
  "south_rms_v": 0.10,
  "west_rms_v": 0.13
}
```

These six numeric fields are required. `conductivity_ms_cm` denotes mS/cm (millisiemens per centimeter). Directional fields are nonnegative calibrated RMS voltage magnitudes, not signed instantaneous voltage or ADC counts.

Optional metadata:

- `device_id`: defaults to `esp32-01`; V1 accepts only the configured device ID.
- `calibration_version`: defaults to `demo-identity-v1` in simulator mode. Hardware mode requires an explicit version matching the configured active profile.

Do not accept the earlier ambiguous names `north`, `east`, `south`, `west`, `water_level`, or `conductivity` as aliases. No existing client requires backwards compatibility.

The server assigns an ISO 8601 UTC receipt timestamp. It means received time, not verified measurement capture time. Device clocks are not required in V1.

### Validation

Reject malformed JSON, arrays, non-object bodies, missing or unknown fields, numeric strings, booleans, nulls, NaN, infinity, negative readings, invalid metadata, and bodies larger than 4 KiB. Reject a device ID or calibration version inconsistent with the active configuration.

Use these configurable **simulator-only input envelopes** initially:

| Input | Demo envelope |
|---|---|
| Water level | 0–100 cm |
| Conductivity | 0–10 mS/cm |
| Each directional voltage | 0–2 V RMS |

These are software fixture bounds, not hardware specifications, usable voltage ranges, detection limits, or electrical safety limits. Hardware mode must not inherit them without explicit hardware validation.

Invalid requests never insert a measurement or refresh device status.

### Measurement representation

All measurement endpoints use the same object:

- `id`, `timestamp`, `device_id`, `calibration_version`.
- The six received engineering-unit fields, unchanged.
- `vx_v`, `vy_v`, `gradient_v`, `direction`, `direction_reason`.
- `rule_risk`, `rule_version`, `analysis_source`.
- Nullable `ai_risk`, `ai_confidence`, and `model_version`, plus `ai_status`.

`analysis_source` is `RULE` for the primary result throughout this plan. AI comparison does not change it. Do not introduce an ambiguous combined `risk` field.

`ai_confidence` is the classifier probability assigned to the predicted class, between 0 and 1. It is an uncalibrated model score, not a probability that an area is safe or hazardous.

## 6. Database Schema

Use one `measurements` table initially:

| Fields | SQLite type and constraints |
|---|---|
| `id` | `INTEGER PRIMARY KEY` |
| `timestamp` | UTC timestamp, `TEXT NOT NULL` |
| `device_id`, `calibration_version` | `TEXT NOT NULL` |
| Six unit-qualified input fields | `REAL NOT NULL`, nonnegative |
| `vx_v`, `vy_v`, `gradient_v` | `REAL NOT NULL`; gradient nonnegative |
| `direction` | Nullable cardinal-direction `TEXT` |
| `direction_reason` | `LOW_SIGNAL`, `AMBIGUOUS`, or `DOMINANT_AXIS` |
| `rule_risk` | Checked `NORMAL`/`MONITOR`/`HIGH`/`CRITICAL` enum, not null |
| `rule_version` | `TEXT NOT NULL` |
| `analysis_source` | Checked `RULE`/`AI` enum; this implementation writes `RULE` |
| `ai_risk` | Nullable checked risk enum |
| `ai_confidence` | Nullable `REAL`, between 0 and 1 |
| `ai_status` | `OK`, `UNAVAILABLE`, `INCOMPATIBLE`, or `ERROR` |
| `model_version` | Nullable `TEXT` |

When AI status is not `OK`, `ai_risk` and `ai_confidence` are null. Record model version when it is available from a validated artifact; otherwise leave it null.

Add an index on `(device_id, id)` and use `PRAGMA user_version` for schema versioning. Open and close a connection per request, use parameterized queries, and set a five-second busy timeout.

Commit one complete measurement atomically. Return success only after commit. Database unavailability returns structured `503`; it must never produce a successful write response. Order recent readings by `id` so clock adjustments do not reorder arrivals.

Do not automatically delete history in V1. Document backups and disk-space maintenance. Raw ADC samples and waveforms are outside the V1 table; experimental acquisition may record them separately during hardware validation.

## 7. Analysis Design

### Deterministic direction

Use the received calibrated RMS values:

```text
vx_v = east_rms_v - west_rms_v
vy_v = north_rms_v - south_rms_v
gradient_v = sqrt(vx_v² + vy_v²)
```

`gradient_v` is the magnitude of directional voltage differences, in volts. It is not a physical electric field in V/m because electrode distances and measurement geometry are not represented. It does not establish source location.

Simulator direction rules:

1. If `gradient_v < 0.01 V`, return null direction and `LOW_SIGNAL`.
2. Otherwise, if `abs(abs(vx_v) - abs(vy_v)) <= 0.01 V`, return null direction and `AMBIGUOUS`.
3. Otherwise select the larger absolute axis: positive/negative `vx_v` means EAST/WEST; positive/negative `vy_v` means NORTH/SOUTH.
4. Cardinal results use `DOMINANT_AXIS`.

The 0.01 V tolerance is a configurable demo parameter, not a measured hardware detection limit. Diagonal direction labels are deferred.

### Prototype rule risk

Define `E` as the maximum directional RMS voltage, `W` as water level in cm, and `C` as conductivity in mS/cm. Evaluate the following in descending severity order:

| `rule_risk` | Demo condition |
|---|---|
| `CRITICAL` | `E >= 1.0`, or `E >= 0.5` and `W >= 20` and `C >= 2.0` |
| `HIGH` | `E >= 0.5`, or `E >= 0.2` and (`W >= 20` or `C >= 2.0`) |
| `MONITOR` | `E >= 0.2`, or `W >= 20`, or `C >= 2.0` |
| `NORMAL` | Otherwise |

These are arbitrary software-development thresholds, not real electrical safety thresholds. Keep them in configuration and record a rule version. Use absolute electrical magnitude so equal elevated readings do not appear normal merely because directional differences cancel.

## 8. AI Design

### Role and features

Use a Random Forest Classifier to classify multi-sensor patterns into the same four prototype classes. Show its result separately from the primary rule result.

Use this exact feature order:

```text
water_level_cm, conductivity_ms_cm,
north_rms_v, east_rms_v, south_rms_v, west_rms_v,
vx_v, vy_v, gradient_v
```

Share feature extraction between training and inference. Defer gradient, water-level, and conductivity change-rate features until reliable timestamped experimental sequences exist.

### Synthetic dataset

Generate 10,000 reproducible rows with seed 42, balanced at 2,500 rows per class. Include directional imbalance, uniform elevated voltage, high water/conductivity independently and jointly, threshold boundaries, tied directions, and low signals.

Generate finite values within the demo envelopes and derive features and labels using the shared analyzer. Use deterministic generation with bounded attempts; fail explicitly if a class quota cannot be filled.

CSV fields include the nine features, label, scenario name, and sample identifier. Exclude scenario names and identifiers from model inputs. Export generation metadata including seed, units, rule version, calibration profile, and generator version.

Synthetic labels reproduce prototype rules. This demonstrates multi-sensor classification and rule approximation, not independent hazard discovery. Real experimental labels and retraining are required before any claim of real-world applicability.

### Training and evaluation

- Stratified 80/20 train/test split, seed 42.
- Random Forest: 200 trees, `max_depth=12`, `min_samples_leaf=2`, `random_state=42`, `n_jobs=1`.
- Report accuracy, macro F1, per-class precision/recall/F1, confusion matrix, class counts, and feature importance.
- Keep test data out of training and tuning; check for exact duplicate feature rows crossing the split.
- Export metrics as JSON and the confusion matrix as an image.
- When experimental sequences arrive, split by experiment/session instead of adjacent individual readings.

Pipeline acceptance is reproducibility, valid outputs, complete evaluation, and artifact compatibility. No synthetic accuracy threshold constitutes electrical safety acceptance.

### Model deployment

Export `model.joblib` plus metadata containing model version, feature order, labels, units, rule/calibration versions, seed, and dependency versions. Load once at startup, using only trusted locally generated artifacts. joblib-based loading can execute code, and cross-version model loading is unsupported; match training and serving dependencies. See [scikit-learn model persistence](https://scikit-learn.org/stable/model_persistence.html).

For each valid reading, obtain `ai_risk` and the predicted-class `predict_proba` value as `ai_confidence`. Validate the label, finite score, and score range.

Failure behavior:

- Missing model: `UNAVAILABLE`.
- Incompatible feature/unit/rule/calibration/dependency metadata: `INCOMPATIBLE`.
- Corrupt artifact, prediction exception, or invalid output: `ERROR`.
- Any failure leaves AI risk/confidence null while rules and storage continue.

Integrate inference into sensor ingestion. A separate public prediction endpoint is unnecessary for V1. Restart the service to activate a newly validated artifact; do not add hot reload.

## 9. API Design

| Endpoint | Purpose |
|---|---|
| `GET /` | Serve dashboard |
| `GET /api/health` | Application, database, and model status; prototype marker |
| `POST /api/sensor` | Validate, analyze, persist, then return `201` with `{"measurement": ...}` |
| `GET /api/latest` | Latest measurement and current device status |
| `GET /api/history` | Bounded measurement history |
| `GET /api/status` | Device status, last receipt time, and reading age |

Before the first reading, latest returns HTTP 200:

```json
{
  "measurement": null,
  "device": {
    "device_id": "esp32-01",
    "status": "OFFLINE",
    "last_received_at": null,
    "age_seconds": null
  }
}
```

After ingestion, `measurement` contains the shared measurement representation. Status is computed when requested, not stored as a permanent property of a historical reading.

History parameters: `limit` defaults to 100, allowed 1–1000; optional `before_id` is a positive integer. Return `{"measurements": [...], "next_before_id": ...}` newest first. The cursor is the last returned ID only if an older page exists; otherwise null. The browser reverses data for chronological plotting. Empty history returns an empty array and null cursor.

Errors use a consistent object:

```json
{
  "error": {
    "code": "INVALID_READING",
    "message": "north_rms_v must be a finite nonnegative number",
    "field": "north_rms_v"
  }
}
```

Use `400` for malformed JSON/queries, `413` for oversized bodies, `415` for unsupported content type, `422` for invalid readings/metadata, `503` for unavailable storage, and `500` for unexpected internal failure without a traceback in the response. Omit `field` when no specific field applies.

Missing AI does not fail health when rules and storage work. Database failure makes health return `503`. Do not expose secrets or host filesystem paths in health output.

## 10. Dashboard Design

Use one responsive page, ordered by importance:

1. Project title and persistent prototype notice.
2. Device status, last update, and reading age.
3. Primary `rule_risk` with explanatory text and a "Prototype rule risk" label.
4. Direction and directional difference magnitude.
5. Water level, conductivity, and directional RMS voltages with explicit units.
6. Separate "Synthetic AI comparison" card: `ai_risk`, model score, model version, and model status.
7. Recent readings, charts, rule/AI risk history, and anomaly entries.

Copy and state requirements:

- NORMAL: "No electrical anomaly detected at monitored point", qualified by the persistent prototype notice.
- MONITOR: "Elevated demo reading — inspect sensor measurements."
- HIGH/CRITICAL: "Electrical anomaly detected."
- CRITICAL additionally: "Do not approach the monitored area."
- Null direction: "No clear direction", with its reason.
- Empty data: "Waiting for sensor readings."
- STALE/OFFLINE: "Current conditions unknown — last received reading shown."
- AI score: "Model score; not a validated safety probability."

Never use "SAFE" as a system assessment. Do not blend AI and rule risk into a single result or allow AI confidence to suppress a rule warning.

Poll latest approximately every second, scheduling after the previous request completes, with a five-second timeout. Fetch failures show a backend-connection warning; do not invent new risk or current device status from failed requests.

Poll history every five seconds. Use native SVG charts, separated by unit, and labeled risk entries. Derive recent anomaly entries from HIGH/CRITICAL rule measurements; no separate event subsystem is required. Label the list as recent readings rather than continuous incident tracking.

Keep historical browsing separate from live refresh so an older-page view is not unexpectedly replaced. Provide a return-to-latest control. Use text alongside colors, accessible contrast, keyboard controls, and local assets without CDN dependencies.

## 11. Implementation Phases

Each phase adds tests for its own behavior. Phase 12 consolidates system verification; it does not postpone all testing.

### Phase 0 — Repository inspection

- **Objective:** Preserve work and establish project constraints.
- **Files:** `PLAN.md`.
- **Tasks:** Inspect files/Git state, record findings, and confirm architecture and contract decisions.
- **Expected result:** An internally consistent implementation plan.
- **Acceptance:** Every required section/phase is present; no application implementation occurs.
- **Dependencies:** None. Inspection is complete for this planning task.

### Phase 1 — Core backend

- **Objective:** Establish Flask, configuration, validation, and error conventions.
- **Files:** `app.py`, `config.py`, dependency files, `.gitignore`, `backend/__init__.py`, `backend/validation.py`, `configuration/prototype.json`, validation/API tests.
- **Tasks:** Create application factory, health endpoint, unit-qualified validator, metadata checks, body limit, and JSON errors.
- **Expected result:** Backend starts and validates requests.
- **Acceptance:** Invalid requests return documented errors. Valid ingestion returns `503 STORAGE_NOT_READY` until Phase 4; do not introduce temporary successful ingestion without storage.
- **Dependencies:** Phase 0.

### Phase 2 — Mock ESP32

- **Objective:** Exercise the permanent HTTP contract before hardware exists.
- **Files:** Simulator package, simulator tests, `README.md`.
- **Tasks:** Add NORMAL, SOURCE_LEFT, SOURCE_RIGHT, SOURCE_NORTH, SOURCE_SOUTH, HIGH_CONDUCTIVITY, HIGH_WATER, and CRITICAL scenarios; configurable URL, interval, count, and seed; continuous randomized generation.
- **Expected result:** Valid JSON is sent every second by default; interruption exits cleanly.
- **Acceptance:** LEFT maps to WEST and RIGHT to EAST. HTTP failures are reported without crashing. Do not retry the same uncertain POST automatically; send the next fresh sample on the next interval.
- **Dependencies:** Phase 1. Successful end-to-end ingestion begins in Phase 4.

Demo defaults: normal water 5 cm, conductivity 0.5 mS/cm, and all channels 0.05 V RMS. Directional scenarios raise the selected channel to 0.8 V RMS. HIGH_WATER uses 30 cm; HIGH_CONDUCTIVITY uses 3 mS/cm. CRITICAL raises one channel to 1.2 V RMS. All use `demo-identity-v1` metadata. Randomization stays within demo envelopes; deterministic mode preserves exact acceptance fixtures.

### Phase 3 — Analysis engine

- **Objective:** Implement deterministic direction and prototype rules.
- **Files:** `backend/analyzer.py`, configuration, analyzer tests.
- **Tasks:** Implement shared feature extraction, axis differences, ambiguity handling, ordered rules, and rule versioning.
- **Expected result:** Pure functions return predictable analysis outputs.
- **Acceptance:** Cover cardinal directions, equal-axis ties, low signals, exact boundaries, and equal elevated readings. AI is not involved in direction.
- **Dependencies:** Phase 1.

### Phase 4 — SQLite

- **Objective:** Complete durable end-to-end ingestion.
- **Files:** `backend/database.py`, `app.py`, database/API tests.
- **Tasks:** Initialize versioned schema; connect validation, rules, transactions, latest, and history. Store AI fields as null/UNAVAILABLE until integration.
- **Expected result:** Successful POSTs return durable complete measurements.
- **Acceptance:** Data survives restart; invalid requests insert nothing; storage failure never returns `201`; history ordering, limits, and cursor behavior pass.
- **Dependencies:** Phases 1 and 3; use Phase 2 for smoke testing.

### Phase 5 — Dashboard V1

- **Objective:** Show current readings and primary rule risk clearly.
- **Files:** Dashboard template/CSS/JavaScript, `README.md`.
- **Tasks:** Add units, direction, risk, prototype notice, empty/error states, and polling.
- **Expected result:** Simulator readings update without a page reload.
- **Acceptance:** Check normal/critical scenarios, no data, disconnected backend, narrow screens, and absence of misleading safety assurances. Display receipt time/age even before Phase 10 adds status classification.
- **Dependencies:** Phase 4.

### Phase 6 — Dashboard history

- **Objective:** Provide bounded historical inspection.
- **Files:** Dashboard files and history API tests.
- **Tasks:** Add table, SVG plots, risk history, recent anomalies, and older-page navigation.
- **Expected result:** Users inspect stored trends without loading all history.
- **Acceptance:** Verify zero/one/many readings, chronological plots, pagination, and stable older-page browsing during live updates.
- **Dependencies:** Phase 5.

### Phase 7 — Synthetic dataset

- **Objective:** Create reproducible ML development data.
- **Files:** `ai/__init__.py`, `ai/generate_dataset.py`, AI requirements, AI pipeline tests.
- **Tasks:** Generate balanced samples, boundary cases, derived features, CSV, and metadata.
- **Expected result:** A reproducible dataset using the same units and features as runtime.
- **Acceptance:** Same seed produces identical output; class quotas and valid envelopes hold; labels/features match the shared analyzer.
- **Dependencies:** Phase 3.

### Phase 8 — AI training pipeline

- **Objective:** Train and evaluate the Random Forest.
- **Files:** `ai/train.py`, `ai/evaluate.py`, AI tests, generated models/reports.
- **Tasks:** Split data, train the specified classifier, report metrics/importance, and export artifact/metadata.
- **Expected result:** Reproducible model and evaluation outputs.
- **Acceptance:** No identifier leakage or exact duplicate feature rows across train/test; all classes appear in reports; export/reload preserves predictions and predicted-class scores.
- **Dependencies:** Phase 7.

### Phase 9 — AI integration

- **Objective:** Add a separate AI comparison without changing rule behavior.
- **Files:** `backend/ai_service.py`, application orchestration, dashboard, AI/API tests.
- **Tasks:** Load trusted compatible artifact once; persist `ai_risk`, `ai_confidence`, model version, and status; show separate comparison card/history.
- **Expected result:** Rule and AI classifications appear side by side.
- **Acceptance:** Missing/corrupt/incompatible/failing models do not prevent rule analysis/storage. A deliberately disagreeing AI prediction cannot change `rule_risk`, primary UI warning, or `analysis_source`.
- **Dependencies:** Phases 4, 5, and 8.

### Phase 10 — Device health

- **Objective:** Distinguish current, delayed, and absent readings.
- **Files:** `backend/device_health.py`, status routes, dashboard, device-health tests.
- **Tasks:** Calculate age from the last successfully persisted receipt; classify ONLINE at age <=5 s, STALE at >5–30 s, OFFLINE at >30 s or before any reading.
- **Expected result:** Status changes without device heartbeat messages.
- **Acceptance:** Test exact boundaries with an injected clock, backend restart, rejected requests, and stale display handling. Clamp negative age from server clock adjustment to zero and document reliance on the server clock.
- **Dependencies:** Phases 4 and 5.

### Phase 11 — Calibration/configuration preparation

- **Objective:** Prepare explicit configuration and provenance for future calibrated sensors.
- **Files:** `config.py`, `configuration/prototype.json`, configuration tests, `README.md`.
- **Tasks:** Separate simulator profile, rule thresholds, direction tolerance, receipt intervals, and calibration identifiers from source code. Validate startup configuration; document the pre-HTTP calibration boundary.
- **Expected result:** Simulator identity profile is reproducible; hardware profiles cannot silently reuse unvalidated assumptions.
- **Acceptance:** Invalid/nonfinite/contradictory settings fail startup. Hardware mode requires a validated profile and matching request metadata. Model/profile mismatch disables AI comparison. No double calibration occurs.
- **Dependencies:** Phases 4 and 9. Actual hardware calibration remains part of Phase 14.

### Phase 12 — Testing

- **Objective:** Verify complete system behavior across components.
- **Files:** Test suite and documented browser/smoke procedures.
- **Tasks:** Exercise simulator-to-database flow, restart recovery, API failures, model failures, and dashboard states.
- **Expected result:** Repeatable unit/integration tests and manual browser checks.
- **Acceptance:** `python -m pytest` passes; all scenarios have expected rule results; no false-success write, stale-current presentation, or AI override remains.
- **Dependencies:** Phases 1–11.

### Phase 13 — Raspberry Pi readiness

- **Objective:** Deploy the same application with minimal platform changes.
- **Files:** Deployment service, dependency files, configuration, `README.md`.
- **Tasks:** Verify 64-bit Raspberry Pi OS, matching Python/dependencies, writable data path, Waitress, service restart, and backup procedure.
- **Expected result:** Pi serves API/dashboard on a trusted local network.
- **Acceptance:** Mac simulator posts to Pi; readings survive restart/reboot; AI loads or its unavailability is visible; sustained one-reading-per-second operation has no growing backlog.
- **Dependencies:** Phase 12 and Pi availability for device-specific acceptance.

### Phase 14 — Real ESP32 integration

- **Objective:** Replace simulated input with calibrated physical measurements.
- **Files:** Hardware integration documentation, contract fixtures, configuration; ESP32 acquisition/firmware files are specified after hardware selection.
- **Tasks:** Resolve hardware TBDs; validate sensors against reference measurements; implement pre-HTTP conversion to the specified units; send unchanged unit-qualified JSON; record calibration version.
- **Expected result:** Real ESP32 readings use the existing backend path.
- **Acceptance:** Captured requests pass contract tests; unplug/reconnect updates status correctly; controlled measurements meet experimentally established tolerances; clipping, invalid measurements, and below-detection-limit behavior have an explicit reviewed representation before live integration.
- **Dependencies:** Phase 13, hardware availability, and resolution of all acquisition TBDs. No source-location or safety claim is accepted on simulator evidence alone.

LED/buzzer wiring and control remain hardware-stage work. A remote actuator-control API is not part of V1.

## 12. Testing Strategy

Use Flask test clients, temporary SQLite databases, seeded data, and injected clocks. Include:

- Missing/extra fields, ambiguous legacy field names, numeric types, finite values, boundaries, malformed/oversized requests, and calibration metadata.
- Direction signs, equal-axis ambiguity, deadband, and uniform elevated readings.
- Every rule branch and exact threshold.
- Transaction rollback, restart persistence, unavailable storage, history ordering, and cursor limits.
- Simulator mappings, seeded random behavior, timeouts, and non-success HTTP responses.
- Shared training/runtime feature names, order, units, and values.
- Model reload, confidence association with predicted class, incompatible metadata, corrupt artifacts, and prediction errors.
- Deliberate AI/rule disagreement proving that AI never overrides primary risk.
- Device-status boundaries, invalid requests, no initial data, and stale displays.
- Profile validation and provenance without double calibration.

Manual browser checks cover readability, responsiveness, polling, plots, separate AI comparison, and disconnected states. Do not add an automated browser framework initially.

## 13. Hardware Integration Strategy

The permanent API receives calibrated physical units. The simulator emits matching fixtures; the ESP32 acquisition adapter later converts actual sensor measurements into those units before transmission.

Hardware-specific items remain **TBD until hardware integration**:

- RMS sampling window, sample rate, filtering, and channel timing.
- Analog front-end topology, isolation, protection, reference convention, and electrode geometry.
- Electrode offsets, sensor baselines, conductivity calibration, water-level calibration, and RMS conversion procedure.
- Usable voltage range, saturation/clipping behavior, accuracy, noise floor, and detection limits.
- Reference instruments, experimental tolerances, and the representation of invalid or below-limit measurements.

The earlier provisional sampling-window proposal is not adopted. Demo envelopes and direction tolerance are not substitutes for these hardware decisions.

Hardware mode is gated on resolving and documenting these items. If invalid/clipped readings require quality metadata, specify and review an additive contract extension before enabling real ingestion; never silently encode a sensor fault as zero.

The ESP32 sends approximately once per second and handles Wi-Fi/server failures without labeling buffered data as fresh. V1 has no offline replay, duplicate suppression, or device capture timestamps. Each accepted request represents a new arrival. Future buffering requires explicit message IDs and capture timestamps.

Retrain with labeled experimental data before interpreting AI output beyond prototype comparison. Confirm electrode orientation; directional RMS differences do not themselves establish the direction of an electric field or the location of a source.

## 14. Raspberry Pi Deployment Strategy

- Use 64-bit Raspberry Pi OS and a virtual environment; confirm the selected Python/package versions on actual hardware.
- Run one application process with Waitress on configurable port 8000.
- Serve assets locally and configure database/model/configuration paths through environment settings.
- Use an unprivileged service account and systemd startup/restart behavior.
- Back up SQLite using its backup facility; document restore checks and disk-space monitoring.
- Train on Mac initially, then deploy a trusted artifact with matching dependency metadata.
- Keep V1 on a trusted local network. Internet exposure requires a separate authentication and transport-security design.
- Verify simulator ingestion, browser polling, restart/reboot persistence, and model compatibility on the Pi.

Hardware performance is unverified until these checks run. No architectural redesign is expected, but package availability and resource consumption must be measured rather than assumed.

## 15. Safety / Limitations

This is a university prototype, not a certified safety device. No output guarantees that floodwater is safe.

- Results concern the monitored point and available measurements only.
- Rule thresholds, simulator envelopes, and direction tolerance are software-development defaults, not validated electrical safety thresholds or hardware detection limits.
- Synthetic AI accuracy measures approximation of synthetic labels, not real-world hazard detection.
- AI confidence is not a calibrated real-world safety probability.
- Stale or missing readings mean current conditions are unknown.
- Real application requires hardware characterization, experimental calibration, representative labeled data, and validation.
- Real electrical testing must not use dangerous mains voltage. Use supervised, isolated, current-limited low-voltage test equipment.
- Direction output indicates measured signal imbalance, not proven source location.

## 16. Definition of Done

### Planning task

- [x] Inspect the repository and identify existing/reusable work.
- [x] Confirm explicit-unit RMS contract and rule-primary/AI-comparison behavior.
- [x] Specify architecture, schema, APIs, dashboard, testing, and all 15 phases.
- [x] Keep hardware-specific acquisition and calibration details explicitly TBD.
- [x] Review consistency across payloads, features, storage, UI labels, and failure behavior.
- [x] Save this finalized plan as root-level `PLAN.md`.
- Stop after verifying this document. Do not implement the application in this task.

### Future software implementation

- [ ] All simulator scenarios operate through HTTP JSON using unit-qualified fields.
- [ ] Invalid requests fail predictably without inserting data or refreshing health.
- [ ] Deterministic direction and prototype rules pass boundary tests.
- [ ] Readings persist across restart and history queries remain bounded.
- [ ] Dashboard presents current readings, direction, rule risk, history, and connectivity clearly.
- [ ] Synthetic generation, training, evaluation, and model export are reproducible.
- [ ] Both rule/AI risks and relevant confidence/version metadata are stored.
- [ ] AI failures are visible and never alter the primary rule result.
- [ ] Calibration provenance is explicit and no double calibration occurs.
- [ ] Unit/integration tests and manual dashboard checks pass.
- [ ] Pi deployment, backup/restore, and recovery checks pass when hardware is available.
- [ ] Prototype and synthetic-data limitations are visible in documentation and UI.

Real ESP32 integration is a separate hardware-dependent gate. The simulated software pipeline can be completed and demonstrated before it, without claiming real-world safety validation.
