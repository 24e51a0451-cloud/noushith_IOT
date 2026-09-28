"""App-owned Cortex stream worker.

Publishes mental-command samples and passes deliberate gestures to the shared
MasterHub engine through CortexControl. The standalone entry point monitors
only; use the Flask console to enable control in the app process.
"""

from __future__ import annotations

import queue
import signal
import sys
import threading
import time
from typing import Optional

from flask import session

from cortex import dashboard
from cortex.auth import AuthCredentials, CortexAuth, CortexAuthError
from cortex.config import STREAM_NAME
from cortex.cortex_client import CortexClient, CortexConnectionError, CortexRequestError
from cortex.headset import HeadsetError, HeadsetInfo, HeadsetManager
from cortex.logger import get_logger
from cortex.prediction_mapper import PredictionMappingError, map_mental_command
from cortex.profile import ProfileManager
from cortex.session import SessionError, SessionManager
from cortex.stream import StreamError, StreamManager
from prediction_pipeline import PredictionPipeline
from services.bci_logger_service import bci_logger

log = get_logger("run_live")

_raw_message_queue: "queue.Queue[dict]" = queue.Queue(maxsize=1)
_shutdown = threading.Event()


def _receive_prediction(raw: dict) -> None:
    """Publish immediately, independent of potentially slow command execution."""
    try:
        prediction = map_mental_command(raw)
    except PredictionMappingError:
        return
    dashboard.update_prediction(gesture=prediction.command, confidence=prediction.confidence)
    try:
        _raw_message_queue.get_nowait()
    except queue.Empty:
        pass
    if dashboard.control_enabled():
        try:
            _raw_message_queue.put_nowait(dict(raw, _received_monotonic=time.monotonic()))
        except queue.Full:
            pass


