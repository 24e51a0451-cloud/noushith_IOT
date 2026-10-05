"""
utils.py
--------
Small shared helpers used across the framework: ANSI colour printing,
directory/file helpers, and a lightweight timer. No third-party
dependencies — standard library only.
"""

import csv
import json
import os
import sys
import time


class Color:
    """ANSI colour codes with a safe no-op fallback."""

    _ENABLED = True

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    GREY = "\033[90m"

    @classmethod
    def configure(cls, enabled: bool):
        cls._ENABLED = enabled and sys.stdout.isatty()
        if cls._ENABLED and os.name == "nt":
            # Enable VT100/ANSI processing on Windows 10+ consoles without
            # requiring a third-party dependency like colorama.
            try:
                os.system("")
            except Exception:
                cls._ENABLED = False

    @classmethod
    def wrap(cls, text: str, *codes: str) -> str:
        if not cls._ENABLED:
            return text
        return "".join(codes) + text + cls.RESET

    @classmethod
    def green(cls, text: str) -> str:
        return cls.wrap(text, cls.GREEN, cls.BOLD)

    @classmethod
    def red(cls, text: str) -> str:
        return cls.wrap(text, cls.RED, cls.BOLD)

    @classmethod
    def yellow(cls, text: str) -> str:
        return cls.wrap(text, cls.YELLOW, cls.BOLD)

    @classmethod
    def cyan(cls, text: str) -> str:
        return cls.wrap(text, cls.CYAN)

    @classmethod
    def dim(cls, text: str) -> str:
        return cls.wrap(text, cls.DIM)

    @classmethod
    def bold(cls, text: str) -> str:
        return cls.wrap(text, cls.BOLD)


class Timer:
    """Simple elapsed-time context manager / stopwatch."""

    def __init__(self):
        self._start = None
        self.elapsed = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_info):
        self.elapsed = time.perf_counter() - self._start
        return False

    def tick(self):
        return time.perf_counter() - self._start


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: str, data) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def save_csv(path: str, rows: list, fieldnames: list) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def human_bool(value) -> str:
    if value is True:
        return "True"
    if value is False:
        return "False"
    return "N/A"


def truncate(text, length=80):
    if text is None:
        return ""
    text = str(text)
    return text if len(text) <= length else text[: length - 3] + "..."
