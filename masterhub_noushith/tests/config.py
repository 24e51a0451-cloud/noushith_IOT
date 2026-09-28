"""
config.py
---------
Single source of configuration for the MasterHub Automated Gesture
Validation framework.

Every path below is resolved RELATIVE TO THE MASTERHUB PROJECT ROOT, which
is computed automatically as "the parent folder of this 'tests' directory".
That's what makes this framework plug-and-play: as long as you copy the
whole "tests" folder into the root of your MasterHub project (next to
app.py, mappings/, logs/), everything resolves correctly with no edits.

You only need to touch this file if:
    - your MasterHub server runs on a different host/port
    - your mappings/ or logs/ folders live somewhere non-standard
    - you want to tune timeouts / delays / output locations
"""

import os

# ---------------------------------------------------------------------------
# PROJECT ROOT (do not change) — parent directory of this "tests" folder.
# ---------------------------------------------------------------------------
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)

# ---------------------------------------------------------------------------
# API CONFIGURATION
# ---------------------------------------------------------------------------
# Base URL of the running MasterHub Flask server.
API_BASE_URL = "http://127.0.0.1:5000"

# Endpoint that accepts {"gesture": ..., "mode": ...} payloads.
API_COMMAND_ENDPOINT = "/api/command"

# Endpoint used for the pre-flight reachability check.
API_HEALTH_ENDPOINT = "/api/health"

# Seconds to wait for each HTTP request before giving up.
REQUEST_TIMEOUT = 5

# ---------------------------------------------------------------------------
# LOG CONFIGURATION
# ---------------------------------------------------------------------------
# Path to MasterHub's runtime log file (see services/logger_service.py).
LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "logs", "masterhub.log")

# After sending a gesture, how long to wait (seconds) before reading the
# log file, to give the RotatingFileHandler time to flush the new lines.
LOG_READ_DELAY = 0.3

# ---------------------------------------------------------------------------
# MAPPING FILE PATHS (the config-driven source of truth for test generation)
# ---------------------------------------------------------------------------
GESTURE_MAP_PATH = os.path.join(PROJECT_ROOT, "mappings", "gesture_map.json")
MODE_MAP_PATH = os.path.join(PROJECT_ROOT, "mappings", "mode_map.json")
COMMAND_MAP_PATH = os.path.join(PROJECT_ROOT, "mappings", "command_map.json")

# ---------------------------------------------------------------------------
# TEST EXECUTION
# ---------------------------------------------------------------------------
# Seconds to sleep between each generated test case. Keep this non-zero:
# tests share the SAME running MasterHub instance and its real FSM/log
# file, so a little breathing room avoids interleaved log output and
# gives slower domain handlers (e.g. desktop automation) time to finish.
DELAY_BETWEEN_TESTS = 0.5

# Domains to skip entirely (no request sent for test cases whose expected
# domain is in this set). Useful if you don't want a full run to actually
# open Chrome / toggle real IoT hardware / move a physical chair.
# Valid values seen in command_map.json: "desktop", "iot", "embedded", "ai_ml"
SKIP_DOMAINS = set()  # e.g. {"iot", "embedded"}

# Specific gestures or modes to exclude from generation entirely.
EXCLUDE_GESTURES = set()   # e.g. {"long_neutral"}
EXCLUDE_MODES = set()      # e.g. {"CAR_MODE"}

# ---------------------------------------------------------------------------
# REPORTING
# ---------------------------------------------------------------------------
REPORT_OUTPUT_DIR = os.path.join(TESTS_DIR, "reports")
REPORT_JSON_PATH = os.path.join(REPORT_OUTPUT_DIR, "report.json")
REPORT_CSV_PATH = os.path.join(REPORT_OUTPUT_DIR, "report.csv")
REPORT_HTML_PATH = os.path.join(REPORT_OUTPUT_DIR, "report.html")

# Print full per-test detail to the console (set False for a terser run).
VERBOSE_CONSOLE = True

# Use ANSI colour in console output (auto-disabled if output isn't a TTY).
COLOR_OUTPUT = True

# Root config fallback / re-exports
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_PROFILE = "Profile 5"
CHROME_ARGS = [f"--profile-directory={CHROME_PROFILE}"]
