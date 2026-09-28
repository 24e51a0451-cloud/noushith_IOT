"""
actions/desktop/system_apps.py
---------------------------------
Simple "open application" launchers for Calculator, Windows Calendar,
and Outlook. These all follow the same Win+R -> type -> Enter pattern.
"""

import time

from services.logger_service import get_logger

log = get_logger("actions.desktop.system_apps")

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


def _launch_via_run(command: str, wait: float) -> None:
    pyautogui.hotkey("win", "r")
    time.sleep(0.5)
    pyautogui.typewrite(command, interval=0.03)
    pyautogui.press("enter")
    time.sleep(wait)


def open_calculator(wait: float = 1.5) -> dict:
    _require_pyautogui()
    log.info("Opening Calculator")
    _launch_via_run("calc", wait)
    return {"success": True, "action": "open_calculator"}


def open_calendar(wait: float = 2.0) -> dict:
    _require_pyautogui()
    log.info("Opening Windows Calendar")
    _launch_via_run("outlookcal:", wait)
    return {"success": True, "action": "open_calendar"}


def open_outlook(wait: float = 3.0) -> dict:
    _require_pyautogui()
    log.info("Opening Outlook")
    _launch_via_run("outlook", wait)
    return {"success": True, "action": "open_outlook"}


def next_tab(wait: float = 0.3) -> dict:
    """Switch to the next tab in the focused browser/app window (Ctrl+Tab)."""
    _require_pyautogui()
    log.info("Switching to next tab")
    pyautogui.hotkey("ctrl", "tab")
    time.sleep(wait)
    return {"success": True, "action": "next_tab"}


def previous_tab(wait: float = 0.3) -> dict:
    """Switch to the previous tab in the focused browser/app window (Ctrl+Shift+Tab)."""
    _require_pyautogui()
    log.info("Switching to previous tab")
    pyautogui.hotkey("ctrl", "shift", "tab")
    time.sleep(wait)
    return {"success": True, "action": "previous_tab"}
