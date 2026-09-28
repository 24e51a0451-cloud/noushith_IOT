"""
log_parser.py
-------------
Tails MasterHub's runtime log file (services/logger_service.py writes it
in the format: "%(asctime)s | %(levelname)-8s | %(name)-22s | %(message)s")
and regex-extracts the specific lines each gesture request produces, e.g.:

    2026-08-03 12:54:21 | DEBUG    | masterhub.core.input_processor | Gesture 'pull' in mode 'MEDIA_MODE' -> command 'media_volume_down'
    2026-08-03 12:54:21 | DEBUG    | masterhub.core.router          | Routed: RouteResult(domain='ai_ml', action='volume_down', command='media_volume_down')
    2026-08-03 12:54:22 | INFO     | masterhub.core.engine          | Processed command 'media_volume_down' -> domain=ai_ml success=True

This module ONLY reads the log file. It never writes to it, and it never
touches any MasterHub source file.

Design note: the parser tracks a byte offset and only reads lines
appended AFTER it was created (see `prime()`), so re-running the suite
never re-parses old history, and a fresh LogParser only ever "sees" the
log lines produced by the test(s) that ran after it started reading.
"""

import os
import re


class LogParser:
    RE_GESTURE = re.compile(
        r"Gesture '(?P<gesture>[^']+)' in mode '(?P<mode>[^']+)' -> command '(?P<command>[^']+)'"
    )
    RE_ROUTED = re.compile(
        r"Routed: RouteResult\(domain='(?P<domain>[^']+)', action='(?P<action>[^']+)', command='(?P<command>[^']+)'\)"
    )
    RE_PROCESSED = re.compile(
        r"Processed command '(?P<command>[^']+)' -> domain=(?P<domain>\S+) success=(?P<success>True|False)"
    )
    RE_MODE_SWITCH = re.compile(r"Mode switch handled: (?P<command>\S+)")
    RE_TRANSITION = re.compile(r"State transition: (?P<from_mode>\S+) -> (?P<to_mode>\S+)")
    RE_UNKNOWN_REJECTED = re.compile(r"Engine rejected unknown command: '(?P<command>[^']+)'")
    RE_INPUT_FAIL = re.compile(r"Input normalization failed: (?P<detail>.+)")

    def __init__(self, log_path: str):
        self.log_path = log_path
        self._offset = self._current_size()
        self.file_found = os.path.exists(log_path)

    def _current_size(self) -> int:
        try:
            return os.path.getsize(self.log_path)
        except OSError:
            return 0

    def prime(self):
        """Reset the read offset to the current end of the log file."""
        self._offset = self._current_size()
        self.file_found = os.path.exists(self.log_path)

    def read_new_lines(self) -> list:
        """Return every line appended to the log file since the last read."""
        if not os.path.exists(self.log_path):
            self.file_found = False
            return []

        self.file_found = True
        size = self._current_size()
        if size < self._offset:
            # File was truncated or rotated externally — resume from start
            # rather than crash; better to over-read than silently miss data.
            self._offset = 0

        with open(self.log_path, "r", encoding="utf-8", errors="replace") as handle:
            handle.seek(self._offset)
            chunk = handle.read()
            self._offset = handle.tell()

        return [line for line in chunk.splitlines() if line.strip()]

    @staticmethod
    def _message_of(line: str) -> str:
        """
        Log lines are formatted "timestamp | LEVEL | logger.name | message".
        Split on the first three " | " separators and return just the
        message portion; regexes below match against that.
        """
        parts = line.split(" | ", 3)
        return parts[3].strip() if len(parts) == 4 else line

    def parse_chunk(self, lines: list) -> dict:
        """
        Parse a batch of newly-read log lines (expected to correspond to
        exactly one gesture request, since tests run sequentially) into a
        structured evidence dict. Later matching lines overwrite earlier
        ones of the same kind, so the LAST occurrence in the chunk wins.
        """
        evidence = {
            "gesture_line": None,
            "routed_line": None,
            "processed_line": None,
            "mode_switch_line": None,
            "transition_line": None,
            "unknown_line": None,
            "input_fail_line": None,
            "raw_lines": list(lines),
        }

        for line in lines:
            message = self._message_of(line)

            m = self.RE_GESTURE.search(message)
            if m:
                evidence["gesture_line"] = m.groupdict()

            m = self.RE_ROUTED.search(message)
            if m:
                evidence["routed_line"] = m.groupdict()

            m = self.RE_PROCESSED.search(message)
            if m:
                data = m.groupdict()
                data["success"] = data["success"] == "True"
                evidence["processed_line"] = data

            m = self.RE_MODE_SWITCH.search(message)
            if m:
                evidence["mode_switch_line"] = m.groupdict()

            m = self.RE_TRANSITION.search(message)
            if m:
                evidence["transition_line"] = m.groupdict()

            m = self.RE_UNKNOWN_REJECTED.search(message)
            if m:
                evidence["unknown_line"] = m.groupdict()

            m = self.RE_INPUT_FAIL.search(message)
            if m:
                evidence["input_fail_line"] = m.groupdict()

        return evidence
