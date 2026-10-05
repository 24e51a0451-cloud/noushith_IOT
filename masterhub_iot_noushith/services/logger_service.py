"""
logger_service.py
------------------
Centralized logging for the whole MasterHub system.
Every module imports get_logger(name) instead of configuring logging itself.
Logs go to logs/masterhub.log (rotating) and to console.
"""

import logging
import os
import shutil
import time
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOG_DIR, "masterhub.log")

os.makedirs(LOG_DIR, exist_ok=True)

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-22s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


class SafeRotatingFileHandler(RotatingFileHandler):
    """
    A Windows-safe RotatingFileHandler that avoids crashing with WinError 32
    (PermissionError: The process cannot access the file because it is being used by another process)
    when multiple threads or processes access the log file during rotation.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rollover_lock_retry_until = 0.0

    def shouldRollover(self, record):
        if time.time() < self._rollover_lock_retry_until:
            return False
        return super().shouldRollover(record)

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None

        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = self.rotation_filename(f"{self.baseFilename}.{i}")
                dfn = self.rotation_filename(f"{self.baseFilename}.{i + 1}")
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        try:
                            os.remove(dfn)
                        except (PermissionError, OSError):
                            pass
                    try:
                        os.rename(sfn, dfn)
                    except (PermissionError, OSError):
                        pass

            dfn = self.rotation_filename(f"{self.baseFilename}.1")
            if os.path.exists(dfn):
                try:
                    os.remove(dfn)
                except (PermissionError, OSError):
                    pass

            try:
                self.rotate(self.baseFilename, dfn)
            except (PermissionError, OSError):
                try:
                    shutil.copy2(self.baseFilename, dfn)
                    with open(self.baseFilename, "w", encoding=self.encoding or "utf-8") as f:
                        f.truncate(0)
                except (PermissionError, OSError):
                    self._rollover_lock_retry_until = time.time() + 10.0

        if not self.delay:
            try:
                self.stream = self._open()
            except Exception:
                pass


def _configure_root():
    """Configure handlers exactly once for the whole process."""
    global _configured
    if _configured:
        return

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = SafeRotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    root = logging.getLogger("masterhub")
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    root.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a namespaced logger under the 'masterhub' tree.
    Usage: log = get_logger('core.engine')
    """
    _configure_root()
    return logging.getLogger(f"masterhub.{name}")
