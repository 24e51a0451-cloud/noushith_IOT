"""
services/bci_logger_service.py
------------------------------
Dedicated logging and persistent recording service for Emotiv Cortex BCI
mental commands, headset lifecycle events, confidence metrics, and
command routing outcomes.

Outputs:
    - logs/bci_commands.log   (Human-readable rotating text log)
    - logs/bci_commands.jsonl (Structured JSON-lines log for analysis & replay)
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

BCI_TEXT_LOG_FILE = os.path.join(_LOG_DIR, "bci_commands.log")
BCI_JSONL_LOG_FILE = os.path.join(_LOG_DIR, "bci_commands.jsonl")

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class BciLoggerService:
    def __init__(
        self,
        text_log_file: str = BCI_TEXT_LOG_FILE,
        jsonl_log_file: str = BCI_JSONL_LOG_FILE,
        max_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 5,
    ):
        self.text_log_file = text_log_file
        self.jsonl_log_file = jsonl_log_file
        self._lock = threading.Lock()
        self._recent_events: deque[dict] = deque(maxlen=500)
        self._active_headset_id = ""
        self._active_session_id = ""

        # Configure dedicated logger
        self._logger = logging.getLogger("masterhub.bci_commands")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        if not getattr(self._logger, "_bci_handler_configured", False):
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
            self._logger._bci_handler_configured = True

    def set_active_session(self, headset_id: str, session_id: str) -> None:
        with self._lock:
            self._active_headset_id = headset_id
            self._active_session_id = session_id

    def log_headset_connected(
        self,
        headset_id: str,
        session_id: str,
        battery: Optional[float] = None,
        signal: Optional[float] = None,
        firmware: str = "",
    ) -> None:
        """Record headset connection and session start event."""
        with self._lock:
            self._active_headset_id = headset_id
            self._active_session_id = session_id

        bat_str = f"{battery}%" if battery is not None else "N/A"
        sig_str = f"{signal}" if signal is not None else "N/A"
        msg = (
            f"HEADSET_CONNECTED | Headset: '{headset_id}' | Session: '{session_id}' | "
            f"Battery: {bat_str} | Signal Quality: {sig_str} | Stream: 'com' (Mental Commands)"
        )
        self._logger.info(msg)

        event_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "HEADSET_CONNECTED",
            "headset_id": headset_id,
            "session_id": session_id,
            "battery_percent": battery,
            "signal_quality": signal,
            "firmware": firmware,
        }
        self._record_event(event_data)

    def log_headset_disconnected(self, headset_id: str, reason: str = "Service stopped") -> None:
        """Record headset disconnect event."""
        msg = f"HEADSET_DISCONNECTED | Headset: '{headset_id}' | Reason: {reason}"
        self._logger.info(msg)

        event_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "HEADSET_DISCONNECTED",
            "headset_id": headset_id,
            "reason": reason,
        }
        self._record_event(event_data)

    def log_bci_command(
        self,
        gesture: str,
        confidence: float,
        accepted: bool = True,
        routed_command: Optional[str] = None,
        domain: Optional[str] = None,
        action: Optional[str] = None,
        status: str = "SUCCESS",
        response_time_ms: Optional[float] = None,
        reason: str = "",
        headset_id: Optional[str] = None,
        session_id: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Record an incoming BCI mental command, confidence evaluation,
        routing translation, and execution outcome to both log files.
        """
        hs_id = headset_id or self._active_headset_id or "EPOC_X"
        s_id = session_id or self._active_session_id or ""
        conf_pct = f"{confidence * 100:.1f}%" if confidence <= 1.0 else f"{confidence:.1f}%"
        resp_ms_str = f"{response_time_ms:.1f}ms" if response_time_ms is not None else "—"

        status_tag = status.upper()
        if not accepted:
            status_tag = "REJECTED" if "threshold" in reason else "STABILIZED"

        routed_str = routed_command or gesture
        domain_str = domain or "system"
        action_str = action or routed_str

        log_line = (
            f"MENTAL_COMMAND | Headset: '{hs_id}' | Gesture: '{gesture}' ({conf_pct}) | "
            f"Outcome: {status_tag} | Mapped: '{routed_str}' [{domain_str} · {action_str}] | "
            f"Latency: {resp_ms_str}"
        )
        if reason:
            log_line += f" | Reason: {reason}"

        if accepted and status == "SUCCESS":
            self._logger.info(log_line)
        elif not accepted:
            self._logger.warning(log_line)
        else:
            self._logger.error(log_line)

        event_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "MENTAL_COMMAND",
            "headset_id": hs_id,
            "session_id": s_id,
            "gesture": gesture,
            "confidence": confidence,
            "confidence_percent": conf_pct,
            "accepted": accepted,
            "routed_command": routed_str,
            "domain": domain_str,
            "action": action_str,
            "status": status_tag,
            "response_time_ms": response_time_ms,
            "reason": reason,
        }
        if extra:
            event_data["extra"] = extra

        self._record_event(event_data)
        return event_data

    def _record_event(self, event_data: dict[str, Any]) -> None:
        """Append event to in-memory buffer and write to JSONL log file."""
        with self._lock:
            self._recent_events.append(event_data)

            # Append to JSON-lines log file
            try:
                with open(self.jsonl_log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event_data) + "\n")
            except Exception as exc:
                self._logger.debug(f"Failed to write to JSONL log file: {exc}")

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


bci_logger = BciLoggerService()
