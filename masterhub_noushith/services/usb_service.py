"""
services/usb_service.py
-----------------------
Thread-safe USB / Serial hardware communication service.
Connects MasterHub to target PCs (running pc_agent over USB COM port),
Raspberry Pi coprocessors, and microcontrollers.
Exchanges JSON-line framed MasterHub Envelope packets over UART/Serial.
"""

import json
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

try:
    import serial
    import serial.tools.list_ports
    PYSERIAL_AVAILABLE = True
except ImportError:
    serial = None
    PYSERIAL_AVAILABLE = False

from services.logger_service import get_logger

log = get_logger("services.usb")


class USBService:
    def __init__(self):
        self._lock = threading.Lock()
        self._serial: Optional[Any] = None
        self._port: Optional[str] = None
        self._baudrate: int = 115200
        self._connected: bool = False
        self._running: bool = False
        self._rx_thread: Optional[threading.Thread] = None
        self._tx_count: int = 0
        self._rx_count: int = 0
        self._last_rx: Optional[Dict[str, Any]] = None

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected and (self._serial is not None or self._port == "SIMULATED")

    @property
    def port(self) -> Optional[str]:
        return self._port

    @property
    def baudrate(self) -> int:
        return self._baudrate

    def list_ports(self) -> List[Dict[str, str]]:
        """Scans and returns all physical and virtual COM ports on Windows."""
        if not PYSERIAL_AVAILABLE:
            log.warning("pyserial is not installed in the environment.")
            return []

        results = []
        try:
            for p in serial.tools.list_ports.comports():
                results.append({
                    "port": p.device,
                    "description": p.description or p.device,
                    "hwid": p.hwid or "",
                })
        except Exception as exc:
            log.error(f"Failed to scan serial ports: {exc}")
        return results

    def connect(self, port: str, baudrate: int = 115200, timeout: float = 1.0) -> Dict[str, Any]:
        """Connect to a designated COM port."""
        port = str(port).strip()
        with self._lock:
            if self._connected:
                self._disconnect_locked()

            self._port = port
            self._baudrate = int(baudrate)

            # Simulated / Loopback mode support
            if port.upper() in ("SIMULATED", "LOOPBACK", "TEST", "MOCK"):
                self._connected = True
                self._running = True
                log.info(f"USB Serial connected in {port.upper()} mode @ {baudrate} baud")
                return {"success": True, "port": port, "baudrate": baudrate, "connected": True, "simulated": True}

            if not PYSERIAL_AVAILABLE:
                return {"success": False, "error": "pyserial library is not installed", "connected": False}

            try:
                self._serial = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=timeout,
                    write_timeout=timeout,
                )
                self._connected = True
                self._running = True
                self._rx_thread = threading.Thread(target=self._rx_worker, daemon=True)
                self._rx_thread.start()
                log.info(f"USB Serial opened successfully on {port} @ {baudrate} baud")
                return {"success": True, "port": port, "baudrate": baudrate, "connected": True}
            except Exception as exc:
                self._serial = None
                self._connected = False
                self._running = False
                log.error(f"Failed to open USB Serial port {port}: {exc}")
                return {"success": False, "error": str(exc), "port": port, "connected": False}

    def disconnect(self) -> Dict[str, Any]:
        """Disconnect active USB serial link."""
        with self._lock:
            return self._disconnect_locked()

    def _disconnect_locked(self) -> Dict[str, Any]:
        prev_port = self._port
        self._running = False
        self._connected = False
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception as exc:
                log.warning(f"Error closing serial port {prev_port}: {exc}")
            self._serial = None
        self._port = None
        log.info(f"USB Serial disconnected from {prev_port}")
        return {"success": True, "message": f"Disconnected from {prev_port}"}

    def send_command(
        self,
        target_device_id: str,
        domain: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        command_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Formats a MasterHub Envelope and sends it as a single JSON line over the serial link.
        Matches the framing expected by pc_agent protocol/serializer.py.
        """
        cmd_id = command_id or f"cmd_{uuid.uuid4().hex[:10]}"
        envelope = {
            "protocol": "masterhub",
            "version": "1.0",
            "message_type": "command",
            "command_id": cmd_id,
            "target": target_device_id,
            "domain": domain,
            "action": action,
            "params": params or {},
            "timestamp": time.time(),
        }

        line = json.dumps(envelope) + "\n"
        data_bytes = line.encode("utf-8")

        with self._lock:
            if not self._connected:
                log.warning(f"Cannot send USB command: Serial port is not connected (tried port {self._port})")
                return {
                    "success": False,
                    "error": "USB Serial port is not connected",
                    "command_id": cmd_id,
                    "target": target_device_id,
                    "domain": domain,
                    "action": action,
                    "transport": "usb",
                    "envelope": envelope,
                }

            if self._port in ("SIMULATED", "LOOPBACK", "TEST", "MOCK") or self._serial is None:
                self._tx_count += 1
                log.info(f"[USB SIMULATED TX] -> {envelope}")
                return {
                    "success": True,
                    "command_id": cmd_id,
                    "target": target_device_id,
                    "domain": domain,
                    "action": action,
                    "transport": "usb",
                    "port": self._port,
                    "envelope": envelope,
                    "simulated": True,
                }

            try:
                self._serial.write(data_bytes)
                self._serial.flush()
                self._tx_count += 1
                log.info(f"[USB TX] {self._port} -> {action} (id={cmd_id})")
                return {
                    "success": True,
                    "command_id": cmd_id,
                    "target": target_device_id,
                    "domain": domain,
                    "action": action,
                    "transport": "usb",
                    "port": self._port,
                    "envelope": envelope,
                }
            except Exception as exc:
                log.error(f"USB Serial write failed on {self._port}: {exc}")
                return {
                    "success": False,
                    "error": f"USB Serial write failed: {exc}",
                    "command_id": cmd_id,
                    "target": target_device_id,
                    "domain": domain,
                    "action": action,
                    "transport": "usb",
                    "port": self._port,
                    "envelope": envelope,
                }

    def _rx_worker(self):
        """Background thread reading incoming JSON-lines from serial."""
        while self._running:
            try:
                ser = self._serial
                if ser is None or not ser.is_open:
                    break

                raw_line = ser.readline()
                if not raw_line:
                    continue

                line_str = raw_line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                self._rx_count += 1
                try:
                    payload = json.loads(line_str)
                    self._last_rx = payload
                    log.debug(f"[USB RX] {self._port} <- {payload}")
                except Exception:
                    log.debug(f"[USB RX RAW] {self._port} <- {line_str}")
            except Exception as exc:
                if self._running:
                    log.error(f"USB RX worker error: {exc}")
                break

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive USB serial status."""
        ports = self.list_ports()
        with self._lock:
            return {
                "connected": self._connected,
                "port": self._port,
                "baudrate": self._baudrate,
                "tx_count": self._tx_count,
                "rx_count": self._rx_count,
                "last_rx": self._last_rx,
                "available_ports": ports,
            }


usb_service = USBService()
