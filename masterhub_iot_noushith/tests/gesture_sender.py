"""
gesture_sender.py
------------------
Sends gesture test cases to MasterHub's real, running HTTP API. This
framework never imports or calls MasterHub's Python code directly — it
only talks to the same POST /api/command endpoint any real gesture
device would use, exactly per requirement: "The framework must NOT
modify MasterHub. It must only read JSON configuration, send gestures,
read logs, validate output, generate reports."
"""

import time

import requests


class GestureSender:
    def __init__(self, base_url: str, command_endpoint: str, health_endpoint: str, timeout: float):
        self.command_url = base_url.rstrip("/") + command_endpoint
        self.health_url = base_url.rstrip("/") + health_endpoint
        self.timeout = timeout

    def check_health(self):
        """
        Pre-flight check. Returns (ok: bool, detail: str).
        """
        try:
            resp = requests.get(self.health_url, timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            return False, str(exc)

        if resp.status_code != 200:
            return False, f"Health endpoint returned HTTP {resp.status_code}"
        return True, "OK"

    def send_gesture(self, gesture: str, mode: str) -> dict:
        """
        POST {"gesture": gesture, "mode": mode} to /api/command.

        Sending an explicit 'mode' override every time (rather than relying
        on MasterHub's live, shared FSM state) is deliberate: it makes each
        test case fully deterministic and independent of test execution
        order or of side effects from earlier tests, per
        core/input_processor.py's documented resolution order:

            "gesture" + "mode" -> resolve via gesture_map.json using the
            explicit 'mode' override in the payload (bypasses the FSM's
            current live mode for resolution purposes only).

        Note the FSM's *actual* mode can still change as a real side effect
        when the resolved command happens to be a mode-switch command —
        that's normal MasterHub behaviour, not a bug in this framework.

        Returns a dict:
            {
                "ok": bool,            # False only on network-level failure
                "status_code": int | None,
                "json": dict | None,
                "elapsed": float,      # seconds
                "error": str | None,
            }
        """
        payload = {"gesture": gesture, "mode": mode}
        start = time.perf_counter()
        try:
            resp = requests.post(self.command_url, json=payload, timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            elapsed = time.perf_counter() - start
            return {
                "ok": False,
                "status_code": None,
                "json": None,
                "elapsed": elapsed,
                "error": str(exc),
            }

        elapsed = time.perf_counter() - start
        try:
            body = resp.json()
        except ValueError:
            body = None

        return {
            "ok": True,
            "status_code": resp.status_code,
            "json": body,
            "elapsed": elapsed,
            "error": None if body is not None else "Response body was not valid JSON",
        }
