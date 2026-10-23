"""Shared JioSaavn MQTT topic contract."""
import os
from dotenv import load_dotenv

load_dotenv()

# Only the dedicated mobile contract is used for JioSaavn.
MOBILE_DEVICE_ID = os.environ.get("BCI_MOBILE_DEVICE_ID", "MOBILE_001")
TOPIC_DISCOVERY = "masterhub/mobile/register"
TOPIC_DEVICES_REGISTER = TOPIC_DISCOVERY
TOPIC_REGISTER_ACK = "masterhub/mobile/{device_uuid}/register_ack"


def get_device_topics(device_id):
    """Build the four device channels; registration uses the hardware UUID."""
    import re
    if not isinstance(device_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{3,64}", device_id):
        raise ValueError("Invalid mobile device ID")
    prefix = "masterhub/mobile/" + device_id
    return {name: prefix + "/" + name for name in ("command", "ack", "status", "heartbeat")}


_mobile_topics = get_device_topics(MOBILE_DEVICE_ID)
TOPIC_COMMAND = _mobile_topics["command"]
TOPIC_ACK = _mobile_topics["ack"]
TOPIC_STATUS = _mobile_topics["status"]
TOPIC_HEARTBEAT = _mobile_topics["heartbeat"]

