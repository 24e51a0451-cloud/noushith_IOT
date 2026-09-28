from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

from services.logger_service import get_logger
from simulator.config import (
    COMMAND_URL,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_STABILIZER_COOLDOWN_MS,
    FORWARD_CONFIDENCE_TO_ENGINE,
    PREDICTION_SOURCE,
    REQUEST_MAX_RETRIES,
    REQUEST_RETRY_BACKOFF_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
)
from simulator.prediction_reader import Prediction

log = get_logger("prediction_pipeline")

_PIPELINE_LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "prediction_pipeline.log",
)
os.makedirs(os.path.dirname(_PIPELINE_LOG_FILE), exist_ok=True)


def _configure_pipeline_logger() -> logging.Logger:
    logger = logging.getLogger("masterhub.prediction_pipeline")
    if getattr(logger, "_pipeline_file_handler_configured", False):
        return logger

    handler = logging.FileHandler(_PIPELINE_LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = True
    logger._pipeline_file_handler_configured = True
    return logger


pipeline_log = _configure_pipeline_logger()


@dataclass
class FilterResult:
    accepted: bool
    prediction: Prediction
    threshold: float
    reason: str = ""


@dataclass
class StabilizerResult:
    accepted: bool
    prediction: Prediction
    reason: str = ""


@dataclass
class SendResult:
    prediction: Prediction
    success: bool
    http_status: Optional[int]
    response_time_ms: float
    response_body: dict = field(default_factory=dict)
    error: str = ""

    @property
    def domain(self) -> str:
        return self.response_body.get("domain", "") if self.response_body else ""

    @property
    def action(self) -> str:
        return self.response_body.get("action", "") if self.response_body else ""

    @property
    def resolved_command(self) -> str:
        return self.response_body.get("command", "") if self.response_body else ""

    @property
    def mode(self) -> str:
        state = self.response_body.get("state") if self.response_body else None
        return state.get("mode", "") if isinstance(state, dict) else ""


class ConfidenceFilter:
    @staticmethod
    def _prediction_gesture(prediction: Prediction) -> str:
        return getattr(prediction, "gesture", None) or getattr(prediction, "command", "") or ""

    def __init__(self, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be between 0.0 and 1.0, got {threshold}")
        self.threshold = threshold
        log.info(f"Confidence filter initialized with threshold={self.threshold}")

    def evaluate(self, prediction: Prediction) -> FilterResult:
        gesture = self._prediction_gesture(prediction)
        if prediction.confidence < self.threshold:
            log.info(
                f"#{getattr(prediction, 'index', '?')} REJECTED (confidence {prediction.confidence:.2f} "
                f"< threshold {self.threshold:.2f}) gesture='{gesture}'"
            )
            return FilterResult(
                accepted=False,
                prediction=prediction,
                threshold=self.threshold,
                reason="below_confidence_threshold",
            )

        log.debug(
            f"#{getattr(prediction, 'index', '?')} ACCEPTED (confidence {prediction.confidence:.2f} "
            f">= threshold {self.threshold:.2f}) gesture='{gesture}'"
        )
        return FilterResult(accepted=True, prediction=prediction, threshold=self.threshold)


class GestureStabilizer:
    @staticmethod
    def _prediction_gesture(prediction: Prediction) -> str:
        return getattr(prediction, "gesture", None) or getattr(prediction, "command", "") or ""

    def __init__(self, cooldown_ms: int = DEFAULT_STABILIZER_COOLDOWN_MS):
        if cooldown_ms < 0:
            raise ValueError(f"cooldown_ms must be >= 0, got {cooldown_ms}")
        self.cooldown_ms = cooldown_ms
        self._last_sent_gesture: Optional[str] = None
        self._last_sent_at: Optional[float] = None

    def reset(self) -> None:
        self._last_sent_gesture = None
        self._last_sent_at = None

    def evaluate(self, prediction: Prediction, now: Optional[float] = None) -> StabilizerResult:
        now = time.monotonic() if now is None else now
        gesture = self._prediction_gesture(prediction)

        is_repeat = (
            self._last_sent_gesture == gesture
            and self._last_sent_at is not None
            and (now - self._last_sent_at) * 1000.0 < self.cooldown_ms
        )

        if is_repeat:
            elapsed_ms = (now - self._last_sent_at) * 1000.0
            log.debug(
                f"#{getattr(prediction, 'index', '?')} SUPPRESSED duplicate gesture='{gesture}' "
                f"({elapsed_ms:.0f}ms < {self.cooldown_ms}ms cooldown)"
            )
            return StabilizerResult(accepted=False, prediction=prediction, reason="duplicate_within_cooldown")

        self._last_sent_gesture = gesture
        self._last_sent_at = now
        log.debug(f"#{getattr(prediction, 'index', '?')} STABILIZED gesture='{gesture}' -> will send")
        return StabilizerResult(accepted=True, prediction=prediction)


class CommandSender:
    @staticmethod
    def _prediction_gesture(prediction: Prediction) -> str:
        return getattr(prediction, "gesture", None) or getattr(prediction, "command", "") or ""

    def __init__(
        self,
        url: str = COMMAND_URL,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        max_retries: int = REQUEST_MAX_RETRIES,
        retry_backoff: float = REQUEST_RETRY_BACKOFF_SECONDS,
        session: Optional[requests.Session] = None,
    ):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._session = session or requests.Session()
        log.info(f"Sender configured for {self.url}")

    def send(self, prediction: Prediction, gesture_override: Optional[str] = None) -> SendResult:
        gesture = gesture_override or self._prediction_gesture(prediction)
        body: dict[str, Any] = {"gesture": gesture}
        if FORWARD_CONFIDENCE_TO_ENGINE:
            body["params"] = {
                "confidence": prediction.confidence,
                "confidence_threshold": getattr(self, "threshold", DEFAULT_CONFIDENCE_THRESHOLD),
                "source": PREDICTION_SOURCE,
            }

        attempt = 0
        last_error = ""
        while attempt <= self.max_retries:
            attempt += 1
            start = time.perf_counter()
            try:
                response = self._session.post(self.url, json=body, timeout=self.timeout)
                elapsed_ms = (time.perf_counter() - start) * 1000.0

                try:
                    payload = response.json()
                except ValueError:
                    payload = {}

                success = response.ok and bool(payload.get("success", response.ok))
                log.info(
                    f"#{getattr(prediction, 'index', '?')} SENT gesture='{gesture}' "
                    f"-> HTTP {response.status_code} success={success} "
                    f"({elapsed_ms:.1f}ms)"
                )
                return SendResult(
                    prediction=prediction,
                    success=success,
                    http_status=response.status_code,
                    response_time_ms=elapsed_ms,
                    response_body=payload,
                )

            except requests.exceptions.RequestException as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                last_error = str(exc)
                log.warning(
                    f"#{getattr(prediction, 'index', '?')} SEND FAILED (attempt {attempt}/{self.max_retries + 1}) "
                    f"gesture='{gesture}': {last_error}"
                )
                if attempt <= self.max_retries:
                    time.sleep(self.retry_backoff)

        return SendResult(
            prediction=prediction,
            success=False,
            http_status=None,
            response_time_ms=elapsed_ms,
            error=last_error or "Unknown request failure",
        )


@dataclass
class PipelineResult:
    accepted: bool
    prediction: Prediction
    filter_result: Optional[FilterResult] = None
    stabilizer_result: Optional[StabilizerResult] = None
    send_result: Optional[SendResult] = None
    reason: str = ""


class PredictionPipeline:
    def __init__(
        self,
        threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        cooldown_ms: int = DEFAULT_STABILIZER_COOLDOWN_MS,
        url: str = COMMAND_URL,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        max_retries: int = REQUEST_MAX_RETRIES,
        retry_backoff: float = REQUEST_RETRY_BACKOFF_SECONDS,
        session: Optional[requests.Session] = None,
    ):
        self.confidence_filter = ConfidenceFilter(threshold=threshold)
        self.stabilizer = GestureStabilizer(cooldown_ms=cooldown_ms)
        self.sender = CommandSender(
            url=url,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            session=session,
        )

    def process(self, prediction: Prediction) -> PipelineResult:
        gesture = getattr(prediction, "gesture", None) or getattr(prediction, "command", "") or ""
        index = getattr(prediction, "index", "?")
        pipeline_log.info("Prediction received: index=%s gesture='%s' confidence=%.4f", index, gesture, getattr(prediction, "confidence", 0.0))

        filter_result = self.confidence_filter.evaluate(prediction)
        if not filter_result.accepted:
            pipeline_log.info(
                "Confidence rejected: index=%s gesture='%s' confidence=%.4f threshold=%.4f reason=%s",
                index,
                gesture,
                getattr(prediction, "confidence", 0.0),
                filter_result.threshold,
                filter_result.reason or "below_confidence_threshold",
            )
            pipeline_log.info("Completed: index=%s gesture='%s' accepted=False reason=%s", index, gesture, filter_result.reason)
            return PipelineResult(
                accepted=False,
                prediction=prediction,
                filter_result=filter_result,
                reason=filter_result.reason,
            )

        pipeline_log.info(
            "Confidence accepted: index=%s gesture='%s' confidence=%.4f threshold=%.4f",
            index,
            gesture,
            getattr(prediction, "confidence", 0.0),
            filter_result.threshold,
        )

        stabilizer_result = self.stabilizer.evaluate(prediction)
        if not stabilizer_result.accepted:
            pipeline_log.info(
                "Gesture stabilized: index=%s gesture='%s' accepted=False reason=%s",
                index,
                gesture,
                stabilizer_result.reason or "duplicate_within_cooldown",
            )
            pipeline_log.info("Completed: index=%s gesture='%s' accepted=False reason=%s", index, gesture, stabilizer_result.reason)
            return PipelineResult(
                accepted=False,
                prediction=prediction,
                filter_result=filter_result,
                stabilizer_result=stabilizer_result,
                reason=stabilizer_result.reason,
            )

        pipeline_log.info("Gesture stabilized: index=%s gesture='%s' accepted=True", index, gesture)
        pipeline_log.info("Command sent: index=%s gesture='%s'", index, gesture)

        send_result = self.sender.send(prediction)
        pipeline_log.info(
            "HTTP response: index=%s gesture='%s' status=%s success=%s elapsed_ms=%.2f",
            index,
            gesture,
            send_result.http_status,
            send_result.success,
            send_result.response_time_ms,
        )
        pipeline_log.info(
            "Completed: index=%s gesture='%s' accepted=%s reason=%s",
            index,
            gesture,
            send_result.success,
            "" if send_result.success else "send_failed",
        )
        return PipelineResult(
            accepted=send_result.success,
            prediction=prediction,
            filter_result=filter_result,
            stabilizer_result=stabilizer_result,
            send_result=send_result,
            reason="" if send_result.success else "send_failed",
        )
