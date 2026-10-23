"""
services/manual_logger_service.py
---------------------------------
Dedicated logging and persistent recording service for Manual commands,
keyboard arrow navigation, chorded combinations, and Web UI interactions.

Outputs:
    - logs/manual_commands.log   (Human-readable rotating text log)
    - logs/manual_commands.jsonl (Structured JSON-lines log for analysis & telemetry)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from services.logger_service import SafeRotatingFileHandler
from typing import Any, Optional

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

MANUAL_TEXT_LOG_FILE = os.path.join(_LOG_DIR, "manual_commands.log")
MANUAL_JSONL_LOG_FILE = os.path.join(_LOG_DIR, "manual_commands.jsonl")

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ManualLoggerService:
    def __init__(
        self,
        text_log_file: str = MANUAL_TEXT_LOG_FILE,
        jsonl_log_file: str = MANUAL_JSONL_LOG_FILE,
        max_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 5,
    ):
        self.text_log_file = text_log_file
        self.jsonl_log_file = jsonl_log_file
        self._lock = threading.Lock()
        self._recent_events: deque[dict] = deque(maxlen=500)

        # Configure dedicated logger
        self._logger = logging.getLogger("masterhub.manual_commands")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        if not getattr(self._logger, "_manual_handler_configured", False):
            formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
            file_handler = SafeRotatingFileHandler(
                self.text_log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)
            self._logger.addHandler(file_handler)
            self._logger._manual_handler_configured = True

    def log_manual_command(
        self,
        command: str,
        gesture: Optional[str] = None,
        input_type: str = "keyboard_arrow",
        keys_pressed: Optional[str] = None,
        routed_command: Optional[str] = None,
        domain: Optional[str] = None,
        action: Optional[str] = None,
        status: str = "SUCCESS",
        response_time_ms: Optional[float] = None,
        mode: str = "IDLE",
        reason: str = "",
        extra: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Record a manual command (keyboard arrow, combo, or UI click) to log files."""
        resp_ms_str = f"{response_time_ms:.1f}ms" if response_time_ms is not None else "—"
        routed_str = routed_command or command
        domain_str = domain or "system"
        action_str = action or routed_str
        gesture_str = gesture or "—"
        keys_str = f" [Keys: {keys_pressed}]" if keys_pressed else ""

        log_line = (
            f"MANUAL_COMMAND | Source: '{input_type}'{keys_str} | Gesture: '{gesture_str}' | "
            f"Mapped: '{routed_str}' [{domain_str} · {action_str}] | Mode: '{mode}' | "
            f"Outcome: {status} | Latency: {resp_ms_str}"
        )
        if reason:
            log_line += f" | Reason: {reason}"

        if status == "SUCCESS":
            self._logger.info(log_line)
        else:
            self._logger.warning(log_line)

        event_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "MANUAL_COMMAND",
            "input_type": input_type,
            "keys_pressed": keys_pressed or "",
            "gesture": gesture_str,
            "command": command,
            "routed_command": routed_str,
            "domain": domain_str,
            "action": action_str,
            "mode": mode,
            "status": status,
            "response_time_ms": response_time_ms,
            "reason": reason,
        }
        if extra:
            event_data["extra"] = extra

        self._record_event(event_data)
        return event_data

    def _record_event(self, event_data: dict[str, Any]) -> None:
        """Append event to memory buffer and write to JSONL file."""
        with self._lock:
            self._recent_events.append(event_data)
            try:
                with open(self.jsonl_log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event_data) + "\n")
            except Exception as exc:
                self._logger.debug(f"Failed to write to manual JSONL log file: {exc}")

    def get_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._recent_events)
        return events[-limit:] if limit > 0 else events

    def get_raw_log_lines(self, lines: int = 50) -> list[str]:
        if not os.path.exists(self.text_log_file):
            return []
        try:
            with open(self.text_log_file, "r", encoding="utf-8", errors="replace") as f:
                return list(deque(f, maxlen=lines))
        except Exception:
            return []

    def clear_logs(self) -> None:
        with self._lock:
            self._recent_events.clear()
            try:
                with open(self.text_log_file, "w", encoding="utf-8") as f:
                    f.write("")
                with open(self.jsonl_log_file, "w", encoding="utf-8") as f:
                    f.write("")
            except Exception:
                pass


manual_logger = ManualLoggerService()
