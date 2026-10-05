"""
actions/ai_ml/handler.py
---------------------------
AI/ML domain: media control system. Uses pyautogui's media key support
where possible (these map to real OS media keys: play/pause, next/prev
track, volume up/down), so they control whatever app currently owns
media focus (Spotify, YouTube tab, Windows Media Player, etc.) without
needing a specific app integration.

Album search is a stub that would call out to a music API (Spotify/
Last.fm/etc.) in a full implementation — kept here as an extension point.
"""

import json
import os

#from fastapi import params

from core.devices import device_registry
from services.logger_service import get_logger
from services.mqtt_service import mqtt_service
from services.usb_service import usb_service

log = get_logger("actions.ai_ml")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_AI_ML_MAP_PATH = os.path.join(_BASE_DIR, "mappings", "ai_ml_map.json")

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    PYAUTOGUI_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    PYAUTOGUI_AVAILABLE = False
    log.warning(f"pyautogui not available in this environment: {exc}")


def _require_pyautogui():
    if not PYAUTOGUI_AVAILABLE:
        raise RuntimeError(
            "pyautogui is not available in this environment. "
            "Media key automation only works on a machine with a display."
        )


def _safe_press(key: str):
    _require_pyautogui()
    try:
        pyautogui.press(key)
    except Exception as exc:
        log.warning(f"pyautogui.press('{key}') failed: {exc}")


class AIMLHandler:
    def __init__(self):
        self._map = self._load_map()
        self._dispatch = {
            "open_jiosaavn": self._open_jiosaavn,
            "search_jiosaavn": self._search_jiosaavn,
            "play": self._play_pause,
            "pause": self._play_pause,
            "next_track": self._next_track,
            "previous_track": self._previous_track,
            "volume_up": self._volume_up,
            "volume_down": self._volume_down,
            "album_search": self._album_search,
            "mute": self._mute,
        }

    def _load_map(self):
        try:
            with open(_AI_ML_MAP_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return {k: v for k, v in data.items() if not k.startswith("_")}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def execute(self, action: str, params: dict = None) -> dict:
        print("=" * 50)
        print("ACTION RECEIVED:", action)

        params = params or {}

        if action.startswith('mobile_jiosaavn_'):
            from actions.media_jiosaavn_mobile import execute
            return execute(action, params)

        # Check target node for remote routing (PC_001, PC_002, PC_003, etc.)
        target = params.get("target") or params.get("target_node") or device_registry.get_active_target()
        if target and str(target).strip().lower() not in ("local host", "local", "localhost", "127.0.0.1", ""):
            target_str = str(target).strip()
            device = device_registry.get(target_str)
            transport = (device.get("transport") if device else "mqtt") or "mqtt"
            transport = str(transport).strip().lower()

            if transport in ("usb", "serial", "uart"):
                log.info(f"Routing AI/ML action '{action}' to node '{target_str}' via USB Serial")
                result = usb_service.send_command(
                    target_device_id=target_str,
                    domain="ai_ml",
                    action=action,
                    params=params,
                )
            else:
                log.info(f"Routing AI/ML action '{action}' to remote node '{target_str}' via MQTT")
                result = mqtt_service.send_pc_agent_command(
                    target_device_id=target_str,
                    domain="ai_ml",
                    action=action,
                    params=params,
                )
            result.setdefault("domain", "ai_ml")
            result.setdefault("action", action)
            return result

        print("Dispatch Keys:", list(self._dispatch.keys()))

        fn = self._dispatch.get(action)

        print("Function Found:", fn)

        if fn is None:
            print("NO FUNCTION FOUND!")
            return {
                "success": False,
                "error": f"Unknown action: {action}"
            }

        print("CALLING FUNCTION...")
        result = fn(params)
        print("FUNCTION FINISHED")

        result.setdefault("domain", "ai_ml")
        result.setdefault("action", action)

        return result
   
    # ---------- handlers ----------

    def _open_jiosaavn(self, params: dict) -> dict:
        from actions.desktop.gmail import open_url_robust
        return {"success": open_url_robust("https://www.jiosaavn.com/"), "url": "https://www.jiosaavn.com/"}

    def _search_jiosaavn(self, params: dict) -> dict:
        from urllib.parse import quote
        from actions.desktop.gmail import open_url_robust
        query = str(params.get('query', '')).strip()
        if not query:
            raise ValueError('Enter a JioSaavn search query.')
        url = 'https://www.jiosaavn.com/search/' + quote(query, safe='')
        return {'success': open_url_robust(url), 'query': query, 'url': url}

    def _play_pause(self, params: dict) -> dict:
        print("Executing AI/ML action: play/pause")
        log.info("Toggling media play/pause")
        _safe_press("playpause")
        return {"success": True}

    def _next_track(self, params: dict) -> dict:
        print("Executing AI/ML action: next_track")
        log.info("Skipping to next track")
        _safe_press("nexttrack")
        return {"success": True}

    def _previous_track(self, params: dict) -> dict:
        print("Executing AI/ML action: previous_track")
        log.info("Skipping to previous track")
        _safe_press("prevtrack")
        return {"success": True}

    def _volume_up(self, params: dict) -> dict:
        print("Executing AI/ML action: volume_up")
        steps = int(params.get("steps", 2))
        log.info(f"Volume up ({steps} steps)")
        for _ in range(steps):
            _safe_press("volumeup")
        return {"success": True, "steps": steps}

    def _volume_down(self, params: dict) -> dict:
        print("Executing AI/ML action: volume_down")
        steps = int(params.get("steps", 2))
        log.info(f"Volume down ({steps} steps)")
        for _ in range(steps):
            _safe_press("volumedown")
        return {"success": True, "steps": steps}

    def _album_search(self, params: dict) -> dict:
        """
        Extension point: wire this up to a real music API (Spotify Web API,
        Last.fm, etc.) to search albums. Currently returns a stub result.
        """
        query = params.get("query", "")
        log.info(f"[STUB] Album search requested for query: '{query}'")
        return {"success": True, "query": query, "results": [], "note": "album_search is a stub - wire to a music API"}

    def _mute(self, params: dict) -> dict:
        print("Executing AI/ML action: mute")
        log.info("Toggling system mute")
        _safe_press("volumemute")
        return {"success": True}


	

ai_ml_handler = AIMLHandler()
print("AI/ML handler initialized")

