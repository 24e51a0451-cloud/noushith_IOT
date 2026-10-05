"""
cortex/headset.py
-------------------
Headset discovery, connection, and diagnostics (battery / signal
quality / firmware info) for an Emotiv EPOC X, built on top of the
generic cortex_client.CortexClient.

Cortex methods used:
    queryHeadsets    -- discover headsets currently visible to Cortex
    controlDevice    -- connect / disconnect / refresh (rescan)

Battery level and per-channel signal quality are not part of
queryHeadsets' response on most firmware/Cortex versions -- they arrive
as samples on Cortex's "dev" stream. This module exposes a small,
self-contained helper (`read_device_diagnostics`) that subscribes to
"dev" just long enough to capture one sample and unsubscribes
immediately after, rather than requiring the caller to keep a stream
subscription open just to check battery level.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from cortex.cortex_client import CortexClient, CortexRequestError
from cortex.logger import get_logger

log = get_logger("headset")


class HeadsetError(Exception):
    """Raised when a headset cannot be found, connected, or queried."""


@dataclass
class HeadsetInfo:
    id: str
    status: str
    connected_by: str = ""
    firmware: str = ""
    dongle: str = ""
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def is_connected(self) -> bool:
        return self.status.lower() == "connected"

    @classmethod
    def from_cortex(cls, data: dict) -> "HeadsetInfo":
        return cls(
            id=data.get("id", ""),
            status=data.get("status", "unknown"),
            connected_by=data.get("connectedBy", ""),
            firmware=data.get("firmware", ""),
            dongle=data.get("dongle", ""),
            raw=data,
        )


@dataclass
class DeviceDiagnostics:
    headset_id: str
    battery_percent: Optional[float] = None
    battery_voltage: Optional[float] = None
    signal_quality: Optional[float] = None
    per_channel_quality: Optional[list] = None
    raw: dict = field(default_factory=dict, repr=False, compare=False)


class HeadsetManager:
    def __init__(self, client: CortexClient):
        self.client = client

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self, headset_id: Optional[str] = None) -> list[HeadsetInfo]:
        """
        Return every headset Cortex currently sees (Bluetooth-paired or
        USB-dongle-connected), optionally filtered to a single id.
        """
        params = {"id": headset_id} if headset_id else {}
        try:
            result = self.client.call("queryHeadsets", params)
        except CortexRequestError as exc:
            log.error(f"queryHeadsets failed: {exc}")
            raise HeadsetError(f"queryHeadsets failed: {exc}") from exc

        headsets = [HeadsetInfo.from_cortex(entry) for entry in result] if isinstance(result, list) else []
        log.info(f"Discovered {len(headsets)} headset(s): {[h.id for h in headsets]}")
        return headsets

    def get_info(self, headset_id: str) -> Optional[HeadsetInfo]:
        matches = self.discover(headset_id=headset_id)
        return matches[0] if matches else None

    def find_first_available(self) -> Optional[HeadsetInfo]:
        """Convenience helper: return the first headset Cortex can see, if any."""
        headsets = self.discover()
        return headsets[0] if headsets else None

    def refresh(self) -> None:
        """Ask Cortex to rescan for headsets (Bluetooth/USB dongle)."""
        try:
            self.client.call("controlDevice", {"command": "refresh"})
            log.info("Requested headset rescan (controlDevice refresh)")
        except CortexRequestError as exc:
            log.error(f"controlDevice refresh failed: {exc}")
            raise HeadsetError(f"controlDevice refresh failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, headset_id: str) -> None:
        try:
            self.client.call("controlDevice", {"command": "connect", "headset": headset_id})
            log.info(f"Connected headset '{headset_id}'")
        except CortexRequestError as exc:
            err_msg = str(exc).lower()
            if "already connected" in err_msg or "connecting" in err_msg:
                log.info(f"Headset '{headset_id}' connection in progress or already connected ({exc})")
                return
            log.error(f"Failed to connect headset '{headset_id}': {exc}")
            raise HeadsetError(f"Failed to connect headset '{headset_id}': {exc}") from exc

    def disconnect(self, headset_id: str) -> None:
        try:
            self.client.call("controlDevice", {"command": "disconnect", "headset": headset_id})
            log.info(f"Disconnected headset '{headset_id}'")
        except CortexRequestError as exc:
            log.warning(f"Disconnect headset '{headset_id}' notice: {exc}")

    def ensure_connected(self, headset_id: Optional[str] = None, timeout: float = 25.0) -> HeadsetInfo:
        """
        Discover a headset (or use the given id), connect it if it
        isn't already, and wait up to `timeout` seconds for Cortex to
        report status "connected". Returns the final HeadsetInfo.
        Retries discovery and device refresh dynamically during the timeout window.
        """
        deadline = time.monotonic() + max(timeout, 5.0)
        last_refresh = 0.0
        target_id = headset_id

        while time.monotonic() < deadline:
            try:
                # Trigger a device refresh/rescan periodically if not yet found
                now = time.monotonic()
                if now - last_refresh > 4.0:
                    try:
                        self.refresh()
                    except Exception:
                        pass
                    last_refresh = now

                info = self.get_info(target_id) if target_id else self.find_first_available()
                if info is not None:
                    target_id = info.id
                    if info.is_connected:
                        log.info(f"Headset '{info.id}' is connected and ready")
                        return info

                    # If discovered but not connected, request connection
                    status_lower = info.status.lower()
                    if status_lower in ("discovered", "idle", "not_connected", "disconnected"):
                        try:
                            self.connect(info.id)
                        except HeadsetError as exc:
                            log.debug(f"Connect attempt for '{info.id}' returned: {exc}")

            except (HeadsetError, CortexRequestError) as exc:
                log.debug(f"Transient error while discovering/connecting headset: {exc}")

            time.sleep(0.5)

        # Final check before raising
        info = self.get_info(target_id) if target_id else self.find_first_available()
        if info and info.is_connected:
            return info

        if info is None:
            raise HeadsetError(
                "No headset found after scanning. Make sure the Emotiv EPOC X is powered on, "
                "paired/plugged in, and visible in EMOTIV Launcher."
            )

        raise HeadsetError(f"Timed out waiting for headset '{info.id}' (status: '{info.status}') to reach status 'connected'")

    # ------------------------------------------------------------------
    # Diagnostics (battery / signal quality)
    # ------------------------------------------------------------------

    def read_device_diagnostics(
        self,
        cortex_token: str,
        session_id: str,
        headset_id: str,
        timeout: float = 5.0,
    ) -> DeviceDiagnostics:
        """
        Subscribe to Cortex's "dev" stream just long enough to capture
        one sample (battery %, battery voltage, overall signal quality,
        and per-channel contact quality), then unsubscribe. Requires an
        already-created session (see session.py) because "dev", like
        every other data stream, is subscribed per-session.
        """
        captured: dict = {}
        received = threading.Event()

        def _on_dev(message: dict) -> None:
            captured.update(message)
            received.set()

        self.client.on("dev", _on_dev)
        try:
            self.client.call(
                "subscribe",
                {"cortexToken": cortex_token, "session": session_id, "streams": ["dev"]},
            )
            if not received.wait(timeout=timeout):
                raise HeadsetError(f"Timed out waiting for a 'dev' sample from headset '{headset_id}'")
        except CortexRequestError as exc:
            raise HeadsetError(f"Failed to subscribe to 'dev' stream: {exc}") from exc
        finally:
            self.client.off("dev", _on_dev)
            try:
                self.client.call(
                    "unsubscribe",
                    {"cortexToken": cortex_token, "session": session_id, "streams": ["dev"]},
                )
            except CortexRequestError:
                log.debug("unsubscribe('dev') failed/no-op; ignoring", exc_info=True)

        dev = captured.get("dev", [])
        # Documented "dev" payload shape: [signalStrengthPerChannel, batteryPercent, batteryVoltage, overallSignalQuality]
        per_channel = dev[0] if len(dev) > 0 else None
        battery_percent = dev[1] if len(dev) > 1 else None
        battery_voltage = dev[2] if len(dev) > 2 else None
        overall_quality = dev[3] if len(dev) > 3 else None

        diagnostics = DeviceDiagnostics(
            headset_id=headset_id,
            battery_percent=battery_percent,
            battery_voltage=battery_voltage,
            signal_quality=overall_quality,
            per_channel_quality=per_channel,
            raw=captured,
        )
        log.info(
            f"Diagnostics for '{headset_id}': battery={battery_percent} "
            f"signal_quality={overall_quality}"
        )
        return diagnostics
