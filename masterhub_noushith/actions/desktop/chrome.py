'''
"""
actions/desktop/chrome.py
---------------------------
Chrome automation: open Chrome, and perform a search by typing into the
omnibox/address bar (works without needing Selenium/webdriver).
"""

import time

from services.logger_service import get_logger

log = get_logger("actions.desktop.chrome")

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
            "Desktop automation only works on a Windows machine with a display."
        )


def open_chrome(wait: float = 2.0) -> dict:
    """Open Google Chrome via the Windows Run dialog."""
    _require_pyautogui()
    log.info("Opening Chrome")
    pyautogui.hotkey("win", "r")
    time.sleep(0.5)
    pyautogui.typewrite("chrome", interval=0.03)
    pyautogui.press("enter")
    time.sleep(wait)
    return {"success": True, "action": "open_chrome"}


def close_chrome(wait: float = 1.0) -> dict:
    """Close the focused Chrome window via Alt+F4."""
    _require_pyautogui()
    log.info("Closing Chrome")
    pyautogui.hotkey("alt", "f4")
    time.sleep(wait)
    return {"success": True, "action": "close_chrome"}


def search_chrome(query: str, open_first: bool = True, wait: float = 1.5) -> dict:
    """
    Open Chrome (optional) then perform a search using the address bar
    (Ctrl+L focuses the omnibox), typing the query and pressing Enter.
    """
    _require_pyautogui()
    if not query:
        raise ValueError("search_chrome requires a non-empty 'query'")

    if open_first:
        open_chrome(wait=wait)

    log.info(f"Searching Chrome for: '{query}'")
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.4)
    pyautogui.typewrite(query, interval=0.02)
    pyautogui.press("enter")
    time.sleep(wait)
    return {"success": True, "action": "search_chrome", "query": query}
'''


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
