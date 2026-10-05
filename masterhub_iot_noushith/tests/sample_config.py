"""
sample_config.py
-----------------
This is a REFERENCE / TEMPLATE copy of config.py. It is not imported by
anything in this framework — it exists purely so you always have an
untouched, fully-commented example to compare against or restore from
if you ever want to reset config.py to its defaults.

To use it: copy this file's contents over config.py, then adjust the
values in the "commonly changed" section below for your environment.

=================================================================
COMMONLY CHANGED VALUES
=================================================================

1. API_BASE_URL
   If MasterHub's Flask server isn't running on localhost:5000, change
   this. Example for a server exposed on your LAN:

       API_BASE_URL = "http://192.168.1.50:5000"

2. LOG_FILE_PATH
   By default this points at <project_root>/logs/masterhub.log, which
   matches services/logger_service.py's LOG_FILE constant. Only change
   this if you've customized logging in your MasterHub deployment.

3. DELAY_BETWEEN_TESTS
   Lower this (e.g. 0.1) for a faster run once you trust your setup.
   Raise it (e.g. 1.0+) if you see WARNING lines about missing log
   evidence — usually a sign the log handler needs more time to flush
   before the next test starts.

4. SKIP_DOMAINS
   The full test suite really executes gestures against your live
   MasterHub instance, meaning real side effects happen (Chrome opens,
   IoT/MQTT commands fire, etc.). Add domains here to skip those test
   cases without deleting them from the report — they'll show up with
   status "SKIPPED".

       SKIP_DOMAINS = {"iot", "embedded"}

=================================================================
FULL TEMPLATE (identical structure to config.py)
=================================================================
"""

import os

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)

# --- API ---
API_BASE_URL = "http://127.0.0.1:5000"
API_COMMAND_ENDPOINT = "/api/command"
API_HEALTH_ENDPOINT = "/api/health"
REQUEST_TIMEOUT = 5

# --- Logs ---
LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "logs", "masterhub.log")
LOG_READ_DELAY = 0.3

# --- Mappings (config-driven source of truth) ---
GESTURE_MAP_PATH = os.path.join(PROJECT_ROOT, "mappings", "gesture_map.json")
MODE_MAP_PATH = os.path.join(PROJECT_ROOT, "mappings", "mode_map.json")
COMMAND_MAP_PATH = os.path.join(PROJECT_ROOT, "mappings", "command_map.json")

# --- Execution ---
DELAY_BETWEEN_TESTS = 0.5
SKIP_DOMAINS = set()
EXCLUDE_GESTURES = set()
EXCLUDE_MODES = set()

# --- Reporting ---
REPORT_OUTPUT_DIR = os.path.join(TESTS_DIR, "reports")
REPORT_JSON_PATH = os.path.join(REPORT_OUTPUT_DIR, "report.json")
REPORT_CSV_PATH = os.path.join(REPORT_OUTPUT_DIR, "report.csv")
REPORT_HTML_PATH = os.path.join(REPORT_OUTPUT_DIR, "report.html")
VERBOSE_CONSOLE = True
COLOR_OUTPUT = True
