"""
core/devices.py
---------------
Thread-safe Device Registry for MasterHub PC Agents and target nodes.
Manages registration, capability discovery, online/offline status,
and active target routing for Desktop and AI/ML domains.
"""

import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional
from core.account_store import database, DEFAULT_DATABASE
import sqlite3


class DeviceRegistry:
    def __init__(self, storage_path=None, database_path=None):
        self._lock = threading.Lock()
        self._storage_path = Path(storage_path) if storage_path is not None else None
        self._database_path = database_path
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
        for record in self._devices.values():
            record['device_category'] = 'laptop'
        saved = None
        if self._database_path is not None:
            with database(self._database_path) as db:
                row = db.execute('SELECT payload FROM device_registry WHERE id=1').fetchone()
                if row:
                    saved = json.loads(row['payload'])
        if saved is None and self._storage_path is not None and self._storage_path.exists():
            saved = json.loads(self._storage_path.read_text(encoding='utf-8'))
        if saved is not None:
            self._devices = {record['device_id']: record for record in saved['devices']}
            for record in self._devices.values():
                record.setdefault('device_category', 'mobile' if record.get('device_type') == 'mobile' else 'laptop')
                record['status'] = 'ONLINE' if record['device_id'] == 'Local Host' else 'OFFLINE'
        if self._database_path is not None:
            self._save()

    def _save(self):
        """Atomically persist registrations while holding the registry lock."""
        if self._database_path is not None:
            with database(self._database_path) as db:
                db.execute('INSERT INTO device_registry VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                           (json.dumps({'devices': list(self._devices.values())}),))
            return
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self._storage_path.parent,
                                             suffix='.tmp', delete=False) as stream:
                temporary = stream.name
                json.dump({'devices': list(self._devices.values())}, stream, indent=2)
                stream.write('\n')
            os.replace(temporary, self._storage_path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def register(
        self,
        device_id: str,
        name: Optional[str] = None,
        transport: str = "mqtt",
        capabilities: Optional[List[str]] = None,
        status: str = "OFFLINE",
        device_type: Optional[str] = None,
        platform: Optional[str] = None,
        device_category: Optional[str] = None,
        mqtt_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            device_id = str(device_id).strip()
            if not device_id:
                raise ValueError("device_id cannot be empty")

            existing = self._devices.get(device_id, {})
            category = device_category or existing.get('device_category') or ('mobile' if device_type == 'mobile' else 'laptop')
            if category not in ('laptop', 'mobile'):
                raise ValueError('device_category must be laptop or mobile')
            record = {
                "device_id": device_id,
                "name": name or existing.get("name") or device_id,
                "transport": transport or existing.get("transport") or "mqtt",
                "status": status or existing.get("status") or "ONLINE",
                "capabilities": capabilities if capabilities is not None else existing.get("capabilities", ["ai_ml"] if category == 'mobile' else ["desktop", "ai_ml"]),
                "device_category": category,
                "device_type": 'mobile' if category == 'mobile' else 'computer',
                "platform": platform or (existing.get("platform") if category == existing.get('device_category') else None) or ('android' if category == 'mobile' else 'windows'),
                "last_seen": time.time(),
                "is_default": existing.get("is_default", False),
            }
            self._devices[device_id] = record
            if mqtt_prefix or existing.get('mqtt_prefix'):
                record['mqtt_prefix'] = mqtt_prefix or existing['mqtt_prefix']
            try:
                self._save()
            except (OSError, sqlite3.Error):
                if existing:
                    self._devices[device_id] = existing
                else:
                    del self._devices[device_id]
                raise
            return dict(record)

    def unregister(self, device_id: str) -> bool:
        with self._lock:
            if device_id in self._devices:
                if device_id == "Local Host":
                    return False
                removed = self._devices.pop(device_id)
                try:
                    self._save()
                except (OSError, sqlite3.Error):
                    self._devices[device_id] = removed
                    raise
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
                    "device_category": "laptop",
                    "platform": "windows",
                    "last_seen": time.time(),
                    "is_default": False,
                }
                self._save()
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


device_registry = DeviceRegistry(Path(__file__).resolve().parents[1] / 'data' / 'devices.json', DEFAULT_DATABASE)
