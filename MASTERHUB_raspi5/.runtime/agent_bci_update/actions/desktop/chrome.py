"""
actions/desktop/chrome.py
-------------------------
Chrome automation using a configurable Chrome path/profile - mirrors
MasterHub's own actions/desktop/chrome.py, but reads chrome_path /
chrome_profile from THIS machine's config/agent_config.json rather than
MasterHub's config.py (MASTERHUB prompt section 25: never assume a
target PC has the same Chrome install path/profile as the host).
"""

import os
import subprocess
import time

from common.logger import get_logger
from config.loader import load_config

log = get_logger("actions.desktop.chrome")

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    PYAUTOGUI_AVAILABLE = False
    log.warning(f"pyautogui not available: {exc}")

_cfg = load_config()
_automation = _cfg.get("automation", {})
CHROME_PATH = _automation.get("chrome_path", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
CHROME_PROFILE = _automation.get("chrome_profile", "Default")
CHROME_EXTRA_ARGS = _automation.get("chrome_extra_args", [])
CHROME_ARGS = [f"--profile-directory={CHROME_PROFILE}"] + list(CHROME_EXTRA_ARGS)


def _require_pyautogui():
    if not PYAUTOGUI_AVAILABLE:
        raise RuntimeError("Desktop automation requires pyautogui and a Windows desktop.")


def open_chrome(wait: float = 3.0) -> dict:
    """Opens Chrome using this Agent's configured path/profile."""
    _require_pyautogui()

    if not os.path.exists(CHROME_PATH):
        raise FileNotFoundError(
            f"Chrome not found at '{CHROME_PATH}'. Set automation.chrome_path in "
            "config/agent_config.json (or MASTERHUB_AGENT_CHROME_PATH) for this machine."
        )

    log.info(f"Opening Chrome (profile={CHROME_PROFILE!r})")
    subprocess.Popen([CHROME_PATH] + CHROME_ARGS)
    time.sleep(wait)
    return {"success": True, "action": "open_chrome"}


def close_chrome(wait: float = 1.0) -> dict:
    _require_pyautogui()

    from actions.desktop.youtube import stop_ad_monitor
    stop_ad_monitor()

    log.info("Closing Chrome")
    pyautogui.hotkey("alt", "f4")
    time.sleep(wait)
    return {"success": True, "action": "close_chrome"}


def search_chrome(query: str, open_first: bool = True, wait: float = 2.0) -> dict:
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
    return {"success": True, "action": "search_chrome", "query": query}


def open_gmail(wait: float = 3.0) -> dict:
    """Opens Google Mail (Gmail) in Chrome."""
    _require_pyautogui()
    if not os.path.exists(CHROME_PATH):
        raise FileNotFoundError(f"Chrome not found at '{CHROME_PATH}'.")
    log.info("Opening Google Mail (Gmail)")
    subprocess.Popen([CHROME_PATH] + CHROME_ARGS + ["https://mail.google.com"])
    time.sleep(wait)
    return {"success": True, "action": "open_gmail"}


def compose_gmail(wait: float = 3.5) -> dict:
    """Opens Google Mail in compose mode."""
    _require_pyautogui()
    if not os.path.exists(CHROME_PATH):
        raise FileNotFoundError(f"Chrome not found at '{CHROME_PATH}'.")
    log.info("Opening Google Mail (Compose)")
    subprocess.Popen([CHROME_PATH] + CHROME_ARGS + ["https://mail.google.com/mail/u/0/#inbox?compose=new"])
    time.sleep(wait)
    return {"success": True, "action": "compose_gmail"}


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
