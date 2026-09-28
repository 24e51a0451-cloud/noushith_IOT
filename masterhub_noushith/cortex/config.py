"""
cortex/config.py
-----------------
Single source of configuration for the Cortex integration module,
mirroring the config-in-one-place convention already used elsewhere in
this project (top-level config.py, simulator/config.py,
tests/config.py): nothing configurable is hardcoded inline in the
other modules, and every path is derived rather than hardcoded so this
folder runs unmodified regardless of where it's copied on disk.

You only need to edit the values below (or set the matching
environment variables, used when no saved value exists) before running
`python -m cortex.run_live`.
"""

import os
from pathlib import Path

from dotenv import load_dotenv, dotenv_values
import threading



# ---------------------------------------------------------------------------
# LOAD MASTERHUB .ENV
# ---------------------------------------------------------------------------

_CORTEX_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _CORTEX_DIR.parent
_ENV_FILE = _PROJECT_DIR / ".env"

load_dotenv(_ENV_FILE, interpolate=False)
_CREDENTIAL_LOCK = threading.RLock()

# ---------------------------------------------------------------------------
# PATHS (derived, nothing hardcoded)
# ---------------------------------------------------------------------------

#_CORTEX_DIR = os.path.dirname(os.path.abspath(__file__))
'''
LOG_DIR = os.path.join(_CORTEX_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "cortex.log")
'''
LOG_DIR = str(_CORTEX_DIR / "logs")
LOG_FILE = str(_CORTEX_DIR / "logs" / "cortex.log")
'''
# ---------------------------------------------------------------------------
# CORTEX APPLICATION CREDENTIALS
# ---------------------------------------------------------------------------
# Obtained from your Emotiv account at https://www.emotiv.com/my-account/cortex-apps/
# See README.md -> "How to obtain Cortex API credentials".
CLIENT_ID = os.environ.get("CORTEX_CLIENT_ID", "YOUR_CORTEX_CLIENT_ID")
CLIENT_SECRET = os.environ.get("CORTEX_CLIENT_SECRET", "YOUR_CORTEX_CLIENT_SECRET")

# Optional. Only required for licensed/pro features (e.g. raw EEG export).
# Leave as an empty string to use whatever free-tier access your Emotiv
# account already has.
LICENSE = os.environ.get("CORTEX_LICENSE", "")
'''
def reload_credentials() -> tuple[str, str, str, str]:
    """Reload credentials from .env or environment dynamically."""
    global CLIENT_ID, CLIENT_SECRET, LICENSE, CORTEX_URL
    with _CREDENTIAL_LOCK:
        saved = dotenv_values(_ENV_FILE, interpolate=False)
        def value(key, default=""):
            return (saved.get(key, os.getenv(key, default)) or "").strip()
        CLIENT_ID = value("CORTEX_CLIENT_ID")
        CLIENT_SECRET = value("CORTEX_CLIENT_SECRET")
        LICENSE = value("CORTEX_LICENSE")
        CORTEX_URL = value("CORTEX_URL", "wss://localhost:6868")
        return CLIENT_ID, CLIENT_SECRET, LICENSE, CORTEX_URL


CLIENT_ID = os.getenv("CORTEX_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("CORTEX_CLIENT_SECRET", "").strip()
LICENSE = os.getenv("CORTEX_LICENSE", "").strip()
CONFIDENCE_THRESHOLD = float(os.getenv("BCI_CONFIDENCE_THRESHOLD", os.getenv("CONFIDENCE_THRESHOLD", "0.20")))
# ---------------------------------------------------------------------------
# CORTEX SERVICE CONNECTION
# ---------------------------------------------------------------------------
# The Cortex service is a local WebSocket server started by the EMOTIV
# Launcher / EMOTIV App running on the same machine (see README.md ->
# "How to start the Cortex service"). It is NOT related to MasterHub's
# own Flask server/port.
CORTEX_URL = os.environ.get("CORTEX_URL", "wss://localhost:6868")

# The Cortex service uses a self-signed TLS certificate on localhost.
# Set to False to skip certificate verification (the standard,
# documented workaround for local Cortex connections). Set to True only
# if you have installed Emotiv's local CA certificate yourself.
VERIFY_SSL = os.environ.get("CORTEX_VERIFY_SSL", "false").strip().lower() in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# STREAM SUBSCRIPTION
# ---------------------------------------------------------------------------
# Cortex stream name for mental-command (facial/cognitive action)
# predictions. Other valid Cortex stream names ("eeg", "mot", "fac",
# "met", "dev", "eq", "pow" ...) can be added later -- see
# stream.py's STREAM_HANDLERS registry, which this module was built to
# extend without modifying existing code.
STREAM_NAME = os.environ.get("CORTEX_STREAM_NAME", "com")

# ---------------------------------------------------------------------------
# SESSION
# ---------------------------------------------------------------------------
# "active" sessions are required to subscribe to most data streams;
# "open" sessions only allow raw/lightweight access. See session.py.
SESSION_STATUS = os.environ.get("CORTEX_SESSION_STATUS", "active")

# ---------------------------------------------------------------------------
# RELIABILITY
# ---------------------------------------------------------------------------
# Seconds to wait before attempting to reconnect after the WebSocket
# connection drops.
RECONNECT_DELAY = float(os.environ.get("CORTEX_RECONNECT_DELAY", "3.0"))

# Maximum consecutive reconnect attempts before giving up entirely.
# Set to 0 for unlimited attempts.
MAX_RECONNECT_ATTEMPTS = int(os.environ.get("CORTEX_MAX_RECONNECT_ATTEMPTS", "0"))

# WebSocket-level ping interval/timeout (seconds), used as the
# connection heartbeat so dead connections are detected promptly
# instead of hanging silently.
HEARTBEAT_INTERVAL = float(os.environ.get("CORTEX_HEARTBEAT_INTERVAL", "20.0"))
HEARTBEAT_TIMEOUT = float(os.environ.get("CORTEX_HEARTBEAT_TIMEOUT", "10.0"))

# Seconds to wait for a JSON-RPC response before considering the
# request timed out.
REQUEST_TIMEOUT = float(os.environ.get("CORTEX_REQUEST_TIMEOUT", "10.0"))

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
LOG_LEVEL = os.environ.get("CORTEX_LOG_LEVEL", "INFO").strip().upper()

# ---------------------------------------------------------------------------
# DASHBOARD (optional Flask blueprint, see dashboard.py)
# ---------------------------------------------------------------------------
DASHBOARD_URL_PREFIX = os.environ.get("CORTEX_DASHBOARD_PREFIX", "/cortex")
