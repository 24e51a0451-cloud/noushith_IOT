"""
cortex/prediction_mapper.py
------------------------------
Converts a raw Cortex "com" (Mental Command) stream message into the
normalized prediction format already used by the rest of this project
(see emotiv_bci_predictions.json / simulator/prediction_reader.py):

    {"timestamp": "...", "command": "push", "confidence": 0.98}

Cortex sends mental command messages shaped like:

    {"com": ["push", 0.92], "time": 1690000000.123, "sid": "abc123"}

This module's only job is that translation -- it does not touch the
network, does not know about sessions/streams/auth, and does not call
MasterHub or the simulator. Whatever wires a live Cortex feed into
MasterHub later just needs to take the NormalizedPrediction objects
this module produces and hand them to the existing sender (e.g. by
constructing a simulator.prediction_reader.Prediction from the same
three fields) -- that integration glue is intentionally left out of
this module, per spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Optional

from cortex.logger import get_logger

log = get_logger("prediction_mapper")


@dataclass(frozen=True)
class NormalizedPrediction:
    """
    The output shape this module produces, matching the schema already
    used across the project (emotiv_bci_predictions.json,
    simulator/prediction_reader.py's Prediction.gesture/.confidence).
    """

    command: str
    confidence: float
    timestamp: str  # ISO 8601, e.g. "2026-08-03T12:45:10.123000+00:00"
    session_id: str = ""
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    def to_dict(self) -> dict:
        return {"command": self.command, "confidence": self.confidence, "timestamp": self.timestamp}


class PredictionMappingError(Exception):
    """Raised when a Cortex message can't be mapped to a NormalizedPrediction."""


def _cortex_time_to_iso(raw_time: Optional[float]) -> str:
    """
    Cortex's "time" field is a Unix timestamp in seconds (float,
    fractional = sub-second precision). Falls back to the current UTC
    time if the field is missing or malformed, so a prediction is never
    dropped purely for lacking a timestamp.
    """
    if raw_time is None:
        return datetime.now(timezone.utc).isoformat()
    try:
        return datetime.fromtimestamp(float(raw_time), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        log.debug(f"Could not parse Cortex 'time' value {raw_time!r}; using current UTC time instead")
        return datetime.now(timezone.utc).isoformat()


def map_mental_command(message: dict) -> NormalizedPrediction:
    """
    Convert one raw Cortex "com" stream message into a
    NormalizedPrediction. Raises PredictionMappingError if the message
    doesn't have the expected shape.

    Input example:
        {"com": ["push", 0.92], "time": 1690000000.123, "sid": "abc123"}

    Output:
        NormalizedPrediction(command="push", confidence=0.92, timestamp="...")
    """
    if not isinstance(message, dict) or "com" not in message:
        raise PredictionMappingError(f"Message has no 'com' field: {message!r}")

    com = message["com"]
    if not isinstance(com, (list, tuple)) or len(com) < 2:
        raise PredictionMappingError(f"'com' field has unexpected shape: {com!r}")

    command, confidence = com[0], com[1]
    if not isinstance(command, str) or not command.strip():
        raise PredictionMappingError(f"'com' action is not a valid string: {command!r}")

    try:
        confidence = float(confidence)
    except (TypeError, ValueError) as exc:
        raise PredictionMappingError(f"'com' power/confidence is not numeric: {confidence!r}") from exc

    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise PredictionMappingError('Mental command power must be finite and between 0 and 1')

    prediction = NormalizedPrediction(
        command=command.strip().lower(),
        confidence=confidence,
        timestamp=_cortex_time_to_iso(message.get("time")),
        session_id=message.get("sid", ""),
        raw=message,
    )
    log.debug(f"Mapped Cortex message -> {prediction.to_dict()}")
    return prediction
