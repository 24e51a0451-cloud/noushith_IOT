'''
embeded

import paho.mqtt.client as mqtt
import time
from datetime import datetime

# ---------------- MQTT Configuration ---------------- #

BROKER = "52.21.249.6"
PORT = 1883

DEVICE_ID = "98:A3:16:BF:2C:C0"

CONTROL_TOPIC = f"robotcar/{DEVICE_ID}/control"
ACK_TOPIC = f"robotcar/{DEVICE_ID}/ack"
STATUS_TOPIC = f"robotcar/{DEVICE_ID}/status"

COMMANDS = [
    "LIFTCARFORWARD",
    "LIFTCARBACKWARD",
    "LIFTCARLEFT",
    "LIFTCARRIGHT",
    "LIFTCARLEFT360",
    "LIFTCARRIGHT360",
    "LIFTCARSTOP"
]

# ---------------- Callbacks ---------------- #

def timestamp():
    return datetime.now().strftime("%H:%M:%S")


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"\n[{timestamp()}] Connected Successfully")

        client.subscribe(ACK_TOPIC)
        client.subscribe(STATUS_TOPIC)

        print("Subscribed to:")
        print(" ", ACK_TOPIC)
        print(" ", STATUS_TOPIC)
        print()

    else:
        print("Connection Failed:", rc)


def on_message(client, userdata, msg):
    print(f"[{timestamp()}] {msg.topic}")
    print("Payload :", msg.payload.decode())
    print("-" * 50)


# ---------------- Main ---------------- #

client = mqtt.Client(client_id="PythonTester")

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)

client.loop_start()

time.sleep(2)

while True:

    print("\n========= Robot Command Menu =========")
    print("1. Forward")
    print("2. Backward")
    print("3. Left")
    print("4. Right")
    print("5. Left 360")
    print("6. Right 360")
    print("7. Stop")
    print("8. Send ALL Commands")
    print("0. Exit")

    choice = input("\nEnter Choice : ")

    if choice == "0":
        break

    elif choice == "8":

        for cmd in COMMANDS:
            print(f"\nPublishing : {cmd}")
            client.publish(CONTROL_TOPIC, cmd)
            time.sleep(2)

    elif choice in ["1", "2", "3", "4", "5", "6", "7"]:

        cmd = COMMANDS[int(choice)-1]

        print(f"\nPublishing : {cmd}")
        client.publish(CONTROL_TOPIC, cmd)

    else:
        print("Invalid Choice")

client.loop_stop()
client.disconnect()


Yes. Since your `mqtt_service.py` **already has a `publish()` function**, you **do not need to change much**. The only thing you need is the ability to publish **plain text commands** (like your tester) while keeping **`publish_json()`** for your IoT devices.

The good news is that your current `publish()` **already publishes plain text**:

```python
mqtt_service.publish("LIFTCARFORWARD", topic="robotcar/98:A3:16:BF:2C:C0/control")
```

will send exactly:

```
LIFTCARFORWARD
```

So you **don't need another publish function**.

---

# Updated `EmbeddedHandler`

Replace your `actions/embedded/handler.py` with the following.

```python
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
    "CHAIRFORWARD",
    "CHAIRBACKWARD",
    "CHAIRLEFT",
    "CHAIRRIGHT",
    "CHAIRSTOP",
}

_CAR_ACTIONS = {
    "LIFTCARFORWARD",
    "LIFTCARBACKWARD",
    "LIFTCARLEFT",
    "LIFTCARRIGHT",
    "LIFTCARLEFT360",
    "LIFTCARRIGHT360",
    "LIFTCARSTOP",
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

        mapping = self._map.get(action)

        if mapping:
            params = dict(params)
            params.setdefault("mapping", mapping)

        if action in _CAR_ACTIONS:
            return self._publish_robot_car(action)

        if action in _CHAIR_ACTIONS:
            return self._publish_wheelchair(action)

        log.warning(f"Unknown Embedded Action : {action}")

        return {
            "success": False,
            "domain": "embedded",
            "action": action,
            "error": "Unknown Action"
        }

    # ---------------------------------------------------------
    # Robot Car
    # ---------------------------------------------------------

    def _publish_robot_car(self, action):

        topic = f"robotcar/{ROBOT_CAR_DEVICE_ID}/control"

        ok = mqtt_service.publish(
            payload=action,
            topic=topic
        )

        if not ok:

            return {
                "success": False,
                "domain": "embedded",
                "device": "robot_car",
                "action": action,
                "error": "MQTT Publish Failed"
            }

        log.info(f"Robot Car Command Published : {action}")

        return {
            "success": True,
            "domain": "embedded",
            "device": "robot_car",
            "action": action,
            "topic": topic,
            "payload": action
        }

    # ---------------------------------------------------------
    # Wheelchair
    # ---------------------------------------------------------

    def _publish_wheelchair(self, action):

        topic = f"wheelchair/{WHEELCHAIR_DEVICE_ID}/control"

        ok = mqtt_service.publish(
            payload=action,
            topic=topic
        )

        if not ok:

            return {
                "success": False,
                "domain": "embedded",
                "device": "wheelchair",
                "action": action,
                "error": "MQTT Publish Failed"
            }

        log.info(f"Wheelchair Command Published : {action}")

        return {
            "success": True,
            "domain": "embedded",
            "device": "wheelchair",
            "action": action,
            "topic": topic,
            "payload": action
        }


embedded_handler = EmbeddedHandler()
```

---

# Now update `mqtt_service.py`

Keep everything exactly the same.

Only add these topic subscriptions.

At the top:

```python
ROBOT_ACK_TOPIC = "robotcar/+/ack"
ROBOT_STATUS_TOPIC = "robotcar/+/status"

WHEELCHAIR_ACK_TOPIC = "wheelchair/+/ack"
WHEELCHAIR_STATUS_TOPIC = "wheelchair/+/status"
```

Then inside `_on_connect()` add:

```python
client.subscribe(ROBOT_ACK_TOPIC)
log.info(f"Subscribed : {ROBOT_ACK_TOPIC}")

client.subscribe(ROBOT_STATUS_TOPIC)
log.info(f"Subscribed : {ROBOT_STATUS_TOPIC}")

client.subscribe(WHEELCHAIR_ACK_TOPIC)
log.info(f"Subscribed : {WHEELCHAIR_ACK_TOPIC}")

client.subscribe(WHEELCHAIR_STATUS_TOPIC)
log.info(f"Subscribed : {WHEELCHAIR_STATUS_TOPIC}")
```

---

## Final Architecture

```
BCI Headset
      │
      ▼
Gesture
      │
      ▼
Master Hub
      │
      ▼
Embedded Handler
      │
      ├──────────────┐
      ▼              ▼
Robot Car        Wheelchair
      │              │
MQTT Publish     MQTT Publish
      │              │
robotcar/<MAC>/control
wheelchair/<MAC>/control
      │
      ▼
ESP32
      │
      ▼
Motor Driver
      │
      ▼
Robot Movement
```

This design keeps your existing IoT JSON communication unchanged while adding support for the robot car and wheelchair using the same plain-text MQTT protocol as your test program.
'''