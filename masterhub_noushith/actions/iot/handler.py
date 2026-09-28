"""
actions/iot/handler.py
-----------------------
Executes IoT domain actions by publishing to MQTT in the exact JSON shape
the ESP32 Unified Firmware expects:

    {"command": "Left_light_on", "command_id": "<uuid>"}
    {"command": "OTA_UPDATE", "command_id": "<uuid>", "url": "http://..."}
    {"command": "TEST", "command_id": "<uuid>"}
    {"command": "all_off", "command_id": "<uuid>"}

Topic Scheme:
    Default: 'iot/esp32/action'
    Device-specific (optional): 'iot/device/<MAC>/action'
"""

import json
import os
import uuid

from services.logger_service import get_logger
from services.mqtt_service import mqtt_service, get_first_online_device

log = get_logger("actions.iot")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_IOT_MAP_PATH = os.path.join(_BASE_DIR, "mappings", "iot_map.json")


class IoTHandler:
    def __init__(self, iot_map_path: str = _IOT_MAP_PATH):
        self.iot_map_path = iot_map_path
        self._iot_map = {}
        self._load()

    def _load(self):
        try:
            with open(self.iot_map_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._iot_map = {k: v for k, v in data.items() if not k.startswith("_")}
            log.info(f"Loaded {len(self._iot_map)} IoT action payloads")
        except FileNotFoundError:
            log.error(f"iot_map.json not found at {self.iot_map_path}")
            self._iot_map = {}
        except json.JSONDecodeError as exc:
            log.error(f"iot_map.json invalid JSON: {exc}")
            self._iot_map = {}

    def reload(self):
        self._load()

    def execute(self, action: str, params: dict = None) -> dict:
        """
        Execute a single IoT action: look up its device-facing command
        string and publish it as a JSON envelope the ESP32 can parse.
        """
        params = params or {}
        device_command = self._iot_map.get(action, action)
        command_id = params.get("command_id") or uuid.uuid4().hex[:12]

        # Handle ping shortcut
        if action == "iot_ping" or device_command.upper() == "PING":
            ok = mqtt_service.ping_esp32()
            return {
                "success": ok,
                "domain": "iot",
                "action": "iot_ping",
                "topic": "iot/esp32/ping",
                "payload": "PING"
            }

        # Build JSON payload
        payload_data = {
            "command": device_command,
            "command_id": command_id
        }

        # Attach optional OTA update URL
        if action == "ota_update" or device_command == "OTA_UPDATE":
            ota_url = params.get("url") or "http://172.18.1.102:5000/firmware.bin"
            payload_data["url"] = ota_url

        wire_payload = json.dumps(payload_data)

        # Target topic strictly matches the ESP32 Unified Firmware:
        # actionTopic = "iot/esp32/action"
        topic = "iot/esp32/action"

        # Publish to primary topic subscribed by firmware
        success = mqtt_service.publish(wire_payload, topic=topic)

        # If a specific device_id was used, also mirror to MAC topic for backwards compatibility
        device_id = params.get("device_id")
        if device_id and device_id != "esp32":
            mqtt_service.publish(wire_payload, topic=f"iot/device/{device_id}/action")

        result = {
            "success": success,
            "domain": "iot",
            "action": action,
            "command": device_command,
            "payload": wire_payload,
            "command_id": command_id,
            "topic": topic,
        }
        if not success:
            result["error"] = "MQTT publish failed"
        return result


iot_handler = IoTHandler()