class LiveRunner:
    """
    Owns one full Cortex connection lifecycle: client, auth, headset,
    session, and stream. Exposes `start()` / `stop()` and knows how to
    re-establish auth/session/subscription after a reconnect (the raw
    WebSocket reconnect itself is handled inside CortexClient).
    """

    def __init__(self):
        self.stop_event = threading.Event()
        self._reconnect_requested = threading.Event()
        self.client = CortexClient(auto_reconnect=False)
        self.client.on("warning", self._on_warning)
        self.auth = CortexAuth(self.client)
        self.headsets = HeadsetManager(self.client)
        self.sessions = SessionManager(self.client)
        self.profiles = ProfileManager(self.client)
        self.streams = StreamManager(self.client)
        from cortex.control import cortex_control
        self.pipeline = cortex_control

        self.headset_info: Optional[HeadsetInfo] = None
        self._profile_checked_at = 0.0


    def start(self) -> None:
        log.info("Starting Cortex live runner")
        self._connect_with_retry()
    
    def run_forever(self, stop_event: threading.Event) -> None:
        log.info("Cortex prediction processing loop started")

        while not stop_event.is_set():
            if not self.client.connected or self._reconnect_requested.is_set() or self.auth._is_token_stale():
                self.pipeline.reset()
                self.pipeline.stop_motion()
                self._connect_with_retry(retry_delay=2.0)
                continue
            if time.monotonic() - self._profile_checked_at >= 2.0:
                self._refresh_profile()
            try:
                raw_message = _raw_message_queue.get(timeout=0.5)
            except queue.Empty:
                if not dashboard.control_enabled():
                    self.pipeline.reset()
                    self.pipeline.stop_motion()
                continue

            try:
                if time.monotonic() - raw_message.get("_received_monotonic", 0) > 1:
                    continue
                prediction = map_mental_command(raw_message)
            except PredictionMappingError as exc:
                log.warning(
                    f"Skipping unmappable Cortex message: {exc}"
                )
                continue

            try:
                _process_prediction(
                    prediction,
                    self.pipeline,
                    publish=False,
                )
            except Exception:
                log.exception(
                    "Error processing Cortex prediction"
                )

        log.info("Cortex prediction processing loop stopped")






    def _connect_with_retry(self, retry_delay: float = 5.0) -> None:
        attempt = 0
        stop_event = getattr(self, "stop_event", threading.Event())
        while not stop_event.is_set():
            attempt += 1
            try:
                dashboard.update_status(connected=False, authorized=False, retry_attempt=attempt, last_error="Connecting...")
                self._reconnect_requested.clear()
                self.client.close()
                self.streams.reset()
                self.auth.clear_token()
                from cortex.config import reload_credentials
                client_id, secret, license_key, url = reload_credentials()
                self.auth.credentials = AuthCredentials(client_id, secret, license_key)
                self.client.url = url
                self.client.connect()
                if stop_event.is_set():
                    self.client.close()
                    return
                dashboard.update_status(connected=True, authorized=False, retry_attempt=attempt, last_error="")
                self._authenticate_and_prepare()
                if stop_event.is_set():
                    self.client.close()
                    return
                if self._reconnect_requested.is_set():
                    continue
                dashboard.update_status(connected=True, authorized=True, retry_attempt=attempt, last_error="")
                log.info("Cortex live runner fully connected and streaming predictions")
                return
            except (CortexConnectionError, CortexAuthError, HeadsetError, SessionError, StreamError, CortexRequestError) as exc:
                log.warning(f"Cortex unavailable: {exc}")
                dashboard.update_status(
                    connected=False,
                    authorized=False,
                    retry_attempt=attempt,
                    last_error=str(exc),
                )
                try:
                    self.client.close()
                except Exception:
                    log.debug("Ignoring close error while retrying Cortex startup", exc_info=True)
                stop_event.wait(retry_delay)

    
    def stop(self) -> None:
        self.stop_event.set()
        log.info("Stopping Cortex live runner")
        dashboard.update_status(connected=False, authorized=False)
        self.pipeline.reset()
        self.pipeline.stop_motion()

        token = self.auth.token
        session = self.sessions.current

        if self.client.connected and token and session:
            try:
                self.streams.unsubscribe(
                    token,
                    session.id,
                    [STREAM_NAME],
                )
            except Exception:
                log.debug(
                    "Failed to unsubscribe during shutdown",
                    exc_info=True,
                )

            try:
                self.sessions.close_session(
                    token,
                    session.id,
                )
            except Exception:
                log.debug(
                    "Failed to close Cortex session during shutdown",
                    exc_info=True,
                )

        if self.headset_info and self.client.connected:
            try:
                self.headsets.disconnect(
                    self.headset_info.id
                )
            except Exception:
                log.debug(
                    "Failed to disconnect headset during shutdown",
                    exc_info=True,
                )

        self.client.close()

        dashboard.update_status(
            connected=False,
            authorized=False,
        )

        dashboard.update_session(
            status="closed"
        )

        log.info("Cortex live runner stopped")
    # ------------------------------------------------------------------
    # Internal: the auth -> headset -> session -> subscribe pipeline,
    # reused both on first start and after every reconnect.
    # ------------------------------------------------------------------

    def _authenticate_and_prepare(self) -> None:
        token = self.auth.login_and_authorize(force=True)
        dashboard.update_status(authorized=True)

        self.headset_info = self.headsets.ensure_connected(
            self.headset_info.id if self.headset_info else None
        )
        dashboard.update_headset(headset_id=self.headset_info.id, status=self.headset_info.status)

        # One session is created here and reused for both the device
        # diagnostics check and the mental-command subscription that
        # follows -- Cortex sessions are per-headset-per-token, so
        # there is no need (and no benefit) to create a second one.
        session = self.sessions.create_session(token, self.headset_info.id, activate=True)
        dashboard.update_session(session_id=session.id, status=session.status, headset_id=self.headset_info.id)

        bat_pct = None
        sig_qual = None
        try:
            diagnostics = self.headsets.read_device_diagnostics(token, session.id, self.headset_info.id)
            bat_pct = diagnostics.battery_percent
            sig_qual = diagnostics.signal_quality
            dashboard.update_headset(
                battery_percent=diagnostics.battery_percent, signal_quality=diagnostics.signal_quality
            )
            log.info(
                f"Headset '{self.headset_info.id}': battery={diagnostics.battery_percent}% "
                f"signal_quality={diagnostics.signal_quality}"
            )
        except HeadsetError as exc:
            log.warning(f"Could not read device diagnostics (continuing anyway): {exc}")

        # Store headset connection in persistent BCI log file
        try:
            bci_logger.log_headset_connected(
                headset_id=self.headset_info.id,
                session_id=session.id,
                battery=bat_pct,
                signal=sig_qual,
                firmware=getattr(self.headset_info, "firmware", ""),
            )
        except Exception as bci_err:
            log.debug(f"Could not log headset connection to BCI log: {bci_err}")

        self.streams.reset()
        self.streams.subscribe_mental_commands(token, session.id, on_prediction_raw=_receive_prediction)
        self._refresh_profile(discover=True)
        log.info(f"Subscribed to '{STREAM_NAME}' stream; waiting for live predictions...")

    def _refresh_profile(self, *, discover=False):
        """Track profiles loaded in EMOTIV after MasterHub connected."""
        if not self.headset_info or not self.auth.token:
            return
        token = self.auth.token
        # Current-profile detection must still run when listing profiles fails.
        available = None
        if discover:
            try:
                available = self.profiles.query_profiles(token)
                dashboard.update_profile(available=available)
            except Exception as exc:
                log.warning('Could not list profiles: %s', exc)
        try:
            current = self.profiles.get_current_profile(token, self.headset_info.id)
            if discover and not current:
                from cortex.config import _ENV_FILE
                from dotenv import dotenv_values
                import os
                selected = dotenv_values(_ENV_FILE, interpolate=False).get('CORTEX_PROFILE') or os.getenv('CORTEX_PROFILE')
                if selected and available and selected in available:
                    self.profiles.load_profile(token, self.headset_info.id, selected)
                    current = self.profiles.get_current_profile(token, self.headset_info.id)
            dashboard.update_profile(current=current or '')
        except Exception as exc:
            dashboard.update_profile(current='')
            log.warning('Could not prepare trained profile: %s', exc)
        finally:
            self._profile_checked_at = time.monotonic()

    def request_reconnect(self) -> None:
        """Wake the single connection owner without starting another worker."""
        self._reconnect_requested.set()
        dashboard.update_status(connected=False, authorized=False, last_error="Recovering connection")

    def _on_warning(self, message: dict) -> None:
        # Cortex can cancel streams while its WebSocket stays connected.
        if message.get("warning", {}).get("code") in (0, 1, 3):
            self.request_reconnect()


