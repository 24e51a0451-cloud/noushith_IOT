"""
input_processor.py
-------------------
Normalizes heterogeneous frontend input into a single, canonical
"normalized command" string that the Router/Engine can act on.

Accepted input shapes (POST /api/command body):
    { "command": "left_light_on" }                       # direct text command
    { "gesture": "push" }                                 # raw gesture
    { "gesture": "push", "mode": "MEDIA_MODE" }            # gesture with explicit context override
    { "eeg_window": [[...], [...], ...] }                  # raw EEG signal window

Resolution order:
    1. If 'command' is present -> normalize and use directly (lowercased/trimmed).
    2. Else if 'eeg_window' is present -> classify via eeg_service into a gesture,
       then resolve that gesture via the gesture map (same as step 3).
    3. Else if 'gesture' is present -> resolve via gesture_map.json using the
       current StateManager mode (or an explicit 'mode' override in the payload).

Any unresolved input raises ValueError with a clear message, which the API
layer turns into a 400 response.
"""

import json
import os

from core.state import state_manager, Mode
from services.eeg_service import eeg_service
from services.logger_service import get_logger

log = get_logger("core.input_processor")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GESTURE_MAP_PATH = os.path.join(_BASE_DIR, "mappings", "gesture_map.json")


class InputProcessor:
    def __init__(self, gesture_map_path: str = _GESTURE_MAP_PATH):
        self.gesture_map_path = gesture_map_path
        self._gesture_map = {}
        self._load_gesture_map()

    def _load_gesture_map(self):
        try:
            with open(self.gesture_map_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._gesture_map = {k: v for k, v in data.items() if not k.startswith("_")}
            log.info(f"Loaded gesture map with {len(self._gesture_map)} gestures")
        except FileNotFoundError:
            log.error(f"gesture_map.json not found at {self.gesture_map_path}")
            self._gesture_map = {}
        except json.JSONDecodeError as exc:
            log.error(f"gesture_map.json invalid JSON: {exc}")
            self._gesture_map = {}

    def reload(self):
        self._load_gesture_map()

    # ---------- public API ----------

    def normalize(self, payload: dict) -> str:
        """
        Take the raw request payload and return a normalized command string.
        Raises ValueError if nothing usable was found.
        """
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")

        if payload.get("command"):
            return self._normalize_text_command(payload["command"])

        if payload.get("eeg_window") is not None:
            gesture = eeg_service.classify(payload["eeg_window"])
            log.debug(f"EEG window classified as gesture '{gesture}'")
            return self._resolve_gesture(gesture, payload.get("mode"))

        if payload.get("gesture"):
            return self._resolve_gesture(payload["gesture"], payload.get("mode"))

        raise ValueError("Payload must contain one of: 'command', 'gesture', 'eeg_window'")

    # ---------- internal helpers ----------

    @staticmethod
    def _normalize_text_command(raw_command: str) -> str:
        if not isinstance(raw_command, str):
            raise ValueError("'command' must be a string")
        return raw_command.strip().lower().replace(" ", "_")

    def _resolve_gesture(self, raw_gesture: str, mode_override: str = None) -> str:
        if not isinstance(raw_gesture, str):
            raise ValueError("'gesture' must be a string")

        gesture = raw_gesture.strip().lower().replace(" ", "")
        gesture_entry = self._gesture_map.get(gesture)
        if gesture_entry is None:
            raise ValueError(f"Unrecognized gesture: '{raw_gesture}'")

        if mode_override:
            try:
                active_mode = Mode(mode_override.strip().upper())
            except ValueError:
                raise ValueError(f"Unknown mode override: '{mode_override}'")
        else:
            active_mode = state_manager.mode

        command = gesture_entry.get(active_mode.value, gesture_entry.get("default"))
        if command is None:
            raise ValueError(f"Gesture '{gesture}' has no mapping for mode '{active_mode.value}'")

        log.debug(f"Gesture '{gesture}' in mode '{active_mode.value}' -> command '{command}'")
        return command


input_processor = InputProcessor()
