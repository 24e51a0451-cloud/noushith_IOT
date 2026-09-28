"""
command_validator.py
---------------------
Validates that a normalized command string is known to the system before
it's allowed to flow into the Router/Engine. Keeps validation logic out
of the engine and out of big if-else chains — it's just a JSON lookup.
"""

import json
import os

from services.logger_service import get_logger

log = get_logger("services.validator")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_COMMAND_MAP_PATH = os.path.join(_BASE_DIR, "mappings", "command_map.json")


class CommandValidator:
    def __init__(self, command_map_path: str = _COMMAND_MAP_PATH):
        self.command_map_path = command_map_path
        self._valid_commands = set()
        self._load()

    def _load(self):
        try:
            with open(self.command_map_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._valid_commands = {k for k in data.keys() if not k.startswith("_")}
            log.info(f"Loaded {len(self._valid_commands)} valid commands from command_map.json")
        except FileNotFoundError:
            log.error(f"command_map.json not found at {self.command_map_path}")
            self._valid_commands = set()
        except json.JSONDecodeError as exc:
            log.error(f"command_map.json is invalid JSON: {exc}")
            self._valid_commands = set()

    def reload(self):
        """Re-read the command map from disk (useful after editing it live)."""
        self._load()

    def is_valid(self, command: str) -> bool:
        if not command or not isinstance(command, str):
            return False
        return command in self._valid_commands

    def validate_or_raise(self, command: str) -> str:
        if not self.is_valid(command):
            log.warning(f"Rejected unknown command: '{command}'")
            raise ValueError(f"Unknown command: '{command}'")
        return command

    def all_commands(self):
        return sorted(self._valid_commands)


command_validator = CommandValidator()