def _process_prediction(prediction, pipeline: PredictionPipeline, *, publish: bool = True) -> None:
    gesture_name = getattr(prediction, "command", "") or getattr(prediction, "gesture", "") or "neutral"
    confidence_val = getattr(prediction, "confidence", 0.0) or 0.0
    session_id = getattr(prediction, "session_id", "") or ""
    if publish:
        dashboard.update_prediction(gesture=gesture_name, confidence=confidence_val)

    if not dashboard.control_enabled():
        return

    # Resting baseline state does not trigger command execution
    if gesture_name == "neutral" and not getattr(pipeline, 'accepts_neutral', False):
        return

    log.debug(f"[BCI SAMPLE] gesture='{gesture_name}' power={confidence_val:.3f}")
    previous_message = getattr(pipeline, 'message', None)
    result = pipeline.process(prediction)
    if result.send_result is None and getattr(pipeline, 'message', None) != previous_message:
        dashboard.report_control_feedback('WAITING', pipeline.message, gesture_name, confidence_val)

    if result.filter_result is not None and not result.filter_result.accepted:
        log.info(f"🧠 [BCI FILTERED] Gesture '{gesture_name}' confidence {confidence_val:.2f} below threshold")
        dashboard.update_pipeline_result(rejected=True)
        try:
            bci_logger.log_bci_command(
                gesture=gesture_name,
                confidence=confidence_val,
                accepted=False,
                reason="below_confidence_threshold",
                status="FILTERED",
                session_id=session_id,
            )
        except Exception:
            pass
    elif result.stabilizer_result is not None and not result.stabilizer_result.accepted:
        log.info(f"🧠 [BCI STABILIZED] Duplicate gesture '{gesture_name}' within cooldown ignored")
        dashboard.update_pipeline_result(duplicate=True)
        try:
            bci_logger.log_bci_command(
                gesture=gesture_name,
                confidence=confidence_val,
                accepted=False,
                reason="duplicate_within_cooldown",
                status="STABILIZED",
                session_id=session_id,
            )
        except Exception:
            pass
    elif result.send_result is not None:
        body = result.send_result.response_body
        gesture_name = body.get('gesture', gesture_name)
        confidence_val = body.get('power', confidence_val)
        cmd = result.send_result.resolved_command or gesture_name
        dom = result.send_result.domain or "system"
        dur = result.send_result.response_time_ms
        log.info(f"🧠 [BCI DISPATCHED] '{gesture_name}' -> '{cmd}' [{dom}] · Status {result.send_result.http_status} ({dur:.1f}ms)")
        dashboard.update_pipeline_result(
            accepted=True,
            commands_sent=result.send_result.success,
            mode=result.send_result.mode,
            routed_command=cmd,
            domain=dom,
            http_status=result.send_result.http_status,
            response_time_ms=dur,
            gesture=gesture_name,
            power=confidence_val,
            error=body.get('error') or result.send_result.error,
        )
        try:
            bci_logger.log_bci_command(
                gesture=gesture_name,
                confidence=confidence_val,
                accepted=True,
                routed_command=cmd,
                domain=dom,
                action=result.send_result.action or cmd,
                status="SUCCESS" if result.send_result.success else "FAILED",
                response_time_ms=dur,
                session_id=session_id,
            )
        except Exception:
            pass


def main() -> int:
    runner = LiveRunner()
    runner.stop_event = _shutdown

    def _handle_sigint(_signum, _frame):
        log.info("Shutdown signal received")
        _shutdown.set()

    signal.signal(signal.SIGINT, _handle_sigint)

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_sigint)

    try:
        runner.start()

        print(
            "Connected. Streaming live mental-command predictions "
            "(Ctrl+C to stop)...\n"
        )

        runner.run_forever(_shutdown)

    except (
        CortexConnectionError,
        CortexAuthError,
        HeadsetError,
        SessionError,
        StreamError,
        CortexRequestError,
    ) as exc:
        log.error(f"Failed to start Cortex live runner: {exc}")

        dashboard.update_status(
            connected=False,
            authorized=False,
            last_error=str(exc),
        )

        print(
            f"Failed to start: {exc}",
            file=sys.stderr,
        )

        return 1

    except KeyboardInterrupt:
        log.info("Keyboard interrupt received")

    finally:
        runner.stop()

    return 0

if __name__ == "__main__":
    sys.exit(main())
