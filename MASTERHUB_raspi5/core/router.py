"""
router.py
---------
The Router's ONLY job is to decide *which domain* a normalized command
belongs to, and what action identifier within that domain to call.
It does NOT execute anything itself — no pyautogui, no MQTT, no logic.
That's the Engine's job (via the actions/ dispatch tables).

This is a pure JSON lookup against mappings/command_map.json, which is
exactly why adding a new command never requires touching this file or
the engine — only the JSON map and the corresponding action handler.
"""

import json
import os

from services.logger_service import get_logger

log = get_logger("core.router")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_COMMAND_MAP_PATH = os.path.join(_BASE_DIR, "mappings", "command_map.json")

VALID_DOMAINS = {"desktop", "iot", "embedded", "ai_ml"}


class RouteResult:
    """Simple value object describing where a command should go."""

    __slots__ = ("domain", "action", "command")

    def __init__(self, domain: str, action: str, command: str):
        self.domain = domain
        self.action = action
        self.command = command

    def to_dict(self):
        return {"domain": self.domain, "action": self.action, "command": self.command}

    def __repr__(self):
        return f"RouteResult(domain={self.domain!r}, action={self.action!r}, command={self.command!r})"


class Router:
    def __init__(self, command_map_path: str = _COMMAND_MAP_PATH):
        self.command_map_path = command_map_path
        self._command_map = {}
        self._load()

    def _load(self):
        try:
            with open(self.command_map_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._command_map = {k: v for k, v in data.items() if not k.startswith("_")}
            log.info(f"Router loaded {len(self._command_map)} command routes")
        except FileNotFoundError:
            log.error(f"command_map.json not found at {self.command_map_path}")
            self._command_map = {}
        except json.JSONDecodeError as exc:
            log.error(f"command_map.json invalid JSON: {exc}")
            self._command_map = {}

    def reload(self):
        self._load()

    def route(self, normalized_command: str) -> RouteResult:
        """
        Resolve a normalized command into a RouteResult(domain, action).
        Raises ValueError if the command has no route (caller / validator
        should ideally have already rejected unknown commands, but this
        is a defensive second check).
        """
        entry = self._command_map.get(normalized_command)
        if entry is None:
            log.warning(f"No route found for command '{normalized_command}'")
            raise ValueError(f"No route found for command: '{normalized_command}'")

        domain = entry.get("domain")
        action = entry.get("action")

        if domain not in VALID_DOMAINS:
            log.error(f"Command '{normalized_command}' maps to invalid domain '{domain}'")
            raise ValueError(f"Invalid domain '{domain}' for command '{normalized_command}'")

        result = RouteResult(domain=domain, action=action, command=normalized_command)
        log.debug(f"Routed: {result}")
        return result


router = Router()
