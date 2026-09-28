# MasterHub Automated Gesture Validation

A self-contained, config-driven test framework that automatically discovers
every gesture and mode MasterHub knows about (from `mappings/gesture_map.json`,
`mappings/mode_map.json`, `mappings/command_map.json`), generates every valid
test case, sends real gestures to your running MasterHub API, cross-checks
the result against both the API's own response **and** independently
regex-parsed log lines, and produces console/JSON/CSV/HTML reports.

**Nothing about MasterHub is modified.** This framework only reads your
JSON mapping files, sends HTTP requests to the API MasterHub already
exposes, reads the log file MasterHub already writes, and writes its own
report files under `tests/reports/`.

> ⚠️ **Important — this executes real actions.** Gestures sent by this
> framework go through the *exact same pipeline* as a real device: Chrome
> really opens, IoT/MQTT commands really fire, the embedded/chair domain
> really publishes over MQTT. If you don't want that on a given run, see
> `SKIP_DOMAINS` in Configuration below.

> ℹ️ **Your project already has a `tests/` folder.** This framework ships
> as a flat set of files (`config.py`, `run_tests.py`, etc.) that live
> alongside your existing `tests/__init__.py`, `tests/test_core.py`, and
> `tests/desktop.py` with **no filename collisions** — nothing of yours
> gets overwritten. We deliberately do not ship our own `__init__.py`.

---

## Installation

1. Copy the entire `tests` folder from this delivery into the root of
   your MasterHub project — the same folder that contains `app.py` and
   `mappings/`. If your project already has files with these exact
   names in `tests/`, this framework's files will sit next to them
   (there are no name clashes with `__init__.py`, `test_core.py`, or
   `desktop.py`).

2. Install the one dependency:

   ```bash
   pip install -r tests/requirements.txt
   ```

3. Start MasterHub as usual, in a separate terminal:

   ```bash
   python app.py
   ```

## Usage

With MasterHub running:

```bash
python tests/run_tests.py
```

That's it. The script will:

1. Load your three mapping files and auto-discover every gesture/mode.
2. Generate every `(gesture, mode)` test case and its expected outcome.
3. Confirm the API is reachable (`GET /api/health`) before doing anything else.
4. Send each gesture to `POST /api/command`, wait briefly, then read only
   the *new* lines MasterHub wrote to its log file for that request.
5. Compare expected vs. actual command / domain / action / success, using
   the API's JSON response as the source of truth and the parsed log
   lines as an independent cross-check.
6. Print a full console report and write `report.json`, `report.csv`,
   and `report.html` to `tests/reports/`.

The process exits with code `0` if every executed test passed, or `1` if
any test failed — safe to wire into CI.

## How to change the API URL

Edit `tests/config.py`:

```python
API_BASE_URL = "http://127.0.0.1:5000"   # <- change host/port here
API_COMMAND_ENDPOINT = "/api/command"
API_HEALTH_ENDPOINT = "/api/health"
```

## How to change the log path

Edit `tests/config.py`:

```python
LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "logs", "masterhub.log")
```

By default this matches `services/logger_service.py`'s `LOG_FILE`
constant exactly, so you normally won't need to touch it unless your
MasterHub deployment customizes logging.

## Other configuration

All in `tests/config.py` (see `tests/sample_config.py` for a fully
commented reference copy you can restore from):

| Setting | Purpose |
|---|---|
| `REQUEST_TIMEOUT` | Seconds to wait for each HTTP request. |
| `DELAY_BETWEEN_TESTS` | Pause between test cases, so log writes don't interleave. |
| `LOG_READ_DELAY` | Pause after sending a gesture before reading new log lines. |
| `SKIP_DOMAINS` | e.g. `{"iot", "embedded"}` — skip test cases whose expected domain is in this set, without deleting them from the report (they show as `SKIPPED`). Use this if you don't have real IoT hardware / an MQTT broker / a desktop with a display attached. |
| `EXCLUDE_GESTURES` / `EXCLUDE_MODES` | Drop specific gestures/modes from generation entirely. |
| `VERBOSE_CONSOLE` | Print the full per-test detail block (Gesture / Mode / Expected / Actual / Result) for every test, not just the one-line progress feed. |
| `COLOR_OUTPUT` | Enable/disable ANSI colour in the console report. |

## Expected output

Console (per test, when `VERBOSE_CONSOLE = True`):

```
Test 1
--------------------------------------------------
Gesture           : push
Current Mode      : IDLE
Expected Command  : mode_desktop
Actual Command    : mode_desktop
Expected Success  : True
Actual Success    : True
HTTP Status       : 200
Execution Time    : 2.5 ms
Result            : PASS
--------------------------------------------------
```

For domain-action tests you'll also see Expected/Actual Domain and Action:

```
Test 3
--------------------------------------------------
Gesture           : push
Current Mode      : DESKTOP_MODE
Expected Command  : open_chrome
Actual Command    : open_chrome
Expected Domain   : desktop
Actual Domain     : desktop
Expected Action   : open_chrome
Actual Action     : open_chrome
Expected Success  : True
Actual Success    : False
HTTP Status       : 422
Execution Time    : 3.5 ms
Result            : FAIL
  - Execution success mismatch: expected True, got False
  error: Desktop automation requires pyautogui and a Windows desktop.
--------------------------------------------------
```

