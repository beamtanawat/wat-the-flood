# WAT THE FLOOD

University prototype for receiving calibrated sensor readings over HTTP, calculating deterministic signal direction, applying prototype rule risk, storing measurements in SQLite, and showing results in a local dashboard.

The permanent device contract is `HTTP POST + JSON`. The mock ESP32 uses the same `/api/sensor` endpoint as future hardware. MQTT is not used.

## Setup

Requires Python 3.9+ for the currently verified local environment. The target development plan is Python 3.12; verify dependency availability on Raspberry Pi before deployment.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -r requirements-ai.txt
```

## Run backend

```bash
.venv/bin/python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

The dashboard displays `rule_risk` as the primary prototype result. Synthetic `ai_risk` appears separately when a compatible local model artifact exists. AI never overrides rule risk.

## Run simulator

Start the backend first, then send one deterministic sample:

```bash
.venv/bin/python -m simulator.mock_esp32 --scenario SOURCE_RIGHT --count 1 --deterministic
```

Continuous randomized NORMAL readings run once per second by default:

```bash
.venv/bin/python -m simulator.mock_esp32 --scenario NORMAL
```

Use `--url`, `--interval`, `--count`, `--seed`, and `--timeout` to change simulator behavior. Network failures report an error and send the next fresh sample; the simulator does not retry the same uncertain POST.

## Generate and train synthetic model

```bash
.venv/bin/python -m ai.generate_dataset --output-dir ai --samples-per-class 2500 --seed 42
.venv/bin/python -m ai.train --dataset ai/dataset.csv --model-dir ai/models --reports-dir ai/reports --seed 42
```

Synthetic labels reproduce prototype rules. Synthetic metrics are not evidence of real-world electrical safety performance. The backend validates model metadata before loading it.

## Tests

```bash
.venv/bin/python -m pytest -q
node --check static/js/dashboard.js
```

Runtime SQLite data is stored under `data/` and is ignored by Git. Back up SQLite with its backup facility before maintenance. Calibration conversion belongs before the HTTP boundary; the backend preserves received engineering units and does not apply calibration a second time.

## Raspberry Pi service

`deployment/wat-the-flood.service` is a readiness template for 64-bit Raspberry Pi OS. It expects `/opt/wat-the-flood`, a `wat-the-flood` service account, and `/var/lib/wat-the-flood` for SQLite data. Install matching dependencies in the virtual environment, review the local-network bind address, then enable the service with systemd. Raspberry Pi restart, reboot, backup/restore, and sustained one-reading-per-second checks remain unverified until Pi hardware is available.

This is not a certified safety device. Do not use prototype thresholds or simulator envelopes as real electrical safety limits.
