"""
core/devices.py
---------------
Thread-safe Device Registry for MasterHub PC Agents and target nodes.
Manages registration, capability discovery, online/offline status,
and active target routing for Desktop and AI/ML domains.
"""

import threading
import time
from typing import Any, Dict, List, Optional


class DeviceRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._active_target = "Local Host"
        self._devices: Dict[str, Dict[str, Any]] = {
            "Local Host": {
                "device_id": "Local Host",
                "name": "Loopback Direct",
                "transport": "local",
                "status": "ONLINE",
                "capabilities": ["desktop", "ai_ml"],
                "device_type": "computer",
                "platform": "windows",
                "last_seen": time.time(),
                "is_default": False,
            },
            "PC_001": {
                "device_id": "PC_001",
                "name": "PC Agent 001",
                "transport": "mqtt",
                "status": "OFFLINE",
                "capabilities": ["desktop", "ai_ml"],
                "device_type": "computer",
                "platform": "windows",
                "last_seen": time.time(),
                "is_default": True,
            },
        }

    def register(
        self,
        device_id: str,
        name: Optional[str] = None,
        transport: str = "mqtt",
        capabilities: Optional[List[str]] = None,
        status: str = "OFFLINE",
        device_type: Optional[str] = "computer",
        platform: Optional[str] = "windows",
    ) -> Dict[str, Any]:
        with self._lock:
            device_id = str(device_id).strip()
            if not device_id:
                raise ValueError("device_id cannot be empty")

            existing = self._devices.get(device_id, {})
            record = {
                "device_id": device_id,
                "name": name or existing.get("name") or device_id,
                "transport": transport or existing.get("transport") or "mqtt",
                "status": status or existing.get("status") or "ONLINE",
                "capabilities": capabilities or existing.get("capabilities") or ["desktop", "ai_ml"],
                "device_type": device_type or existing.get("device_type") or "computer",
                "platform": platform or existing.get("platform") or "windows",
                "last_seen": time.time(),
                "is_default": existing.get("is_default", False),
            }
            self._devices[device_id] = record
            return dict(record)

    def unregister(self, device_id: str) -> bool:
        with self._lock:
            if device_id in self._devices:
                if device_id == "Local Host":
                    return False
                del self._devices[device_id]
                if self._active_target == device_id:
                    self._active_target = "Local Host"
                return True
            return False

    def update_status(
        self,
        device_id: str,
        status: str,
        capabilities: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            if device_id not in self._devices:
                self._devices[device_id] = {
                    "device_id": device_id,
                    "name": f"Remote {device_id}",
                    "transport": "mqtt",
                    "status": status,
                    "capabilities": capabilities or ["desktop", "ai_ml"],
                    "device_type": "computer",
                    "platform": "windows",
                    "last_seen": time.time(),
                    "is_default": False,
                }
                return dict(self._devices[device_id])

            record = self._devices[device_id]
            record["status"] = status
            record["last_seen"] = time.time()
            if capabilities:
                record["capabilities"] = capabilities
            return dict(record)

    def get(self, device_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            dev = self._devices.get(device_id)
            return dict(dev) if dev else None

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(d) for d in self._devices.values()]

    def get_active_target(self) -> str:
        with self._lock:
            return self._active_target

    def set_active_target(self, target: str) -> str:
        with self._lock:
            target = str(target).strip()
            if target in self._devices:
                self._active_target = target
            else:
                self._active_target = target
            return self._active_target


device_registry = DeviceRegistry()
