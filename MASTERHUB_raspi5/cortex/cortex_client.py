"""
cortex/cortex_client.py
-------------------------
Generic, reusable JSON-RPC-over-WebSocket client for the Emotiv Cortex
API. This file knows NOTHING about authentication, headsets, sessions,
or streams -- those concerns live in auth.py, headset.py, session.py,
and stream.py, which are all built on top of this client. Keeping this
file generic is deliberate, per spec, so it can be reused as-is if a
future module needs to speak JSON-RPC to Cortex for something new.

Responsibilities:
    * Open/maintain the WebSocket connection to the local Cortex service
    * Send JSON-RPC 2.0 requests and match responses by request id
    * Automatically reconnect on unexpected disconnects
    * Heartbeat via WebSocket ping/pong (detects dead connections early)
    * Dispatch unsolicited stream messages (e.g. "com" mental command
      data) to registered callbacks
    * Centralized logging and exception handling for all of the above
"""

from __future__ import annotations

import itertools
import json
import ssl
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import websocket  # websocket-client package, see requirements.txt

from cortex.config import (
    CORTEX_URL,
    HEARTBEAT_INTERVAL,
    HEARTBEAT_TIMEOUT,
    MAX_RECONNECT_ATTEMPTS,
    RECONNECT_DELAY,
    REQUEST_TIMEOUT,
    VERIFY_SSL,
)
from cortex.logger import get_logger

log = get_logger("cortex_client")


class CortexRequestError(Exception):
    """Raised when a JSON-RPC call returns a Cortex 'error' object."""

    def __init__(self, code, message, data=None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"Cortex error {code}: {message}")


class CortexConnectionError(Exception):
    """Raised when the WebSocket connection cannot be established, is
    lost mid-request, or a request times out waiting for a response."""


@dataclass
class _PendingRequest:
    event: threading.Event = field(default_factory=threading.Event)
    response: Optional[dict] = None


