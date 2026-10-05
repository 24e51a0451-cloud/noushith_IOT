"""
cortex/logger.py
-----------------
Centralized logging for the cortex module, following the exact same
rotating-file-handler + console-handler pattern already established by
services/logger_service.py and simulator/logger.py: one root handler
set configured once, namespaced child loggers via get_logger(name).

Deliberately writes to its own cortex/logs/cortex.log instead of
logs/masterhub.log or simulator/logs/simulation.log, so live headset
sessions never interleave with -- or rotate -- either of those.
"""

import logging
from services.logger_service import SafeRotatingFileHandler

from cortex.config import LOG_DIR, LOG_FILE, LOG_LEVEL

import os

os.makedirs(LOG_DIR, exist_ok=True)

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-24s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _resolve_level(name: str) -> int:
    return getattr(logging, name, logging.INFO) if isinstance(getattr(logging, name, None), int) else logging.INFO


def _configure_root() -> None:
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
    console_handler.setLevel(_resolve_level(LOG_LEVEL))

    root = logging.getLogger("cortex")
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    root.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a namespaced logger under the 'cortex' tree.
    Usage: log = get_logger('auth')
    """
    _configure_root()
    return logging.getLogger(f"cortex.{name}")
