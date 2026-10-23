"""
eeg_service.py
---------------
Placeholder/extensible service for future EEG -> gesture ML classification.

Today: accepts a raw EEG signal window (list of floats / channel data) and
returns a stubbed gesture label using a trivial heuristic, so the rest of
the pipeline (router/engine) can already be wired end-to-end.

Tomorrow: swap `_classify_stub` for a real model (e.g. load a trained
sklearn/torch model in __init__ and call model.predict() in classify()).
The public interface (classify) does not need to change.
"""

import random
from typing import List, Union

from services.logger_service import get_logger

log = get_logger("services.eeg")

GESTURE_LABELS = ["push", "pull", "left", "right", "lift", "drop", "neutral"]


class EEGService:
    def __init__(self, model_path: str = None):
        self.model_path = model_path
        self.model = None
        if model_path:
            self._load_model(model_path)

    def _load_model(self, model_path: str):
        """
        Hook for loading a real trained model later, e.g.:
            import joblib
            self.model = joblib.load(model_path)
        Left unimplemented intentionally — current pipeline runs in stub mode.
        """
        log.info(f"EEG model path provided ({model_path}) but no loader implemented yet; running in stub mode.")
        self.model = None

    def classify(self, signal_window: List[Union[float, List[float]]]) -> str:
        """
        Classify an EEG signal window into one of GESTURE_LABELS.

        Args:
            signal_window: raw EEG samples, e.g. [[ch1, ch2, ...], ...] or a flat list.

        Returns:
            A gesture label string.
        """
        if not signal_window:
            log.warning("Empty EEG signal window received, defaulting to 'neutral'")
            return "neutral"

        if self.model is not None:
            # Real model path (future):
            # return self.model.predict([signal_window])[0]
            pass

        return self._classify_stub(signal_window)

    def _classify_stub(self, signal_window) -> str:
        """
        Deterministic-ish stub: uses the average signal amplitude to pick a
        bucket, so behavior is at least reproducible for the same input
        rather than fully random. Replace with real inference later.
        """
        try:
            flat = self._flatten(signal_window)
            avg = sum(flat) / len(flat)
        except (TypeError, ZeroDivisionError):
            log.warning("Could not compute average for EEG window, defaulting to 'neutral'")
            return "neutral"

        bucket = int(abs(avg)) % len(GESTURE_LABELS)
        label = GESTURE_LABELS[bucket]
        log.debug(f"EEG stub classified window (avg={avg:.3f}) as '{label}'")
        return label

    @staticmethod
    def _flatten(window):
        flat = []
        for item in window:
            if isinstance(item, (list, tuple)):
                flat.extend(item)
            else:
                flat.append(item)
        return [float(x) for x in flat]


eeg_service = EEGService()
