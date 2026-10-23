"""
actions/media/handler.py
---------------------------
Media-control dispatch table. Internally called "media" per the project
brief ("the PC Agent can internally call its handler `media`"), but the
COMMAND envelope's `domain` field on the wire is still "ai_ml" - that is
MasterHub's actual, existing domain name for this functionality
(mappings/ai_ml_map.json / actions/ai_ml/handler.py), discovered from
the source ZIP, and is NOT renamed here. agent/pc_agent.py maps
domain="ai_ml" -> this handler.

Action identifiers match MasterHub's mappings/ai_ml_map.json exactly:
    play, pause, next_track, previous_track, volume_up, volume_down,
    mute, album_search
"""

from common.logger import get_logger

log = get_logger("actions.media")

try:
    import pyautogui
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


class MediaHandler:
    def __init__(self):
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

    def execute(self, action: str, params: dict = None) -> dict:
        params = params or {}
        fn = self._dispatch.get(action)
        if fn is None:
            log.warning(f"No media handler registered for action '{action}'")
            return {"success": False, "error": f"Unknown action: {action}"}

        result = fn(params)
        result.setdefault("domain", "ai_ml")
        result.setdefault("action", action)
        return result

    # ---------- handlers (mirrors actions/ai_ml/handler.py exactly) ----------

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
        _require_pyautogui()
        log.info("Toggling media play/pause")
        pyautogui.press("playpause")
        return {"success": True}

    def _next_track(self, params: dict) -> dict:
        _require_pyautogui()
        log.info("Skipping to next track")
        pyautogui.press("nexttrack")
        return {"success": True}

    def _previous_track(self, params: dict) -> dict:
        _require_pyautogui()
        log.info("Skipping to previous track")
        pyautogui.press("prevtrack")
        return {"success": True}

    def _volume_up(self, params: dict) -> dict:
        _require_pyautogui()
        steps = int(params.get("steps", 2))
        log.info(f"Volume up ({steps} steps)")
        for _ in range(steps):
            pyautogui.press("volumeup")
        return {"success": True, "steps": steps}

    def _volume_down(self, params: dict) -> dict:
        _require_pyautogui()
        steps = int(params.get("steps", 2))
        log.info(f"Volume down ({steps} steps)")
        for _ in range(steps):
            pyautogui.press("volumedown")
        return {"success": True, "steps": steps}

    def _album_search(self, params: dict) -> dict:
        """Stub - matches MasterHub's own local ai_ml_handler._album_search
        (extension point for a real music API), reproduced here so the
        action is not silently "unknown" when routed to a target PC."""
        query = params.get("query", "")
        log.info(f"[STUB] Album search requested for query: '{query}'")
        return {"success": True, "query": query, "results": [], "note": "album_search is a stub - wire to a music API"}

    def _mute(self, params: dict) -> dict:
        _require_pyautogui()
        log.info("Toggling system mute")
        pyautogui.press("volumemute")
        return {"success": True}


media_handler = MediaHandler()
