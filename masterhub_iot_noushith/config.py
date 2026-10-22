"""
Global configuration for MasterHub
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# CHROME / BROWSER CONFIGURATION
# ==========================================
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_PROFILE = "Profile 5"
CHROME_ARGS = [
    f"--profile-directory={CHROME_PROFILE}"
]

# ==========================================
# MQTT CONFIGURATION
# ==========================================
MQTT_PRIMARY_BROKER = "52.21.249.6"
MQTT_FALLBACK_BROKER = "broker.emqx.io"
MQTT_BROKER = MQTT_PRIMARY_BROKER
MQTT_PORT = 1883
MQTT_QOS = 1
MQTT_KEEPALIVE = 60
CLIENT_ID_PREFIX = "MASTERHUB"

from services.mobile_topics import (
    MOBILE_DEVICE_ID, TOPIC_DISCOVERY, TOPIC_DEVICES_REGISTER, TOPIC_REGISTER_ACK,
    TOPIC_COMMAND, TOPIC_ACK, TOPIC_STATUS, TOPIC_HEARTBEAT, get_device_topics,
)

# ==========================================
# COMMAND MAPPING (aligned with Android app)
# ==========================================
COMMAND_MAP = {
    "Right": "Right",
    "Right_jiosaavn": "Right_jiosaavn",
    "Right_Play_Pause": "Right_Play_Pause",
    "Right_Next_Song": "Right_Next_Song",
    "Right_Previous_Song": "Right_Previous_Song",
    "Right_Volume_Up": "Right_Volume_Up",
    "Right_Volume_Down": "Right_Volume_Down",
    "Right_Search_Playlist": "Right_Search_Playlist",
    "Drop": "Drop",
    "Right_Return_to_Home": "Right_Return_to_Home",
    "Right_Close_App": "Right_Close_App",
    "Close_App": "Right_Close_App",
    "Close_JioSaavn": "Right_Close_App",
    "SEARCH": "SEARCH",
    "type_query": "type_query",
    # Raw primitives & action aliases
    "LEFT": "Right_Play_Pause",
    "PUSH": "Right_Next_Song",
    "PULL": "Right_Previous_Song",
    "RIGHT+PUSH": "Right_Volume_Up",
    "RIGHT+PULL": "Right_Volume_Down",
    "PUSH+RIGHT": "Right_Close_App",
    "Back to Level 2": "Right_Close_App",
    "back_to_level_2": "Right_Close_App",
    "Play / Pause": "Right_Play_Pause",
    "Next Track": "Right_Next_Song",
    "Previous Track": "Right_Previous_Song",
    "Volume Up": "Right_Volume_Up",
    "Volume Down": "Right_Volume_Down",
    "Search": "Right_Search_Playlist",
    "Search Album/Playlist": "Right_Search_Playlist",
}

DISPLAY_LABELS = {
    "Right": "Right Gesture",
    "Right_jiosaavn": "Open JioSaavn",
    "Right_Play_Pause": "Play / Pause",
    "Right_Next_Song": "Next Track",
    "Right_Previous_Song": "Previous Track",
    "Right_Volume_Up": "Volume +",
    "Right_Volume_Down": "Volume -",
    "Right_Search_Playlist": "Search Playlist",
    "Drop": "Return to Home",
    "Right_Return_to_Home": "Return to Home",
    "Right_Close_App": "Close JioSaavn",
    "SEARCH": "Search",
    "type_query": "Search Query",
    "LEFT": "Play / Pause",
    "PUSH": "Next Track",
    "PUSH+RIGHT": "Back to Level 2",
    "PULL": "Previous Track",
    "RIGHT+PUSH": "Volume +",
    "RIGHT+PULL": "Volume -",
}

# ==========================================
# THRESHOLDS
# ==========================================
CONFIDENCE_THRESHOLD = 0.80
TARGET_DOMAIN = "AI_ML"

DEBUG_MODE = True
