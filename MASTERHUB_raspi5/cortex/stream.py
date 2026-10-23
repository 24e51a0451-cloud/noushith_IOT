"""
cortex/stream.py
------------------
Manages subscribing to Cortex data streams for an active session.

Phase 1 only needs the Mental Command stream ("com"), but this module
is deliberately built around a small registry (`SUPPORTED_STREAMS`) and
generic subscribe/unsubscribe/callback methods so that adding EEG
("eeg"), Motion ("mot"), Facial Expression ("fac"), Performance Metrics
("met"), or any other Cortex stream later is just:

    1. Add its name to SUPPORTED_STREAMS below.
    2. Call stream_manager.subscribe(["eeg"], on_eeg_data) somewhere.

No changes to cortex_client.py, session.py, or this file's existing
methods are required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from cortex.cortex_client import CortexClient, CortexRequestError
from cortex.logger import get_logger

log = get_logger("stream")

# Cortex stream names this module is known to work with. Adding a new
# stream later only requires adding its name here (plus a mapper for
# its payload shape, analogous to prediction_mapper.py for "com") --
# the subscribe/unsubscribe plumbing below already handles any of them.
SUPPORTED_STREAMS = {
    "com": "Mental Command (facial/cognitive action predictions)",
    "eeg": "Raw EEG (requires an appropriate license)",
    "mot": "Motion sensor data (gyro/accelerometer/magnetometer)",
    "fac": "Facial expression detections",
    "met": "Performance metrics (stress, focus, engagement, ...)",
    "dev": "Device/contact-quality info (battery, signal quality)",
    "pow": "Band power (theta/alpha/lowBeta/highBeta/gamma per channel)",
    "eq": "EEG channel contact quality",
}


@dataclass
class SubscriptionResult:
    stream_name: str
    success: bool
    sid: str = ""
    message: str = ""


class StreamError(Exception):
    """Raised when subscribing to or unsubscribing from a stream fails."""


class StreamManager:
    def __init__(self, client: CortexClient):
        self.client = client
        self._active_streams: set[str] = set()
        self._callbacks: dict[str, Callable[[dict], None]] = {} # new: store callbacks for each stream

    @property
    def active_streams(self) -> set[str]:
        return set(self._active_streams)

    def subscribe(
        self,
        cortex_token: str,
        session_id: str,
        streams: list[str],
        on_data: Optional[Callable[[dict], None]] = None,
    ) -> list[SubscriptionResult]:
        """
        Subscribe to one or more Cortex streams on an active session.
        If `on_data` is given, it is registered against every stream
        name in `streams` via the client's generic event dispatch (see
        cortex_client.CortexClient.on), so it will be invoked for every
        raw message Cortex sends on any of those streams.
        """
        unknown = [s for s in streams if s not in SUPPORTED_STREAMS]
        if unknown:
            log.warning(f"Subscribing to stream(s) not in SUPPORTED_STREAMS registry: {unknown} (will still attempt it)")

        try:
            result = self.client.call(
                "subscribe",
                {"cortexToken": cortex_token, "session": session_id, "streams": streams},
            )
        except CortexRequestError as exc:
            log.error(f"subscribe({streams}) failed: {exc}")
            raise StreamError(f"subscribe({streams}) failed: {exc}") from exc

        results = self._parse_subscription_result(result, streams)
        for res in results:
            if res.success:
                self._active_streams.add(res.stream_name)
                if on_data is not None:
                    self._register_callback(res.stream_name, on_data) # new: register callback for this stream
                
                log.info(f"Subscribed to stream '{res.stream_name}' (sid={res.sid})")
            else:
                log.error(f"Failed to subscribe to stream '{res.stream_name}': {res.message}")

        return results

    def unsubscribe(self, cortex_token: str, session_id: str, streams: list[str]) -> None:
        try:
            self.client.call(
                "unsubscribe",
                {"cortexToken": cortex_token, "session": session_id, "streams": streams},
            )
            for stream_name in streams:
                self._active_streams.discard(stream_name)
                self._remove_callback(stream_name) # new: remove callback for this stream
            log.info(f"Unsubscribed from stream(s): {streams}")
        except CortexRequestError as exc:
            log.warning(f"unsubscribe({streams}) reported an error (may already be unsubscribed): {exc}")

    def subscribe_mental_commands(
        self, cortex_token: str, session_id: str, on_prediction_raw: Callable[[dict], None]
    ) -> SubscriptionResult:
        """
        Convenience wrapper for the one stream Phase 1 actually needs:
        subscribes to "com" and registers `on_prediction_raw` to receive
        every raw {"com": [label, power], "time": ..., "sid": ...}
        message. Callers typically pass the raw message straight into
        prediction_mapper.map_mental_command().
        """
        results = self.subscribe(cortex_token, session_id, ["com"], on_data=on_prediction_raw)
        return results[0] if results else SubscriptionResult(stream_name="com", success=False, message="No result returned")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_subscription_result(result, requested_streams: list[str]) -> list[SubscriptionResult]:
        """
        Cortex's "subscribe" response shape is:
            {"success": [{"streamName": "com", "sid": "..."}], "failure": [{"streamName": "...", "message": "..."}]}
        """
        parsed: list[SubscriptionResult] = []

        successes = result.get("success", []) if isinstance(result, dict) else []
        failures = result.get("failure", []) if isinstance(result, dict) else []

        for entry in successes:
            parsed.append(
                SubscriptionResult(
                    stream_name=entry.get("streamName", ""),
                    success=True,
                    sid=entry.get("sid", ""),
                )
            )
        for entry in failures:
            parsed.append(
                SubscriptionResult(
                    stream_name=entry.get("streamName", ""),
                    success=False,
                    message=entry.get("message", "Unknown failure"),
                )
            )

        covered = {p.stream_name for p in parsed}
        for stream_name in requested_streams:
            if stream_name not in covered:
                parsed.append(SubscriptionResult(stream_name=stream_name, success=False, message="No entry in Cortex response"))

        return parsed
    # new
    def _register_callback(
        self,
        stream_name: str,
        callback: Callable[[dict], None],
        ) -> None:
        existing = self._callbacks.get(stream_name)

        if existing is callback:
            return

        if existing is not None:
            self.client.off(stream_name, existing)
            log.debug(
                f"Removed previous callback for stream '{stream_name}'"
            )

        self.client.on(stream_name, callback)
        self._callbacks[stream_name] = callback

        log.debug(
            f"Registered callback for stream '{stream_name}'"
        )

    def _remove_callback(self, stream_name: str) -> None:
        callback = self._callbacks.pop(stream_name, None)

        if callback is not None:
            self.client.off(stream_name, callback)
            log.debug(
                f"Removed callback for stream '{stream_name}'"
            )

    def reset(self) -> None:
    
        for stream_name in list(self._callbacks):
            self._remove_callback(stream_name)

        self._active_streams.clear()

        log.debug("Stream manager state reset")

"""
    Clear local subscription state and remove registered callbacks.

    Used after a Cortex WebSocket reconnect because the old Cortex
    session/subscription no longer belongs to the new connection."""