"""
core/metrics.py
---------------
Thread-safe metrics tracking, latency measurement, and runtime configuration
for MasterHub modernization.
"""

import threading
import time
from typing import Any, Dict


class MetricsTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._temporal_window = 4.0  # seconds, default within [2.0, 10.0]
        self._total_commands = 0
        self._successful_commands = 0
        self._failed_commands = 0
        self._had_failure = False

        # Latency rolling history (in ms)
        self._response_latencies = []
        self._process_latencies = []
        self._execution_latencies = []
        self._max_samples = 100

        # Latest latencies
        self._last_response_ms = 0.0
        self._last_process_ms = 0.0
        self._last_execution_ms = 0.0

    # ---- Temporal Window Configuration ----
    def get_temporal_window(self) -> float:
        with self._lock:
            return round(self._temporal_window, 2)

    def set_temporal_window(self, value: float) -> float:
        """
        Sets the temporal window in seconds.
        Strictly bounded between 2.0s and 10.0s.
        Raises ValueError if out of bounds.
        """
        try:
            val = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Temporal window must be a valid number: {exc}")

        if val < 2.0 or val > 10.0:
            raise ValueError("Temporal window must be between 2.0s and 10.0s")

        with self._lock:
            self._temporal_window = round(val, 2)
            return self._temporal_window

    # ---- Latency & Command Execution Recording ----
    def record_command(self, success: bool, response_ms: float, process_ms: float = 0.0, execution_ms: float = 0.0):
        with self._lock:
            self._total_commands += 1
            if success:
                self._successful_commands += 1
            else:
                self._failed_commands += 1
                self._had_failure = True

            self._last_response_ms = round(float(response_ms), 2)
            self._last_process_ms = round(float(process_ms), 2)
            self._last_execution_ms = round(float(execution_ms), 2)

            self._response_latencies.append(self._last_response_ms)
            self._process_latencies.append(self._last_process_ms)
            self._execution_latencies.append(self._last_execution_ms)

            if len(self._response_latencies) > self._max_samples:
                self._response_latencies.pop(0)
            if len(self._process_latencies) > self._max_samples:
                self._process_latencies.pop(0)
            if len(self._execution_latencies) > self._max_samples:
                self._execution_latencies.pop(0)

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            total = self._total_commands
            success = self._successful_commands
            failed = self._failed_commands

            if total > 0:
                avg_response = round(sum(self._response_latencies) / len(self._response_latencies), 2)
                avg_process = round(sum(self._process_latencies) / len(self._process_latencies), 2)
                avg_execution = round(sum(self._execution_latencies) / len(self._execution_latencies), 2)
                recovery_rate = round((success / total) * 100.0, 1)
            else:
                avg_response = self._last_response_ms
                avg_process = self._last_process_ms
                avg_execution = self._last_execution_ms
                recovery_rate = 100.0

            # Fault recovery status
            if failed == 0:
                fault_recovery = "100% · OPTIMAL"
            elif self._had_failure and total > 0 and success > 0:
                fault_recovery = "RECOVERED"
            else:
                fault_recovery = f"{recovery_rate}% · DEGRADED"

            return {
                "response_ms": self._last_response_ms,
                "process_ms": self._last_process_ms,
                "execution_ms": self._last_execution_ms,
                "response_latency_ms": self._last_response_ms,
                "process_latency_ms": self._last_process_ms,
                "execution_latency_ms": self._last_execution_ms,
                "avg_response_ms": avg_response,
                "avg_process_ms": avg_process,
                "avg_execution_ms": avg_execution,
                "fault_recovery": fault_recovery,
                "recovery_rate": recovery_rate,
                "total_commands": total,
                "successful_commands": success,
                "failed_commands": failed,
                "temporal_window_s": self._temporal_window,
            }

    def reset(self):
        with self._lock:
            self._temporal_window = 4.0
            self._total_commands = 0
            self._successful_commands = 0
            self._failed_commands = 0
            self._had_failure = False
            self._response_latencies.clear()
            self._process_latencies.clear()
            self._execution_latencies.clear()
            self._last_response_ms = 0.0
            self._last_process_ms = 0.0
            self._last_execution_ms = 0.0


metrics_tracker = MetricsTracker()