(That specific failure is a *correct* result from a machine with no
display attached — not a bug in the framework. See Troubleshooting.)

Summary block:

```
======================================================================
SUMMARY
Total Tests       : 56
Executed          : 56
Skipped           : 0
Passed            : 26
Failed            : 30
Accuracy          : 46.43%
Execution Time    : 60.23s
======================================================================
```

Plus, at the end:

```
Detailed reports written to:
  tests/reports/report.json
  tests/reports/report.csv
  tests/reports/report.html
```

`report.html` renders a dark, colour-coded, sortable-by-eye table (green
row = PASS, red = FAIL, yellow = SKIPPED) with the same per-test detail,
plus a header showing the same summary counters. `report.json` is a
machine-readable version (`{"summary": {...}, "results": [...]}`), and
`report.csv` is a flat spreadsheet-friendly export — both suitable for
feeding into CI dashboards.

## Folder structure

```
tests/
├── README.md              <- this file
├── requirements.txt        <- just "requests"
├── config.py                <- YOUR active configuration (edit this)
├── sample_config.py         <- untouched reference copy of config.py
├── run_tests.py              <- entry point: python tests/run_tests.py
├── test_generator.py         <- discovers gestures/modes, builds test cases
├── gesture_sender.py         <- sends gestures to the live API
├── log_parser.py             <- regex-parses new MasterHub log lines
├── validator.py              <- compares expected vs. actual, PASS/FAIL
├── report_generator.py       <- console + JSON + CSV + HTML reports
├── utils.py                  <- colour output / file I/O helpers
└── reports/                   <- created at runtime
    ├── report.json
    ├── report.csv
    └── report.html
```

## Example report (excerpt of `report.json`)

```json
{
  "summary": {
    "generated_at": "2026-08-03T07:58:00",
    "total_tests": 56,
    "executed": 56,
    "skipped": 0,
    "passed": 26,
    "failed": 30,
    "accuracy_percent": 46.43,
    "execution_time_seconds": 60.23,
    "generation_warnings": [
      {"gesture": "push", "orphaned_mode_key": "MEDIA_MODE1"}
    ]
  },
  "results": [
    {
      "index": 1,
      "gesture": "push",
      "mode": "IDLE",
      "expected_command": "mode_desktop",
      "actual_command": "mode_desktop",
      "expected_type": "mode_switch",
      "expected_success": true,
      "actual_success": true,
      "status": "PASS",
      "reasons": [],
      "log_verified": true,
      "log_notes": ["Observed real FSM transition Mode.IDLE -> Mode.DESKTOP_MODE"],
      "elapsed_ms": 2.45,
      "http_status": 200
    }
  ]
}
```

`generation_warnings` calls out gesture/mode-key combinations in
`gesture_map.json` that don't correspond to any mode actually registered
in `mode_map.json` (e.g. this project's `MEDIA_MODE1` / `MEDIA_MODE2`
entries) — these are unreachable dead configuration, not test failures,
and are surfaced so you can clean them up if they're not intentional.

## Troubleshooting

**"Could not reach MasterHub at http://127.0.0.1:5000"**
MasterHub isn't running, or `API_BASE_URL` in `config.py` doesn't match
its actual host/port. Start it with `python app.py` and confirm
`GET /api/health` works in a browser or with `curl` first.

**Every IoT-domain test fails with "No online IoT device found"**
This is MasterHub's own IoT handler correctly reporting it has no
connected device to command — expected behaviour on a dev machine
without real hardware, not a framework bug. Add `"iot"` to
`SKIP_DOMAINS` in `config.py` if you want to skip these.

**Every desktop-domain test fails with "pyautogui ... requires a display"**
Same idea — MasterHub's desktop automation needs a real GUI session.
Add `"desktop"` to `SKIP_DOMAINS`, or run the suite on a machine with a
display attached.

**Embedded/chair or car tests take ~5 seconds each and then fail with a
read timeout**
The embedded domain publishes over MQTT; if no broker is reachable, the
publish call blocks until connection failure. Either add `"embedded"` to
`SKIP_DOMAINS`, or raise `REQUEST_TIMEOUT` if you'd rather wait it out.

**"WARNING: log file not found at .../logs/masterhub.log"**
Confirm `LOG_FILE_PATH` in `config.py` points at the same file
`services/logger_service.py` writes to, and that MasterHub has been run
at least once (the log directory/file are created on first import).
Tests still run and PASS/FAIL correctly from the API response alone —
you just lose the independent log cross-check (`log_verified` will be
`false` for every result).

**A test's `log_verified` is `false` but the test still `PASS`ed**
This means the API confirmed success, but this framework's read window
(`LOG_READ_DELAY`) closed before the corresponding log line was flushed
to disk. It's a timing note, not a failure — raise `LOG_READ_DELAY`
slightly (e.g. to `0.5`) if you want tighter log confirmation on every
single test.

**I get lots of `FAIL`s for gestures resolving to `neutral`**
That's actually *correct*: `gesture_map.json`'s `neutral` gestures
intentionally resolve to a command string that isn't in
`command_map.json`, so MasterHub's `CommandValidator` is *supposed* to
reject it as `"Unknown command: 'neutral'"`. This framework classifies
that case as `expected_type: "unknown_command"` and expects
`success: false` — if you see it reported as `PASS`, that's the
framework confirming MasterHub is rejecting it exactly as designed.
