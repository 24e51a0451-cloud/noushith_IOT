"""
actions/desktop/notepad.py
----------------------------
Notepad automation using pyautogui + Windows shortcuts.

Functions are intentionally small and composable so the handler/engine
can call exactly what's needed (open / write / save) independently.
"""

import time

from services.logger_service import get_logger

log = get_logger("actions.desktop.notepad")

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except Exception as exc:  # pragma: no cover - import guard for non-Windows/dev machines
    PYAUTOGUI_AVAILABLE = False
    log.warning(f"pyautogui not available in this environment: {exc}")


def _require_pyautogui():
    if not PYAUTOGUI_AVAILABLE:
        raise RuntimeError(
            "pyautogui is not available in this environment. "
            "Desktop automation only works on a Windows machine with a display "
            "and pyautogui installed."
        )


def open_notepad(wait: float = 1.5) -> dict:
    """Open Notepad via the Windows Run dialog."""
    _require_pyautogui()
    log.info("Opening Notepad")
    pyautogui.hotkey("win", "r")
    time.sleep(0.5)
    pyautogui.typewrite("notepad", interval=0.03)
    pyautogui.press("enter")
    time.sleep(wait)
    return {"success": True, "action": "open_notepad"}


def write_notepad(text: str = "", wait: float = 0.3) -> dict:
    """Type the given text into the currently focused Notepad window."""
    _require_pyautogui()
    if not text:
        text = "Hello from MasterHub - automated note."
    log.info(f"Writing text into Notepad ({len(text)} chars)")
    time.sleep(wait)
    pyautogui.typewrite(text, interval=0.02)
    return {"success": True, "action": "write_notepad", "text_length": len(text)}


def save_notepad(filename: str = "masterhub_note.txt", wait: float = 0.5) -> dict:
    """Save the current Notepad document via Ctrl+S, typing a filename in the Save dialog."""
    _require_pyautogui()
    log.info(f"Saving Notepad file as '{filename}'")
    pyautogui.hotkey("ctrl", "s")
    time.sleep(wait)
    pyautogui.typewrite(filename, interval=0.02)
    pyautogui.press("enter")
    time.sleep(wait)
    return {"success": True, "action": "save_notepad", "filename": filename}
