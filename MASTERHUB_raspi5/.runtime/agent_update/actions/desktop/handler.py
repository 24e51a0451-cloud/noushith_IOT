"""
actions/desktop/handler.py
----------------------------
Dispatch table for the desktop domain, executed locally on THIS target
Windows PC once a COMMAND envelope with domain="desktop" arrives from
MasterHub. Action identifiers match MasterHub's mappings/desktop_map.json
/ actions/desktop/handler.py exactly - discovered from the source ZIP,
not invented:

    open_notepad, write_notepad, save_notepad, open_calculator,
    open_chrome, close_chrome, search_chrome, previous_tab, next_tab,
    open_youtube, search_youtube, play_youtube, youtube_next,
    youtube_previous, youtube_volume_up, youtube_volume_down,
    youtube_pause, youtube_mute, open_calendar, open_gmail
"""

from actions.desktop import notepad, chrome, youtube, system_apps, gmail
from common.logger import get_logger
import time

log = get_logger("actions.desktop")


def _ping_agent(params: dict) -> dict:
    """Safe, side-effect-free health check (project brief section 26 -
    "a safe test command such as ping_agent"). Deliberately does NOT
    touch pyautogui/the display, so it also works to verify the wire
    protocol end-to-end (HELLO -> COMMAND -> ACK) on a headless test
    box that has no real desktop to automate."""
    return {"success": True, "domain": "desktop", "action": "ping_agent", "pong": True, "timestamp": time.time()}


def _get_agent_status(params: dict) -> dict:
    """Same spirit as _ping_agent - a safe introspection action for the
    real-broker MQTT smoke test (scripts/test_mqtt_connection.py)."""
    return {"success": True, "domain": "desktop", "action": "get_agent_status", "status": "alive", "timestamp": time.time()}


class DesktopHandler:
    def __init__(self):
        self._dispatch = {
            "open_notepad": lambda p: notepad.open_notepad(),
            "write_notepad": lambda p: notepad.write_notepad(text=p.get("text", "")),
            "save_notepad": lambda p: notepad.save_notepad(filename=p.get("filename", "masterhub_note.txt")),

            "open_calculator": lambda p: system_apps.open_calculator(),

            "open_chrome": lambda p: chrome.open_chrome(),
            "close_chrome": lambda p: chrome.close_chrome(),
            "search_chrome": lambda p: chrome.search_chrome(query=p.get("query", "")),
            "previous_tab": lambda p: system_apps.previous_tab(),
            "next_tab": lambda p: system_apps.next_tab(),

            "open_youtube": lambda p: youtube.open_youtube(),
            "search_youtube": lambda p: youtube.search_youtube(query=p.get("query", "")),
            "play_youtube": lambda p: youtube.play_youtube(query=p.get("query", "")),
            "youtube_next": lambda p: youtube.next_youtube(),
            "youtube_previous": lambda p: youtube.previous_youtube(),
            "youtube_volume_up": lambda p: youtube.youtube_volume_up(),
            "youtube_volume_down": lambda p: youtube.youtube_volume_down(),
            "youtube_mute": lambda p: youtube.youtube_mute(),
            "search_gmail": lambda p: gmail.search_gmail(query=p.get("query", "")),
            "gmail_search": lambda p: gmail.search_gmail(query=p.get("query", "")),
            "send_gmail": lambda p: gmail.send_gmail(),
            "gmail_send": lambda p: gmail.send_gmail(),
            "youtube_pause": lambda p: youtube.pause_youtube(),

            "open_calendar": lambda p: system_apps.open_calendar(),
            "open_gmail": lambda p: gmail.open_gmail(),
            "compose_gmail": lambda p: gmail.compose_gmail(to=p.get("to", ""), subject=p.get("subject", ""), body=p.get("body", "")),
            "gmail_open": lambda p: gmail.open_gmail(),
            "gmail_compose": lambda p: gmail.compose_gmail(to=p.get("to", ""), subject=p.get("subject", ""), body=p.get("body", "")),

            # Safe, non-destructive test/health-check actions (section 26) -
            # never touch pyautogui, so they also work headless.
            "ping_agent": _ping_agent,
            "get_agent_status": _get_agent_status,
        }

    def execute(self, action: str, params: dict = None) -> dict:
        params = params or {}
        fn = self._dispatch.get(action)
        if fn is None:
            log.warning(f"No desktop handler registered for action '{action}'")
            return {"success": False, "error": f"Unknown desktop action: '{action}'"}

        try:
            result = fn(params)
            result.setdefault("domain", "desktop")
            return result
        except Exception as exc:
            log.error(f"Desktop action '{action}' failed: {exc}")
            return {"success": False, "domain": "desktop", "action": action, "error": str(exc)}


desktop_handler = DesktopHandler()
