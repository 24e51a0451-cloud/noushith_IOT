"""
simulator/config.py
--------------------
All tunables for the Emotiv Cortex Phase-1 simulator live here, mirroring
how the main project keeps its knobs in the top-level config.py rather
than scattered through the code.

Nothing here is hardcoded as an absolute path -- everything is derived
from this file's location so the simulator runs unmodified regardless of
where the MasterHub project folder lives (including on Windows).
"""

import os
PREDICTION_SOURCE = os.getenv(
    "PREDICTION_SOURCE",
    "masterhub",
)
# --------------------------------------------------------------------
# Paths (all derived, nothing hardcoded)
# --------------------------------------------------------------------

# masterhub/simulator/
_SIMULATOR_DIR = os.path.dirname(os.path.abspath(__file__))

# masterhub/  (the existing project root -- never written to except
# through the real HTTP API, per the "do not modify MasterHub" rule)
PROJECT_ROOT = os.path.dirname(_SIMULATOR_DIR)

# Recorded prediction stream this simulator replays. Defaults to the
# file living at the project root (masterhub/emotiv_bci_predictions.json)
# but can be overridden with --file on the command line or the
# EMOTIV_PREDICTIONS_FILE environment variable.
DEFAULT_PREDICTIONS_FILE = os.environ.get(
    "EMOTIV_PREDICTIONS_FILE",
    os.path.join(PROJECT_ROOT, "emotiv_bci_predictions.json"),
)

# simulator/logs/simulation.log -- kept separate from
# masterhub/logs/masterhub.log so the simulator never touches the real
# system's log file, but follows the exact same rotating-file pattern
# as services/logger_service.py.
LOG_DIR = os.path.join(_SIMULATOR_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "simulation.log")

# --------------------------------------------------------------------
# MasterHub API connection
# --------------------------------------------------------------------

# MasterHub's Flask server (app.py) listens on 0.0.0.0:5000 by default.
MASTERHUB_HOST = os.environ.get("MASTERHUB_HOST", "127.0.0.1")
MASTERHUB_PORT = int(os.environ.get("MASTERHUB_PORT", "5000"))
MASTERHUB_BASE_URL = f"http://{MASTERHUB_HOST}:{MASTERHUB_PORT}"

# The simulator must use MasterHub's EXISTING command endpoint. MasterHub
# exposes POST /api/command (see api/routes.py) -- there is no separate
# /api/send_command route, and Phase 1 does not add one. The simulator
# always sends {"gesture": <name>, "params": {...}} so the request flows
# through the exact same InputProcessor -> gesture_map.json -> Engine ->
# Router pipeline a live Cortex stream would use.
COMMAND_ENDPOINT = "/api/command"
COMMAND_URL = f"{MASTERHUB_BASE_URL}{COMMAND_ENDPOINT}"

# HTTP request timeout, in seconds.
REQUEST_TIMEOUT_SECONDS = 5.0

# Number of HTTP retries on connection errors (e.g. MasterHub still
# starting up). 0 disables retrying.
REQUEST_MAX_RETRIES = 2
REQUEST_RETRY_BACKOFF_SECONDS = 0.5

# --------------------------------------------------------------------
# Confidence Filter
# --------------------------------------------------------------------

# Predictions below this confidence are rejected before ever reaching
# MasterHub. Overridable with --threshold or BCI_CONFIDENCE_THRESHOLD.
DEFAULT_CONFIDENCE_THRESHOLD = float(os.getenv("BCI_CONFIDENCE_THRESHOLD", os.getenv("CONFIDENCE_THRESHOLD", "0.20")))

# --------------------------------------------------------------------
# Gesture Stabilizer
# --------------------------------------------------------------------

# Minimum time (ms) that must pass before the SAME gesture is allowed to
# be sent again. Prevents a held/repeated gesture (push, push, push,
# push...) from flooding MasterHub with duplicate commands.
# Overridable with --cooldown.
DEFAULT_STABILIZER_COOLDOWN_MS = 500

# --------------------------------------------------------------------
# Replay
# --------------------------------------------------------------------

# Supported fixed playback speeds (multiplies the delay between
# predictions; higher = faster). Real inter-prediction gaps can also be
# replayed as-is with --real-time.
SUPPORTED_SPEEDS = (1, 2, 5)
DEFAULT_SPEED = 1

# Confidence that is treated as "attach a confidence param" when sending
# to MasterHub, so Engine.process()'s own defense-in-depth confidence
# check (params["confidence"] / params["confidence_threshold"], see
# core/engine.py) sees the same value the simulator already filtered on.
# This is intentional double coverage, not duplicated logic: the
# simulator's ConfidenceFilter decides whether to spend an HTTP call at
# all (so a Cortex stream doesn't hammer the API with noise), while
# Engine's check is MasterHub's own last line of defense regardless of
# which client is talking to it.
FORWARD_CONFIDENCE_TO_ENGINE = True

# --------------------------------------------------------------------
# Console table
# --------------------------------------------------------------------

# Domains recognized by MasterHub's router (core/router.py VALID_DOMAINS)
# used to bucket the end-of-run summary counts.
KNOWN_DOMAINS = ("desktop", "iot", "embedded", "ai_ml")