class CortexClient:
    """
    Low-level JSON-RPC client for wss://localhost:6868 (the local
    Cortex service started by the EMOTIV Launcher/App).
    """

    def __init__(
        self,
        url: Optional[str] = None,
        verify_ssl: bool = VERIFY_SSL,
        on_reconnect: Optional[Callable[[], None]] = None,
        auto_reconnect: bool = True,
    ):
        from cortex.config import reload_credentials
        self.url = url if url is not None else reload_credentials()[3]
        self.auto_reconnect = auto_reconnect
        self.verify_ssl = verify_ssl
        self.on_reconnect = on_reconnect

        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._id_counter = itertools.count(1)
        self._pending: dict[int, _PendingRequest] = {}
        self._pending_lock = threading.Lock()

        # message_key -> list of callbacks, e.g. "com" -> [handler, ...]
        self._event_callbacks: dict[str, list[Callable[[dict], None]]] = {}

        self._connected_event = threading.Event()
        self._should_run = False
        self._closing = False
        self._reconnect_attempts = 0
        self._reconnect_lock = threading.Lock()
        self._is_reconnecting = False

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self, timeout: float = REQUEST_TIMEOUT) -> None:
        """
        Open the WebSocket connection and start the background receive
        thread. Blocks until connected or `timeout` seconds elapse.
        """
        if self.connected:
            return
        self._should_run = True
        self._closing = False
        self._open_socket()

        if not self._connected_event.wait(timeout=timeout):
            raise CortexConnectionError(f"Timed out connecting to Cortex at {self.url}")

    def close(self) -> None:
        """Gracefully close the connection and stop reconnect attempts."""
        self._closing = True
        self._should_run = False
        with self._reconnect_lock:
            self._is_reconnecting = False
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                log.debug("Ignoring error while closing an already-broken socket", exc_info=True)
        self._connected_event.clear()
        log.info("Cortex client closed")

    @property
    def connected(self) -> bool:
        return self._connected_event.is_set()

    def _open_socket(self) -> None:
        sslopt = None if self.verify_ssl else {"cert_reqs": ssl.CERT_NONE}
        self._connected_event.clear()

        # Ignore callbacks from a retired socket.
        previous, self._ws = self._ws, None
        if previous is not None:
            try:
                previous.close()
            except Exception:
                pass

        self._ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        self._thread = threading.Thread(
            target=self._ws.run_forever,
            kwargs={
                "sslopt": sslopt,
                "ping_interval": HEARTBEAT_INTERVAL,
                "ping_timeout": HEARTBEAT_TIMEOUT,
            },
            daemon=True,
            name="cortex-ws-recv",
        )
        self._thread.start()

    def _on_open(self, _ws) -> None:
        if _ws is not self._ws or self._closing:
            return
        log.info(f"Connected to Cortex at {self.url}")
        self._reconnect_attempts = 0
        with self._reconnect_lock:
            self._is_reconnecting = False
        self._connected_event.set()

    def _on_error(self, _ws, error) -> None:
        log.error(f"Cortex WebSocket error: {error}")

    def _on_close(self, _ws, status_code, message) -> None:
        if _ws is not self._ws:
            return
        self._connected_event.clear()
        log.warning(f"Cortex WebSocket closed (status={status_code}, message={message})")

        # Unblock any in-flight call() so callers fail fast instead of
        # hanging until their own timeout.
        with self._pending_lock:
            for pending in self._pending.values():
                pending.response = {"error": {"code": -1, "message": "Connection closed"}}
                pending.event.set()
            self._pending.clear()

        if self.auto_reconnect and self._should_run and not self._closing:
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        with self._reconnect_lock:
            if self._is_reconnecting or self._closing or not self._should_run:
                return
            self._is_reconnecting = True

        if MAX_RECONNECT_ATTEMPTS and self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            log.error(f"Giving up after {self._reconnect_attempts} reconnect attempts")
            with self._reconnect_lock:
                self._is_reconnecting = False
            return

        self._reconnect_attempts += 1
        delay = min(RECONNECT_DELAY * (1.2 ** min(self._reconnect_attempts - 1, 5)), 15.0)
        log.info(f"Reconnecting to Cortex in {delay:.1f}s (attempt {self._reconnect_attempts})")

        def _reconnect_worker() -> None:
            time.sleep(delay)
            if not self._should_run or self._closing:
                with self._reconnect_lock:
                    self._is_reconnecting = False
                return
            try:
                self._open_socket()
                if self._connected_event.wait(timeout=REQUEST_TIMEOUT):
                    log.info("Reconnected to Cortex")
                    with self._reconnect_lock:
                        self._is_reconnecting = False
                    if self.on_reconnect is not None:
                        try:
                            self.on_reconnect()
                        except Exception:
                            log.exception("on_reconnect callback raised an exception")
                else:
                    with self._reconnect_lock:
                        self._is_reconnecting = False
                    self._schedule_reconnect()
            except Exception:
                log.exception("Reconnect attempt failed")
                with self._reconnect_lock:
                    self._is_reconnecting = False
                self._schedule_reconnect()

        threading.Thread(target=_reconnect_worker, daemon=True, name="cortex-ws-reconnect").start()

    # ------------------------------------------------------------------
    # JSON-RPC request/response
    # ------------------------------------------------------------------

    def call(self, method: str, params: Optional[dict] = None, timeout: float = REQUEST_TIMEOUT) -> dict:
        """
        Send a JSON-RPC request and block until its matching response
        arrives (matched by "id"). Raises CortexRequestError if Cortex
        returns an "error" object, or CortexConnectionError if there is
        no active connection, sending fails, or the request times out.
        """
        if not self.connected or self._ws is None:
            raise CortexConnectionError("Not connected to Cortex")

        request_id = next(self._id_counter)
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}

        pending = _PendingRequest()
        with self._pending_lock:
            self._pending[request_id] = pending

        log.debug(f"-> {method} (id={request_id})")
        try:
            self._ws.send(json.dumps(payload))
        except Exception as exc:
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise CortexConnectionError(f"Failed to send '{method}': {exc}") from exc

        if not pending.event.wait(timeout=timeout):
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise CortexConnectionError(f"Timed out waiting for response to '{method}' (id={request_id})")

        response = pending.response or {}
        if "error" in response:
            error = response["error"]
            log.warning(f"<- {method} (id={request_id}) ERROR {error.get('code')}: {error.get('message')}")
            raise CortexRequestError(error.get("code"), error.get("message"), error.get("data"))

        log.debug(f"<- {method} (id={request_id}) OK")
        return response.get("result", {})

    # ------------------------------------------------------------------
    # Unsolicited message dispatch (stream data, warnings, etc.)
    # ------------------------------------------------------------------

    def on(self, key: str, callback: Callable[[dict], None]) -> None:
        """
        Register a callback for unsolicited (non-JSON-RPC-response)
        messages whose payload contains `key` as a top-level field --
        e.g. on("com", handler) for mental command stream data. Multiple
        callbacks may be registered for the same key. This is the
        extension point stream.py uses to add new stream types later
        without touching this file.
        """
        self._event_callbacks.setdefault(key, []).append(callback)

  # def off(self, key: str, callback: Callable[[dict], None]) -> None:
   #      """Remove a previously registered callback."""
   #     callbacks = self._event_callbacks.get(key, [])
    #    if callback in callbacks:
    #        callbacks.remove(callback)

    def off(self, key: str, callback: Callable[[dict], None]) -> None:
        callbacks = self._event_callbacks.get(key)

        if not callbacks:
            return

        try:
            callbacks.remove(callback)
        except ValueError:
            return

        if not callbacks:
            self._event_callbacks.pop(key, None)



 
    def _on_message(self, _ws, raw_message: str) -> None:
        if _ws is not self._ws:
            return
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            log.warning(f"Received non-JSON message, ignoring: {raw_message[:200]!r}")
            return

        if isinstance(message, dict) and "id" in message:
            self._dispatch_response(message)
            return

        self._dispatch_event(message)

    def _dispatch_response(self, message: dict) -> None:
        request_id = message.get("id")
        with self._pending_lock:
            pending = self._pending.pop(request_id, None)
        if pending is None:
            log.debug(f"Received response for unknown/expired request id={request_id}")
            return
        pending.response = message
        pending.event.set()

    def _dispatch_event(self, message: dict) -> None:
        if not isinstance(message, dict):
            log.debug(f"Ignoring non-object Cortex message: {message!r}")
            return

        matched = False
        for key, callbacks in list(self._event_callbacks.items()):
            if key in message:
                matched = True
                for callback in list(callbacks):
                    try:
                        callback(message)
                    except Exception:
                        log.exception(f"Callback registered for '{key}' raised an exception")

        if not matched:
            log.debug(f"Unhandled Cortex message (no registered callback): {message}")
