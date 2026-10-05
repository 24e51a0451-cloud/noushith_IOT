"""
simulator/logger.py
--------------------
Centralized logging for the simulator, mirroring the pattern already
established in services/logger_service.py (rotating file handler +
console handler, one shared root configured once, namespaced child
loggers via get_logger(name)).

Deliberately kept separate from MasterHub's own logger: the simulator
writes to simulator/logs/simulation.log instead of logs/masterhub.log,
so replay runs never interleave with -- or rotate -- the real system
log. Every other module in this package imports get_logger(name) from
here instead of configuring logging itself, exactly like the rest of
the project does with services.logger_service.
"""

import logging
import os
from services.logger_service import SafeRotatingFileHandler

from simulator.config import LOG_DIR, LOG_FILE

os.makedirs(LOG_DIR, exist_ok=True)

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-24s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


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
    console_handler.setLevel(logging.WARNING)  # live table already covers INFO on screen

    root = logging.getLogger("simulator")
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    root.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a namespaced logger under the 'simulator' tree.
    Usage: log = get_logger('replay')
    """
    _configure_root()
    return logging.getLogger(f"simulator.{name}")
