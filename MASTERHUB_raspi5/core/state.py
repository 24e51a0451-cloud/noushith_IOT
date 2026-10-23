"""
state.py
--------
Centralized Finite State Machine (FSM) for MasterHub.

Why this exists:
    Gestures like 'push', 'left', 'lift' are ambiguous on their own — 'push'
    means "chair forward" in CHAIR_MODE but "play" in MEDIA_MODE. The
    StateManager tracks *which mode* the system is currently in and is the
    single source of truth for that context. Nothing else in the codebase
    is allowed to decide "what mode are we in" — they ask StateManager.

Modes (registered in mappings/mode_map.json, not hardcoded here):
    IDLE          - default/no active domain focus
    IOT_MODE      - lights/fans/pumps control active
    DESKTOP_MODE  - desktop automation active
    EMBEDDED_MODE - gesture-driven embedded controller (wheelchair) active
    MEDIA_MODE    - AI/ML media control active
    CHAIR_MODE    - legacy wheelchair control mode (dashboard/back-compat)
    CAR_MODE      - legacy robot car control mode (dashboard/back-compat)

Mode switching is itself driven by specific commands (mode_*) so the FSM
stays explicit and centralized rather than inferred ad hoc elsewhere.

Scalability note:
    The set of valid modes and their mode_* switch command is loaded from
    mappings/mode_map.json at import time, NOT hardcoded as a Python enum
    literal. Adding a brand new mode (e.g. "GAME_MODE") only requires:
        1. Adding an entry to mappings/mode_map.json
        2. Adding gesture rules for it in mappings/gesture_map.json
        3. Adding its domain commands to mappings/command_map.json
    No change to this file, core/engine.py, or core/router.py is required.
"""

import json
import os
import threading
from enum import Enum

from services.logger_service import get_logger

log = get_logger("core.state")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODE_MAP_PATH = os.path.join(_BASE_DIR, "mappings", "mode_map.json")

# Fallback used only if mode_map.json is missing/invalid, so the system
# still boots with the original, pre-gesture-update mode set.
_FALLBACK_MODES = {
    "IDLE": "mode_idle",
    "CHAIR_MODE": "mode_chair",
    "CAR_MODE": "mode_car",
    "IOT_MODE": "mode_iot",
    "MEDIA_MODE": "mode_media",
    "DESKTOP_MODE": "mode_desktop",
}


def _load_mode_config(path: str = _MODE_MAP_PATH) -> dict:
    """
    Load {mode_name: switch_command} from mappings/mode_map.json.
    Falls back to the built-in default set (with a logged error) if the
    file is missing or malformed, so the app never fails to start.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        modes = data.get("modes", {})
        config = {
            name: entry.get("switch_command")
            for name, entry in modes.items()
            if isinstance(entry, dict) and entry.get("switch_command")
        }
        if not config:
            raise ValueError("mode_map.json contained no usable modes")
        log.info(f"Loaded {len(config)} modes from mode_map.json: {sorted(config)}")
        return config
    except FileNotFoundError:
        log.error(f"mode_map.json not found at {path}; falling back to built-in modes")
        return dict(_FALLBACK_MODES)
    except (json.JSONDecodeError, ValueError) as exc:
        log.error(f"mode_map.json invalid ({exc}); falling back to built-in modes")
        return dict(_FALLBACK_MODES)


_MODE_CONFIG = _load_mode_config()

# Mode is built dynamically (functional Enum API) from mode_map.json instead
# of being a fixed literal class, so registering a new mode never requires
# editing this source file. `type=str` preserves the original `class Mode
# (str, Enum)` behavior (Mode.IDLE == "IDLE", JSON-serializable via .value).
Mode = Enum("Mode", {name: name for name in _MODE_CONFIG}, type=str)

# Commands that explicitly request a mode switch (not domain actions themselves)
MODE_SWITCH_COMMANDS = {
    switch_command: Mode[name] for name, switch_command in _MODE_CONFIG.items()
}

# Legal transitions: from_mode -> set of to_modes it can move to.
# IDLE can go anywhere; every mode can return to IDLE; direct domain hops
# are also allowed since the user can switch context without going via IDLE.
_ALL_MODES = set(Mode)
TRANSITIONS = {mode: _ALL_MODES for mode in _ALL_MODES}


class StateManager:
    """
    Thread-safe FSM holding the current operating mode plus light
    last-command memory for context (e.g. last gesture per mode).
    """

    def __init__(self, initial: Mode = Mode.IDLE):
        self._lock = threading.Lock()
        self._mode: Mode = initial
        self._previous_mode: Mode = initial
        self._last_command: str = None
        self._history = []
        self._max_history = 50

    @property
    def mode(self) -> Mode:
        with self._lock:
            return self._mode

    @property
    def previous_mode(self) -> Mode:
        with self._lock:
            return self._previous_mode

    def can_transition(self, to_mode: Mode) -> bool:
        with self._lock:
            allowed = TRANSITIONS.get(self._mode, set())
            return to_mode in allowed

    def transition(self, to_mode: Mode) -> bool:
        """Attempt a mode transition. Returns True if it happened."""
        with self._lock:
            if to_mode not in TRANSITIONS.get(self._mode, set()):
                log.warning(f"Illegal transition {self._mode} -> {to_mode}")
                return False
            if to_mode != self._mode:
                log.info(f"State transition: {self._mode} -> {to_mode}")
                self._previous_mode = self._mode
                self._mode = to_mode
            return True

    def maybe_switch_mode(self, normalized_command: str) -> bool:
        """
        If the given command is a mode-switch command, perform the
        transition and return True. Otherwise return False (no-op),
        letting the caller treat it as a normal domain command.
        """
        target = MODE_SWITCH_COMMANDS.get(normalized_command)
        if target is None:
            return False
        return self.transition(target)

    def record_command(self, command: str):
        with self._lock:
            self._last_command = command
            self._history.append({"mode": self._mode.value, "command": command})
            if len(self._history) > self._max_history:
                self._history.pop(0)

    @property
    def last_command(self) -> str:
        with self._lock:
            return self._last_command

    def snapshot(self) -> dict:
        """Read-only snapshot of current state, useful for API responses/debugging."""
        with self._lock:
            return {
                "mode": self._mode.value,
                "previous_mode": self._previous_mode.value,
                "last_command": self._last_command,
                "history_length": len(self._history),
            }

    def reset(self):
        with self._lock:
            self._mode = Mode.IDLE
            self._previous_mode = Mode.IDLE
            self._last_command = None
            self._history.clear()
            log.info("StateManager reset to IDLE")


# Shared singleton state across the whole app
state_manager = StateManager()
