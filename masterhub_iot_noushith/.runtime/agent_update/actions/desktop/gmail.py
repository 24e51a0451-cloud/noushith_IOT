"""
actions/desktop/gmail.py
------------------------
Gmail desktop and browser automation:
  - open_gmail: navigate directly to Gmail web interface
  - compose_gmail: trigger compose window or navigate to direct compose URL
  - search_gmail: search emails by query
  - send_gmail: dispatch the composed email (Ctrl+Enter)
"""

import os
import subprocess
import time
import urllib.parse
import shutil
from actions.desktop.chrome import CHROME_PATH, CHROME_ARGS
from typing import Optional

from common.logger import get_logger

log = get_logger("actions.desktop.gmail")

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except Exception as exc:
    PYAUTOGUI_AVAILABLE = False
    log.warning(f"pyautogui not available: {exc}")


def _require_pyautogui():
    if not PYAUTOGUI_AVAILABLE:
        raise RuntimeError("Desktop automation requires pyautogui and an active display.")


def find_chrome_path() -> Optional[str]:
    """Auto-detects Chrome executable across standard Windows installation paths."""
    candidates = [
        CHROME_PATH,
        shutil.which("chrome"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def open_url_robust(url: str, wait: float = 2.5) -> bool:
    """
    Launch a URL in the configured Chrome profile; report failure if Chrome is unavailable.
    """
    chrome_exe = find_chrome_path()
    if not chrome_exe:
        log.error("Google Chrome was not found; configure CHROME_PATH on the target PC.")
        return False
    try:
        subprocess.Popen([chrome_exe, *CHROME_ARGS, url])
        time.sleep(wait)
        return True
    except OSError as exc:
        log.error("Chrome launch failed: %s", exc)
        return False


def open_gmail(wait: float = 3.5) -> dict:
    """Opens the Gmail web interface."""
    log.info("Opening Gmail")
    ok = open_url_robust("https://mail.google.com", wait=wait)
    return {"success": ok, "action": "open_gmail", "app": "gmail"}


def compose_gmail(to: str = "", subject: str = "", body: str = "", wait: float = 2.5) -> dict:
    """
    Opens Gmail directly in full compose view with prefilled parameters.
    """
    log.info(f"Opening Gmail Compose (to='{to}', subject='{subject}')")
    params = ["view=cm", "fs=1"]
    if to:
        params.append(f"to={urllib.parse.quote(to)}")
    if subject:
        params.append(f"su={urllib.parse.quote(subject)}")
    if body:
        params.append(f"body={urllib.parse.quote(body)}")

    compose_url = f"https://mail.google.com/mail/u/0/?{'&'.join(params)}"
    ok = open_url_robust(compose_url, wait=wait)
    return {
        "success": ok,
        "action": "compose_gmail",
        "to": to,
        "subject": subject,
        "body": body,
    }


def search_gmail(query: str = "", wait: float = 2.5) -> dict:
    """Search Gmail messages with search query."""
    if not query:
        return open_gmail(wait=wait)

    log.info(f"Searching Gmail for: '{query}'")
    search_url = f"https://mail.google.com/mail/u/0/#search/{urllib.parse.quote(query)}"
    ok = open_url_robust(search_url, wait=wait)
    return {"success": ok, "action": "search_gmail", "query": query}


def send_gmail(wait: float = 1.0) -> dict:
    """Sends the currently active/focused Gmail draft using Ctrl+Enter."""
    _require_pyautogui()
    log.info("Dispatching email via shortcut (Ctrl+Enter)")
    pyautogui.hotkey("ctrl", "enter")
    time.sleep(wait)
    return {"success": True, "action": "send_gmail"}
