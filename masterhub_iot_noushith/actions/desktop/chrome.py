"""
actions/desktop/chrome.py
-------------------------
Chrome automation using a configurable Chrome profile.
"""

import os
import subprocess
import time

from services.logger_service import get_logger
from config import CHROME_PATH, CHROME_ARGS

log = get_logger("actions.desktop.chrome")

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except Exception as exc:
    PYAUTOGUI_AVAILABLE = False
    log.warning(f"pyautogui not available: {exc}")


def _require_pyautogui():
    if not PYAUTOGUI_AVAILABLE:
        raise RuntimeError(
            "Desktop automation requires pyautogui and a Windows desktop."
        )


def open_chrome(wait: float = 3.0) -> dict:
    """
    Opens Chrome using the configured or auto-detected path.
    """
    _require_pyautogui()

    from actions.desktop.gmail import find_chrome_path
    path = CHROME_PATH if (CHROME_PATH and os.path.exists(CHROME_PATH)) else find_chrome_path()

    if path:
        log.info(f"Opening Chrome via {path}")
        try:
            subprocess.Popen([path] + CHROME_ARGS)
            time.sleep(wait)
            return {"success": True, "action": "open_chrome"}
        except Exception as exc:
            log.warning(f"Chrome launch with args failed: {exc}")

    # Fallback via Windows Run dialog
    try:
        pyautogui.hotkey("win", "r")
        time.sleep(0.5)
        pyautogui.typewrite("chrome", interval=0.03)
        pyautogui.press("enter")
        time.sleep(wait)
        return {"success": True, "action": "open_chrome"}
    except Exception as exc:
        log.error(f"Failed to open Chrome: {exc}")
        return {"success": False, "action": "open_chrome", "error": str(exc)}


def close_chrome(wait: float = 1.0) -> dict:
    _require_pyautogui()

    # Lazy import to avoid circular import
    from actions.desktop.youtube import stop_ad_monitor

    stop_ad_monitor()

    log.info("Closing Chrome")

    pyautogui.hotkey("alt", "f4")

    time.sleep(wait)

    return {
        "success": True,
        "action": "close_chrome"
    }

def search_chrome(
    query: str,
    open_first: bool = True,
    wait: float = 2.0,
) -> dict:

    _require_pyautogui()

    if not query:
        raise ValueError("Query cannot be empty.")

    if open_first:
        open_chrome()

    log.info(f"Searching Chrome: {query}")

    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.5)

    pyautogui.hotkey("ctrl", "a")

    pyautogui.write(query, interval=0.02)

    pyautogui.press("enter")

    time.sleep(wait)

    return {
        "success": True,
        "action": "search_chrome",
        "query": query,
    }


def scroll_chrome(direction: str) -> dict:
    _require_pyautogui()
    # Bring an existing Chrome window forward, avoiding accidental scrolling in MasterHub.
    import pygetwindow
    windows = [w for w in pygetwindow.getWindowsWithTitle('Google Chrome') if w.title]
    if not windows:
        raise RuntimeError('Open Chrome before scrolling.')
    window = windows[0]
    if window.isMinimized:
        window.restore()
    window.activate()
    time.sleep(0.2)
    pyautogui.scroll(5 if direction == 'up' else -5)
    return {'success': True, 'action': 'chrome_scroll_' + direction}
