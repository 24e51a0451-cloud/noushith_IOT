"""
services/mqtt_service.py
------------------------
Reusable MQTT client wrapping paho-mqtt with unified topic compatibility for:
  - ESP32 Unified IoT + BCI Actuator Node (iot/esp32/#, iot/+/status, iot/+/ack, iot/+/sensor)
  - MAC-scoped devices (iot/device/+/...)
  - Embedded mobility devices (robotcar/+, wheelchair/+)

Features
--------
✓ Persistent thread-safe MQTT connection
✓ Auto-reconnect on broker disconnect
✓ Bidirectional Status, ACK, Sensor, and Ping/Pong tracking
✓ Live state cache for IoT actuators (light, fan, pump) and LoRa telemetry
"""

import json
import uuid
from services.hardware_config import read_config
import threading
import time

import paho.mqtt.client as mqtt

from core.devices import device_registry
from services.logger_service import get_logger

log = get_logger("services.mqtt")

BROKER_HOST = "52.21.249.6"
BROKER_PORT = 1883
KEEPALIVE = 60

# Default Publish Topic
DEFAULT_TOPIC = "iot/esp32/action"

# Unified IoT Subscriptions (Matching ESP32 Unified Firmware)
ESP32_WILDCARD_TOPIC = "iot/esp32/#"
STATUS_TOPICS = ["iot/esp32/status", "iot/+/status", "iot/device/+/status"]
ACK_TOPICS = ["iot/esp32/ack", "iot/+/ack", "iot/device/+/ack"]
SENSOR_TOPICS = ["iot/esp32/sensor", "iot/+/sensor", "iot/device/+/sensor"]
PONG_TOPIC = "iot/esp32/pong"

# Embedded Topics
ROBOT_ACK_TOPIC = "robotcar/+/ack"
ROBOT_STATUS_TOPIC = "robotcar/+/status"
WHEELCHAIR_ACK_TOPIC = "wheelchair/+/ack"
WHEELCHAIR_STATUS_TOPIC = "wheelchair/+/status"

# PC Agent Topics (Target Node Control & Status)
PC_AGENT_STATUS_TOPIC = "masterhub/devices/+/status"
PC_AGENT_ACK_TOPIC = "masterhub/devices/+/ack"
PC_AGENT_ERROR_TOPIC = "masterhub/devices/+/error"

# In-memory runtime state registries
ONLINE_DEVICES = {}
DEVICE_STATES = {}
LATEST_SENSORS = {}
LAST_ACKS = {}
ROBOT_CAR_STATE = {
    "device_id": "98:A3:16:BF:2C:C0",
    "online": False,
    "status": "UNKNOWN",
    "last_ack": None,
    "motion_active": False,
    "obstacle_alert": None,
    "last_seen": 0,
}
WHEELCHAIR_STATE = {
    "device_id": "98:A3:16:BF:2C:C1",
    "online": False,
    "status": "UNKNOWN",
    "last_ack": None,
    "last_seen": 0,
}


