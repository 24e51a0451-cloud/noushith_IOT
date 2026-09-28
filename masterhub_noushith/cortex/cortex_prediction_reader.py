"""
simulator/prediction_reader.py
-------------------------------
Loads emotiv_bci_predictions.json and reads predictions sequentially.

This module does exactly one job and nothing else: turn each raw JSON
record into a typed Prediction object (timestamp, gesture, confidence).
No filtering, no stabilization, no HTTP -- those are separate stages
downstream (confidence_filter.py, stabilizer.py, sender.py), matching
the pipeline architecture MasterHub itself uses (InputProcessor knows
nothing about routing, Router knows nothing about execution, etc.).

Phase 2 swap-in note:
    A future Cortex WebSocket client only needs to produce the same
    Prediction objects (via an equivalent `.read()` generator) for the
    rest of the pipeline -- confidence_filter, stabilizer, sender,
    replay -- to keep working unchanged.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator, Optional

from simulator.logger import get_logger

log = get_logger("prediction_reader")

# The recorded file uses this exact timestamp format, e.g.
# "2026-07-31 12:45:01.123"
_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


@dataclass(frozen=True)
class Prediction:
    """
    One raw prediction record, exactly as it will arrive from a future
    live Cortex stream: a timestamp, a predicted gesture, and the
    model's confidence in that prediction. No MasterHub-specific
    concepts (mode, domain, action) live on this object -- resolving
    the gesture into a concrete command is MasterHub's job via
    gesture_map.json, not the simulator's.
    """

    index: int
    timestamp: Optional[datetime]
    raw_timestamp: str
    gesture: str
    confidence: float
    raw: dict = field(repr=False, compare=False)


class PredictionReaderError(Exception):
    """Raised when the prediction file cannot be loaded or parsed."""


class PredictionReader:
    """
    Reads predictions sequentially from a JSON file.

    The file is expected to be a JSON array of objects shaped like:
        {"timestamp": "...", "command": "push", "confidence": 0.98}

    Note: the recorded field is named "command" in the JSON, but its
    values ("push", "pull", "left", "right", "lift", "drop", "neutral",
    ...) are raw predicted gestures, not resolved MasterHub commands --
    the same names used as keys in mappings/gesture_map.json. This
    reader exposes them as `Prediction.gesture` accordingly; letting
    MasterHub's own gesture_map.json + FSM resolve the actual command
    is what keeps this simulator behaving like a real Cortex client
    instead of duplicating MasterHub's gesture-resolution logic.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._records: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.file_path):
            log.error(f"Prediction file not found: {self.file_path}")
            raise PredictionReaderError(f"Prediction file not found: {self.file_path}")

        try:
            with open(self.file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            log.error(f"Prediction file is invalid JSON: {exc}")
            raise PredictionReaderError(f"Prediction file is invalid JSON: {exc}") from exc

        if not isinstance(data, list):
            log.error("Prediction file must contain a JSON array of records")
            raise PredictionReaderError("Prediction file must contain a JSON array of records")

        self._records = data
        log.info(f"Loaded {len(self._records)} predictions from {self.file_path}")

    def __len__(self) -> int:
        return len(self._records)

    @staticmethod
    def _parse_timestamp(raw_timestamp: str) -> Optional[datetime]:
        if not isinstance(raw_timestamp, str):
            return None
        try:
            return datetime.strptime(raw_timestamp, _TIMESTAMP_FORMAT)
        except ValueError:
            log.debug(f"Could not parse timestamp '{raw_timestamp}'; real-time replay will fall back to fixed delay for it")
            return None

    def read(self) -> Iterator[Prediction]:
        """
        Yield predictions in file order, one at a time. Pure read --
        no confidence filtering, no deduplication, no network calls.
        """
        for idx, record in enumerate(self._records, start=1):
            if not isinstance(record, dict):
                log.warning(f"Skipping record #{idx}: not a JSON object ({record!r})")
                continue

            raw_timestamp = record.get("timestamp", "")
            gesture = record.get("command")
            confidence = record.get("confidence")

            if not isinstance(gesture, str) or not gesture.strip():
                log.warning(f"Skipping record #{idx}: missing/invalid 'command' field")
                continue

            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                log.warning(f"Skipping record #{idx}: missing/invalid 'confidence' field")
                continue

            yield Prediction(
                index=idx,
                timestamp=self._parse_timestamp(raw_timestamp),
                raw_timestamp=raw_timestamp,
                gesture=gesture.strip().lower(),
                confidence=confidence,
                raw=record,
            )
