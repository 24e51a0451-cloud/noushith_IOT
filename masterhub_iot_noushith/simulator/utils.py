"""
simulator/utils.py
--------------------
Small formatting/statistics helpers shared by replay.py. Kept separate
from replay.py so the orchestration logic isn't cluttered with string
padding and ANSI color codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

# --------------------------------------------------------------------
# Console colors (plain ANSI, no external dependency -- works in
# Windows Terminal / PowerShell 7+ / cmd.exe with VT100 enabled, which
# is the default on Windows 10 1909+ and Windows 11)
# --------------------------------------------------------------------

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    GRAY = "\033[90m"


def enable_windows_ansi() -> None:
    """
    Best-effort enable of ANSI/VT100 escape sequence processing on
    Windows consoles. No-op (and safe) on other platforms or if the
    console doesn't support it.
    """
    import os
    import sys

    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:
        pass  # non-fatal -- table just prints without color


def colorize(text: str, color: str) -> str:
    return f"{color}{text}{C.RESET}"


def pad(text: str, width: int) -> str:
    text = str(text)
    if len(text) > width:
        return text[: max(0, width - 1)] + "…"
    return text.ljust(width)


def fmt_ms(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:.0f}ms"


def fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.0f}%"


def mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


# --------------------------------------------------------------------
# Run-level statistics accumulator
# --------------------------------------------------------------------

@dataclass
class RunStats:
    total_predictions: int = 0
    accepted: int = 0          # passed confidence filter
    rejected: int = 0          # failed confidence filter
    duplicates_skipped: int = 0  # suppressed by stabilizer
    commands_executed: int = 0   # successfully sent + MasterHub reported success
    failures: int = 0            # sent but failed (HTTP error or success=False)
    confidences: list = field(default_factory=list)
    response_times_ms: list = field(default_factory=list)
    domain_counts: dict = field(default_factory=dict)

    def record_domain(self, domain: str) -> None:
        if not domain:
            return
        self.domain_counts[domain] = self.domain_counts.get(domain, 0) + 1

    @property
    def avg_confidence(self) -> float:
        return mean(self.confidences)

    @property
    def avg_response_time_ms(self) -> float:
        return mean(self.response_times_ms)