class MQTTService:

    def __init__(
        self,
        host=BROKER_HOST,
        port=BROKER_PORT,
        topic=DEFAULT_TOPIC,
        client_id=None
    ):
        config = read_config()
        self.host = config["host"] if host == BROKER_HOST else host
        self.port = config["port"] if port == BROKER_PORT else port
        self.topic = topic
        self.client_id = client_id or f"masterhub_{uuid.uuid4().hex[:12]}"

        self._client = mqtt.Client(
            client_id=self.client_id,
            clean_session=True
        )

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self._connected = False
        self._lock = threading.Lock()

        # User-defined callback
        self.message_callback = None

    # -------------------------------------------------
    # MQTT CALLBACKS
    # -------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            log.info(f"Connected to MQTT Broker {self.host}:{self.port}")

            # Subscribe to ESP32 Unified Topics
            client.subscribe(ESP32_WILDCARD_TOPIC)
            log.info(f"Subscribed : {ESP32_WILDCARD_TOPIC}")

            for t in STATUS_TOPICS:
                client.subscribe(t)
            for t in ACK_TOPICS:
                client.subscribe(t)
            for t in SENSOR_TOPICS:
                client.subscribe(t)

            # Embedded Devices Subscriptions
            client.subscribe(ROBOT_ACK_TOPIC)
            client.subscribe(ROBOT_STATUS_TOPIC)
            client.subscribe(WHEELCHAIR_ACK_TOPIC)
            client.subscribe(WHEELCHAIR_STATUS_TOPIC)

            # PC Agent Subscriptions (Target Nodes)
            client.subscribe(PC_AGENT_STATUS_TOPIC)
            client.subscribe(PC_AGENT_ACK_TOPIC)
            client.subscribe(PC_AGENT_ERROR_TOPIC)
            log.info("All IoT, Embedded, and PC Agent subscriptions initialized")
        else:
            self._connected = False
            log.error(f"MQTT Connection Failed : {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        log.warning(f"MQTT Disconnected : {rc}")

    def _on_message(self, client, userdata, msg):
        payload = msg.payload.decode(errors="replace")

        log.debug(f"MQTT RX [{msg.topic}] : {payload}")

        try:
            data = json.loads(payload)
        except Exception:
            data = payload

        # Firmware may publish JSON or plain text; identify nodes from the topic.
        parts = msg.topic.split("/")
        if len(parts) == 3 and parts[0] in ("robotcar", "wheelchair"):
            domain, device_id, channel = parts
            state = ROBOT_CAR_STATE if domain == "robotcar" else WHEELCHAIR_STATE
            configured = read_config()["car_topic" if domain == "robotcar" else "chair_topic"].split("/")[1]
            if device_id != configured:
                ONLINE_DEVICES[device_id] = {"domain": domain, "status": "DISCOVERED", "_last_seen": time.time()}
                return
            value = str(data.get("status", "UNKNOWN") if isinstance(data, dict) else data).strip().upper()
            state.update(device_id=device_id, last_seen=time.time())
            if channel == "status":
                state.update(status=value, online=value.split()[-1] in ("ONLINE", "CONNECTED", "READY") if value else False)
                ONLINE_DEVICES[device_id] = {"domain": domain, "status": value, "_last_seen": time.time()}
            elif channel == "ack":
                state["last_ack"] = data
                LAST_ACKS[device_id] = {"ack": data, "_timestamp": time.time()}
            if isinstance(data, dict):
                return

        if isinstance(data, dict):
            # Check PC Agent topics: masterhub/devices/{device_id}/{channel}
            if msg.topic.startswith("masterhub/devices/"):
                parts = msg.topic.split("/")
                if len(parts) >= 4:
                    pc_device_id = parts[2]
                    channel = parts[3]
                    if channel == "status":
                        status_val = str(data.get("status", "")).lower()
                        if status_val == "offline" or data.get("command_id") == "lwt" or (getattr(msg, "retain", False) and isinstance(data.get("timestamp"), (int, float)) and time.time() - data["timestamp"] > 90):
                            device_registry.update_status(pc_device_id, "OFFLINE")
                            if pc_device_id in ONLINE_DEVICES:
                                ONLINE_DEVICES[pc_device_id]["status"] = "OFFLINE"
                        else:
                            caps = None
                            if isinstance(data.get("params"), dict):
                                caps = data.get("params", {}).get("capabilities")
                            device_registry.update_status(pc_device_id, "ONLINE", capabilities=caps)
                            ONLINE_DEVICES[pc_device_id] = {
                                "device_id": pc_device_id,
                                "domain": "desktop",
                                "status": "ONLINE",
                                "_last_seen": time.time(),
                            }
                        log.info(f"PC Agent Status Updated : {pc_device_id} -> {data}")
                    elif channel == "ack":
                        LAST_ACKS[pc_device_id] = data
                        log.info(f"PC Agent ACK Received from {pc_device_id}: {data}")
                    elif channel == "error":
                        LAST_ACKS[pc_device_id] = {"error": data}
                        log.warning(f"PC Agent ERROR from {pc_device_id}: {data}")

                return

            # Resolve device ID from either camelCase (deviceId) or snake_case (device_id)
            device_id = data.get("deviceId") or data.get("device_id")
            if not device_id and "esp32" in msg.topic:
                device_id = "esp32"

            if device_id:
                # 1. Update Online Devices / Status
                if msg.topic.endswith("/status"):
                    ONLINE_DEVICES[device_id] = data
                    ONLINE_DEVICES[device_id]["_last_seen"] = time.time()
                    if "states" in data and isinstance(data["states"], dict):
                        DEVICE_STATES[device_id] = data["states"]
                    if "lastSensor" in data and isinstance(data["lastSensor"], dict):
                        LATEST_SENSORS[device_id] = data["lastSensor"]
                    if "esp32" in msg.topic:
                        ONLINE_DEVICES["esp32"] = data
                        if "states" in data and isinstance(data["states"], dict):
                            DEVICE_STATES["esp32"] = data["states"]
                        if "lastSensor" in data and isinstance(data["lastSensor"], dict):
                            LATEST_SENSORS["esp32"] = data["lastSensor"]
                    log.info(f"IoT Device Status Updated : {device_id} -> {data.get('states')}")

                # 2. Update ACKs
                elif msg.topic.endswith("/ack"):
                    LAST_ACKS[device_id] = data
                    # Update local state if acknowledged
                    if device_id not in DEVICE_STATES:
                        DEVICE_STATES[device_id] = {}
                    if "light" in data:
                        DEVICE_STATES[device_id]["light"] = data["light"]
                    if "fan" in data:
                        DEVICE_STATES[device_id]["fan"] = data["fan"]
                    if "pump" in data:
                        DEVICE_STATES[device_id]["pump"] = data["pump"]
                    if "esp32" in msg.topic:
                        LAST_ACKS["esp32"] = data
                        if "esp32" not in DEVICE_STATES:
                            DEVICE_STATES["esp32"] = {}
                        if "light" in data:
                            DEVICE_STATES["esp32"]["light"] = data["light"]
                        if "fan" in data:
                            DEVICE_STATES["esp32"]["fan"] = data["fan"]
                        if "pump" in data:
                            DEVICE_STATES["esp32"]["pump"] = data["pump"]
                    log.info(f"IoT ACK Received from {device_id}: {data.get('command')} -> {data.get('result')}")

                # 3. Update Sensors (LoRa Telemetry)
                elif msg.topic.endswith("/sensor"):
                    LATEST_SENSORS[device_id] = data
                    LATEST_SENSORS[device_id]["_timestamp"] = time.time()
                    if "esp32" in msg.topic:
                        LATEST_SENSORS["esp32"] = data
                    log.info(f"LoRa Sensor Packet from {device_id}: distance={data.get('distance')} float={data.get('float')} rssi={data.get('rssi')}")

        else:
            # Handle raw text payloads from Embedded Devices (ESP32-C6 Robot Car / Wheelchair)
            parts = msg.topic.split("/")
            if len(parts) >= 3 and parts[0] in ("robotcar", "wheelchair"):
                domain = parts[0]
                device_id = parts[1]
                channel = parts[2]
                raw_text = str(data).strip()

                if domain == "robotcar":
                    ROBOT_CAR_STATE["device_id"] = device_id
                    ROBOT_CAR_STATE["last_seen"] = time.time()

                    if channel == "status":
                        ROBOT_CAR_STATE["status"] = raw_text
                        if raw_text == "ONLINE":
                            ROBOT_CAR_STATE["online"] = True
                            ONLINE_DEVICES[device_id] = {"domain": domain, "status": "ONLINE", "_last_seen": time.time()}
                        elif raw_text == "OFFLINE":
                            ROBOT_CAR_STATE["online"] = False
                            if device_id in ONLINE_DEVICES:
                                ONLINE_DEVICES[device_id]["status"] = "OFFLINE"
                        elif "OBSTACLE" in raw_text or "BLOCKED" in raw_text:
                            ROBOT_CAR_STATE["obstacle_alert"] = raw_text
                            ROBOT_CAR_STATE["motion_active"] = False
                        elif "MOTION COMPLETE" in raw_text or "STOP" in raw_text:
                            ROBOT_CAR_STATE["motion_active"] = False
                        log.info(f"Robot Car [{device_id}] Status: {raw_text}")

                    elif channel == "ack":
                        ROBOT_CAR_STATE["last_ack"] = raw_text
                        LAST_ACKS[device_id] = {"domain": domain, "ack": raw_text, "_timestamp": time.time()}
                        if "OBSTACLE" in raw_text or "BLOCKED" in raw_text:
                            ROBOT_CAR_STATE["obstacle_alert"] = raw_text
                            ROBOT_CAR_STATE["motion_active"] = False
                        elif "EXECUTED" in raw_text:
                            ROBOT_CAR_STATE["obstacle_alert"] = None
                            ROBOT_CAR_STATE["motion_active"] = "STOP" not in raw_text
                        log.info(f"Robot Car [{device_id}] ACK: {raw_text}")

                elif domain == "wheelchair":
                    WHEELCHAIR_STATE["device_id"] = device_id
                    WHEELCHAIR_STATE["last_seen"] = time.time()
                    if channel == "status":
                        WHEELCHAIR_STATE["status"] = raw_text
                        if raw_text == "ONLINE":
                            WHEELCHAIR_STATE["online"] = True
                            ONLINE_DEVICES[device_id] = {"domain": domain, "status": "ONLINE", "_last_seen": time.time()}
                        elif raw_text == "OFFLINE":
                            WHEELCHAIR_STATE["online"] = False
                    elif channel == "ack":
                        WHEELCHAIR_STATE["last_ack"] = raw_text
                        LAST_ACKS[device_id] = {"domain": domain, "ack": raw_text, "_timestamp": time.time()}
                    log.info(f"Wheelchair [{device_id}] {channel.upper()}: {raw_text}")

        # Call custom callback if registered
        if self.message_callback:
            try:
                self.message_callback(msg.topic, data)
            except Exception as e:
                log.error(f"Message Callback Error : {e}")

    # -------------------------------------------------
    # REGISTER CALLBACK
    # -------------------------------------------------

    def set_message_callback(self, callback):
        self.message_callback = callback

    # -------------------------------------------------
    # CONNECTION
    # -------------------------------------------------

    def connect(self, timeout=5):
        with self._lock:
            if self._connected:
                return True

            try:
                self._client.connect(
                    self.host,
                    self.port,
                    KEEPALIVE
                )
                self._client.loop_start()
            except Exception as exc:
                log.error(f"MQTT connect error: {exc}")
                return False

        waited = 0.0
        while not self._connected and waited < timeout:
            time.sleep(0.1)
            waited += 0.1

        return self._connected

    def disconnect(self):
        with self._lock:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            log.info("MQTT Client Disconnected")

    # -------------------------------------------------
    # PUBLISH
    # -------------------------------------------------

    def publish(
        self,
        payload,
        topic=None,
        qos=1,
        retry=1
    ):
        target_topic = topic or self.topic

        if not self._connected:
            if not self.connect():
                log.error("MQTT Not Connected")
                return False

        try:
            result = self._client.publish(
                target_topic,
                payload,
                qos=qos
            )
            result.wait_for_publish(timeout=5)

            if result.is_published():
                log.info(f"Published -> {target_topic} : {payload}")
                return True

            if retry > 0:
                return self.publish(
                    payload,
                    topic,
                    qos,
                    retry - 1
                )

            return False

        except Exception as e:
            log.error(f"MQTT publish exception: {e}")
            if retry > 0:
                return self.publish(
                    payload,
                    topic,
                    qos,
                    retry - 1
                )
            return False

    def publish_json(
        self,
        data,
        topic=None,
        qos=1
    ):
        return self.publish(
            json.dumps(data),
            topic,
            qos
        )

    def ping_esp32(self):
        return self.publish("PING", topic="iot/esp32/ping", qos=0)

    def send_pc_agent_command(
        self,
        target_device_id: str,
        domain: str,
        action: str,
        params: dict = None,
        command_id: str = None,
    ) -> dict:
        """
        Dispatches an action command envelope to a remote target PC node running pc_agent.
        Topic schema: masterhub/devices/{target_device_id}/command
        Wire envelope matches protocol/envelope.py in pc_agent.
        """
        import uuid
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
        topic = f"masterhub/devices/{target_device_id}/command"
        published = self.publish_json(envelope, topic=topic, qos=1)
        return {
            "success": published,
            "command_id": cmd_id,
            "target": target_device_id,
            "domain": domain,
            "action": action,
            "envelope": envelope,
            "transport": "mqtt",
            "topic": topic,
            "error": None if published else "MQTT publish failed (broker unreachable or not connected)",
        }


mqtt_service = MQTTService()


def get_first_online_device():
    """Return the first active registered device ID or default to 'esp32'."""
    if ONLINE_DEVICES:
        return next(iter(ONLINE_DEVICES))
    return "esp32"


def get_all_online_devices():
    return ONLINE_DEVICES


def get_all_device_states():
    return DEVICE_STATES


def get_all_sensor_data():
    return LATEST_SENSORS


def get_robot_car_state():
    return ROBOT_CAR_STATE


def get_wheelchair_state():
    return WHEELCHAIR_STATE