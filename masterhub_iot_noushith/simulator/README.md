# MasterHub Emotiv Cortex Simulator — Phase 1

Replays a recorded Emotiv Cortex prediction file into MasterHub over the
existing HTTP API, so the rest of the system (Router, FSM, domain
handlers) can be exercised exactly as it will be once a real headset is
attached in Phase 2.

**This does not modify MasterHub.** It is a standalone client that
talks to `POST /api/command`, the same way the dashboard or `tests/`
scripts already do. `core/`, `services/`, `actions/`, `api/`,
`mappings/*.json` are untouched.

## Architecture

```
emotiv_bci_predictions.json
        │
        ▼
Prediction Reader     (prediction_reader.py)   — load + read sequentially, no processing
        │
        ▼
Confidence Filter     (confidence_filter.py)   — drop predictions below threshold
        │
        ▼
Gesture Stabilizer    (stabilizer.py)          — drop repeats of a held gesture
        │
        ▼
API Sender            (sender.py)              — HTTP POST, never a direct function call
        │
        ▼
POST /api/command
        │
        ▼
MasterHub (core/input_processor.py → gesture_map.json → core/engine.py → router → domain handlers)
```

## Important: endpoint name

The task spec referenced `POST /api/send_command`. MasterHub's actual
route (see `api/routes.py`) is **`POST /api/command`**, and no new
route was added — the simulator uses the endpoint that already exists,
per the "don't create a new endpoint" requirement. If a
`/api/send_command` route is added later, only `simulator/config.py`
(`COMMAND_ENDPOINT`) needs to change.

## What gets sent

`emotiv_bci_predictions.json` records look like:

```json
{"timestamp": "2026-07-31 12:45:01.123", "command": "push", "confidence": 0.98}
```

The `command` field's values (`push`, `pull`, `left`, `right`, `lift`,
`drop`, `neutral`, ...) are the same names used as keys in
`mappings/gesture_map.json` — they are **raw predicted gestures**, not
resolved MasterHub commands. So the sender POSTs:

```json
{"gesture": "push", "params": {"confidence": 0.98, "source": "emotiv_simulator"}}
```

and lets MasterHub's own `InputProcessor` resolve the gesture through
`gesture_map.json` using the FSM's current mode — identical to how a
dashboard button or a future live Cortex stream would be handled. The
simulator never hardcodes gesture→command→domain mappings itself,
avoiding any duplication of `core/input_processor.py` or
`core/router.py` logic.

`params.confidence` is also forwarded so `core/engine.py`'s own
optional confidence check runs too. This is intentional, not
duplicated logic: the simulator's Confidence Filter decides whether a
prediction is worth an HTTP call at all (so a live Cortex stream
doesn't hammer the API with noise); MasterHub's check is its own last
line of defense regardless of which client is talking to it.

## Usage

Run from the MasterHub project root (one level above `simulator/`),
with the Flask server (`app.py`) already running:

```bash
# Windows
python app.py
python -m simulator.replay
```

Options:

```bash
python -m simulator.replay --speed 2                 # 2x playback speed
python -m simulator.replay --speed 5                 # 5x playback speed
python -m simulator.replay --real-time                # replay using real recorded time gaps
python -m simulator.replay --threshold 0.85            # override confidence threshold (default 0.80)
python -m simulator.replay --cooldown 750               # override stabilizer cooldown, ms (default 500)
python -m simulator.replay --file "C:\path\other.json"  # replay a different prediction file
python -m simulator.replay --base-url http://127.0.0.1:5000  # override MasterHub URL
python -m simulator.replay --limit 100                  # only replay the first 100 predictions
python -m simulator.replay --help
```

By default the simulator reads `emotiv_bci_predictions.json` from the
MasterHub project root. Override with `--file`, or the
`EMOTIV_PREDICTIONS_FILE` environment variable. No paths are hardcoded
anywhere in the code — everything is derived from `simulator/config.py`
relative to this folder, so the project can live anywhere on disk
(Windows included).

## Console output

A live table streams one row per prediction:

```
#     | Timestamp    | Gesture | Conf | Mode        | Resolved Cmd  | Domain | Action        | HTTP | Resp  | Status
------------------------------------------------------------------------------------------------------------------
1     | 12:45:01.123 | push    | 98%  | DESKTOP_MODE| open_chrome   | desktop| open_chrome   | 200  | 42ms  | PASS
2     | 12:45:01.353 | push    | 98%  | DESKTOP_MODE| -             | -      | -             | -    | -     | SKIP
3     | 12:45:02.100 | left    | 55%  | DESKTOP_MODE| -             | -      | -             | -    | -     | REJECT
```

- **PASS** — sent to MasterHub and it reported success
- **FAIL** — sent but MasterHub reported failure, or the HTTP request errored
- **REJECT** — dropped by the Confidence Filter (below threshold)
- **SKIP** — dropped by the Gesture Stabilizer (duplicate within cooldown)

At the end, a summary is printed and logged:

```
==================================================
Simulation Finished
Total Predictions      : 1260
Accepted               : 1180
Rejected               : 80
Commands Executed      : 640
Skipped                : 620 (80 low-confidence, 540 duplicate)
Average Confidence     : 97%
Average Response Time  : 38ms
Desktop Commands       : 210
IoT Commands           : 150
Embedded Commands      : 90
Media Commands         : 190
Failures               : 0
==================================================
```

## Logging

Every run writes to `simulator/logs/simulation.log` (rotating, same
pattern as `services/logger_service.py`'s `logs/masterhub.log`, kept
completely separate so replay runs never interleave with MasterHub's
own log). Each processed prediction logs one `RESULT` line with
timestamp, gesture, confidence, resolved mode, resolved command, the
MasterHub API response, and success/failure — plus per-stage DEBUG/INFO
lines from the filter, stabilizer, and sender, and a final `SUMMARY`
line matching the console summary.

## Phase 2: swapping in the real Cortex stream

Only `prediction_reader.py` needs to change. Replace `PredictionReader`
with a Cortex WebSocket client that yields the same `Prediction`
objects (`index`, `timestamp`, `gesture`, `confidence`) from a
`.read()` generator. `confidence_filter.py`, `stabilizer.py`,
`sender.py`, `replay.py`, and `logger.py` all stay exactly as they are
— they only depend on the `Prediction` shape, never on how it was
produced.

## Requirements

- Python 3.11+
- `requests` (already a dependency elsewhere in this project, e.g. `tests/desktop.py`)
- MasterHub's Flask server running and reachable at the configured base URL
