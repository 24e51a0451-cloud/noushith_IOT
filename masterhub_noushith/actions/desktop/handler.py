"""
actions/desktop/handler.py
----------------------------
Dispatch table for the desktop domain. Maps action identifiers (as
defined in mappings/command_map.json) to the actual automation function
to call. The Engine calls DesktopHandler.execute(action, params) and
never needs to know which specific module/function implements it.
"""

import json
import os

from actions.desktop import notepad, chrome, youtube, system_apps, gmail
from core.devices import device_registry
from services.logger_service import get_logger
from services.mqtt_service import mqtt_service
from services.usb_service import usb_service

log = get_logger("actions.desktop")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DESKTOP_MAP_PATH = os.path.join(_BASE_DIR, "mappings", "desktop_map.json")


class DesktopHandler:
    def __init__(self):
        self._map = self._load_map()
        # action_id -> callable(params: dict) -> dict
        self._dispatch = {
            # Notepad
            "open_notepad": lambda p: notepad.open_notepad(),
            "notepad_open": lambda p: notepad.open_notepad(),
            "write_notepad": lambda p: notepad.write_notepad(text=p.get("text", "")),
            "notepad_write": lambda p: notepad.write_notepad(text=p.get("text", "")),
            "save_notepad": lambda p: notepad.save_notepad(filename=p.get("filename", "masterhub_note.txt")),
            "notepad_save": lambda p: notepad.save_notepad(filename=p.get("filename", "masterhub_note.txt")),

            # Calculator & Apps
            "open_calculator": lambda p: system_apps.open_calculator(),
            "calculator_open": lambda p: system_apps.open_calculator(),
            "calc_open": lambda p: system_apps.open_calculator(),

            "chrome_scroll_up": lambda p: chrome.scroll_chrome("up"),
            "chrome_scroll_down": lambda p: chrome.scroll_chrome("down"),

            # Chrome
            "open_chrome": lambda p: chrome.open_chrome(),
            "chrome_open_article": lambda p: chrome.open_chrome(),
            "chrome_open": lambda p: chrome.open_chrome(),
            "close_chrome": lambda p: chrome.close_chrome(),
            "chrome_close": lambda p: chrome.close_chrome(),
            "search_chrome": lambda p: chrome.search_chrome(query=p.get("query", "")),
            "chrome_search": lambda p: chrome.search_chrome(query=p.get("query", "")),
            "previous_tab": lambda p: system_apps.previous_tab(),
            "next_tab": lambda p: system_apps.next_tab(),

            # YouTube
            "open_youtube": lambda p: youtube.open_youtube(),
            "youtube_open": lambda p: youtube.open_youtube(),
            "search_youtube": lambda p: youtube.search_youtube(query=p.get("query", "")),
            "youtube_search": lambda p: youtube.search_youtube(query=p.get("query", "")),
            "play_youtube": lambda p: youtube.play_youtube(query=p.get("query", "")),
            "youtube_play": lambda p: youtube.play_youtube(query=p.get("query", "")),
            "youtube_next": lambda p: youtube.next_youtube(),
            "youtube_previous": lambda p: youtube.previous_youtube(),
            "youtube_volume_up": lambda p: youtube.youtube_volume_up(),
            "youtube_volume_down": lambda p: youtube.youtube_volume_down(),
            "youtube_pause": lambda p: youtube.pause_youtube(),
            "youtube_mute": lambda p: youtube.youtube_mute(),

            # Gmail
            "open_gmail": lambda p: gmail.open_gmail(),
            "gmail_open": lambda p: gmail.open_gmail(),
            "compose_gmail": lambda p: gmail.compose_gmail(to=p.get("to", ""), subject=p.get("subject", ""), body=p.get("body", "")),
            "gmail_compose": lambda p: gmail.compose_gmail(to=p.get("to", ""), subject=p.get("subject", ""), body=p.get("body", "")),
            "search_gmail": lambda p: gmail.search_gmail(query=p.get("query", "")),
            "gmail_search": lambda p: gmail.search_gmail(query=p.get("query", "")),
            "send_gmail": lambda p: gmail.send_gmail(),
            "gmail_send": lambda p: gmail.send_gmail(),

            # Outlook & Calendar
            "open_calendar": lambda p: system_apps.open_calendar(),
        }

    def _load_map(self):
        try:
            with open(_DESKTOP_MAP_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return {k: v for k, v in data.items() if not k.startswith("_")}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def execute(self, action: str, params: dict = None) -> dict:
        params = params or {}
        mapping = self._map.get(action)
        if mapping is not None:
            params = dict(params)
            params.setdefault("mapping", mapping)

        # Check target node for remote routing (PC_001, PC_002, PC_003, etc.)
        target = params.get("target") or params.get("target_node") or device_registry.get_active_target()
        if target and str(target).strip().lower() not in ("local host", "local", "localhost", "127.0.0.1", ""):
            target_str = str(target).strip()
            device = device_registry.get(target_str)
            transport = (device.get("transport") if device else "mqtt") or "mqtt"
            transport = str(transport).strip().lower()

            if transport in ("usb", "serial", "uart"):
                log.info(f"Routing desktop action '{action}' to node '{target_str}' via USB Serial")
                result = usb_service.send_command(
                    target_device_id=target_str,
                    domain="desktop",
                    action=action,
                    params=params,
                )
            else:
                log.info(f"Routing desktop action '{action}' to remote node '{target_str}' via MQTT")
                result = mqtt_service.send_pc_agent_command(
                    target_device_id=target_str,
                    domain="desktop",
                    action=action,
                    params=params,
                )
            result.setdefault("domain", "desktop")
            result.setdefault("mapping", mapping)
            return result

        fn = self._dispatch.get(action)
        if fn is None:
            log.warning(f"No desktop handler registered for action '{action}'")
            return {"success": False, "error": f"Unknown desktop action: '{action}'"}

        try:
            result = fn(params)
            result.setdefault("domain", "desktop")
            result.setdefault("mapping", mapping)
            return result
        except Exception as exc:
            log.error(f"Desktop action '{action}' failed: {exc}")
            return {"success": False, "domain": "desktop", "action": action, "error": str(exc)}


desktop_handler = DesktopHandler()
