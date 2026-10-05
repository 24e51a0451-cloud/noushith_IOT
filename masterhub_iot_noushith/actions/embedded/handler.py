"""
actions/embedded/handler.py
------------------------------

Embedded domain:
    • Wheelchair
    • Robot Car

Publishes movement commands over MQTT.
"""

import json
import os

from services.logger_service import get_logger
from services.mqtt_service import mqtt_service
from services.hardware_config import read_config

log = get_logger("actions.embedded")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_EMBEDDED_MAP_PATH = os.path.join(_BASE_DIR, "mappings", "embedded_map.json")


# ------------------------------------------------------------------
# Device IDs
# ------------------------------------------------------------------

ROBOT_CAR_DEVICE_ID = "98:A3:16:BF:2C:C0"

# Change this to your wheelchair MAC
WHEELCHAIR_DEVICE_ID = "98:A3:16:BF:2C:C1"


# ------------------------------------------------------------------
# Supported Commands
# ------------------------------------------------------------------

_CHAIR_ACTIONS = {
    "chair_forward",
    "chair_back",
    "chair_backward",
    "chair_left",
    "chair_right",
    "chair_left360",
    "chair_right360",
    "chair_360",
    "chair_stop",
}

_CAR_ACTIONS = {
    "car_forward",
    "car_back",
    "car_backward",
    "car_left",
    "car_right",
    "car_left360",
    "car_right360",
    "car_360",
    "car_stop",
}

_CHAIR_PAYLOADS = {
    "chair_forward": "CHAIRFORWARD",
    "chair_back": "CHAIRBACKWARD",
    "chair_backward": "CHAIRBACKWARD",
    "chair_left": "CHAIRLEFT",
    "chair_right": "CHAIRRIGHT",
    "chair_left360": "CHAIRLEFT360",
    "chair_right360": "CHAIRRIGHT360",
    "chair_360": "CHAIRLEFT360",
    "chair_stop": "CHAIRSTOP",
}

_CAR_PAYLOADS = {
    "car_forward": "LIFTCARFORWARD",
    "car_back": "LIFTCARBACKWARD",
    "car_backward": "LIFTCARBACKWARD",
    "car_left": "LIFTCARLEFT",
    "car_right": "LIFTCARRIGHT",
    "car_left360": "LIFTCARLEFT360",
    "car_right360": "LIFTCARRIGHT360",
    "car_360": "LIFTCARLEFT360",
    "car_stop": "LIFTCARSTOP",
}


class EmbeddedHandler:

    def __init__(self):
        self._map = self._load_map()

    def _load_map(self):
        try:
            with open(_EMBEDDED_MAP_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            return {k: v for k, v in data.items() if not k.startswith("_")}

        except Exception:
            return {}

    def execute(self, action: str, params: dict = None):

        params = params or {}
        action = action.strip().lower()

        # Resolve generic actions if device specified
        device = str(params.get("device", "")).strip().lower()
        if action in ("left360", "360_left", "360"):
            action = "chair_left360" if device in ("wheelchair", "chair") else "car_left360"
        elif action in ("right360", "360_right"):
            action = "chair_right360" if device in ("wheelchair", "chair") else "car_right360"
        elif action in ("forward",):
            action = "chair_forward" if device in ("wheelchair", "chair") else "car_forward"
        elif action in ("back", "backward"):
            action = "chair_back" if device in ("wheelchair", "chair") else "car_back"
        elif action in ("left",):
            action = "chair_left" if device in ("wheelchair", "chair") else "car_left"
        elif action in ("right",):
            action = "chair_right" if device in ("wheelchair", "chair") else "car_right"
        elif action in ("stop",):
            action = "chair_stop" if device in ("wheelchair", "chair") else "car_stop"

        mapping = self._map.get(action)

        if mapping:
            params = dict(params)
            params.setdefault("mapping", mapping)

        if action in _CAR_ACTIONS:
            payload = _CAR_PAYLOADS.get(action)
            return self._publish_robot_car(payload)

        if action in _CHAIR_ACTIONS:
            payload = _CHAIR_PAYLOADS.get(action)
            return self._publish_wheelchair(payload)

        log.warning(f"Unknown Embedded Action : {action}")

        return {
            "success": False,
            "domain": "embedded",
            "action": action,
            "error": "Unknown Action"
        }

    # ---------------------------------------------------------
    # Robot Car (ESP32-C6 SynaptiMesh Slave)
    # ---------------------------------------------------------

    def _publish_robot_car(self, payload):

        topic = read_config()["car_topic"]
        device_id = topic.split("/")[1]
        ack_topic = f"robotcar/{device_id}/ack"
        status_topic = f"robotcar/{device_id}/status"

        # Resolve duration metadata based on ESP32-C6 firmware specifications
        duration_ms = None
        if "360" in payload:
            duration_ms = 2000
        elif "LEFT" in payload or "RIGHT" in payload:
            duration_ms = 500

        ok = mqtt_service.publish(
            payload=payload,
            topic=topic
        )

        if not ok:

            return {
                "success": False,
                "domain": "embedded",
                "device": "robot_car",
                "device_id": device_id,
                "action": payload,
                "error": "MQTT Publish Failed"
            }

        log.info(f"Robot Car Command Published : {payload} to {topic}")

        result = {
            "success": True,
            "delivery": "published",
            "hardware_confirmed": False,
            "domain": "embedded",
            "device": "robot_car",
            "device_id": device_id,
            "action": payload,
            "topic": topic,
            "ack_topic": ack_topic,
            "status_topic": status_topic,
            "payload": payload,
            "obstacle_limit_cm": 30.0,
        }
        if duration_ms:
            result["duration_ms"] = duration_ms

        return result

    # ---------------------------------------------------------
    # Wheelchair
    # ---------------------------------------------------------

    def _publish_wheelchair(self, payload):

        topic = read_config()["chair_topic"]
        device_id = topic.split("/")[1]

        duration_ms = None
        if "360" in payload:
            duration_ms = 2000
        elif "LEFT" in payload or "RIGHT" in payload:
            duration_ms = 500

        ok = mqtt_service.publish(
            payload=payload,
            topic=topic
        )

        if not ok:

            return {
                "success": False,
                "domain": "embedded",
                "device": "wheelchair",
                "device_id": device_id,
                "action": payload,
                "error": "MQTT Publish Failed"
            }

        log.info(f"Wheelchair Command Published : {payload} to {topic}")

        result = {
            "success": True,
            "delivery": "published",
            "hardware_confirmed": False,
            "domain": "embedded",
            "device": "wheelchair",
            "device_id": device_id,
            "action": payload,
            "topic": topic,
            "payload": payload
        }
        if duration_ms:
            result["duration_ms"] = duration_ms

        return result


embedded_handler = EmbeddedHandler()