import threading
import time

from cortex.run_live import LiveRunner
from services.logger_service import get_logger

log = get_logger("cortex_service")

_runner = None
_thread = None
_stop_event = threading.Event()
_lifecycle_lock = threading.RLock()


def _run_cortex_worker() -> None:
    global _runner

    log.info("Cortex worker started")

    while not _stop_event.is_set():
        try:
            if _runner is None:
                _runner = LiveRunner()
                _runner.stop_event = _stop_event
            _runner.start()
            _runner.run_forever(_stop_event)
        except Exception as exc:
            log.exception(f"Cortex worker encountered exception: {exc}")
            from cortex import dashboard
            dashboard.update_status(connected=False, authorized=False, last_error=str(exc))
            _stop_event.wait(2.0)

    if _runner is not None:
        _runner.stop()
    log.info("Cortex worker stopped")


def start_cortex():
    with _lifecycle_lock:
        _start_cortex()


def _start_cortex():
    global _runner, _thread

    if _thread is not None and _thread.is_alive():
        log.info("Cortex service already running")
        return

    _stop_event.clear()

    _runner = LiveRunner()
    _runner.stop_event = _stop_event

    _thread = threading.Thread(
        target=_run_cortex_worker,
        daemon=True,
        name="CortexThread",
    )

    _thread.start()

    log.info("Cortex service thread started")


def stop_cortex():
    with _lifecycle_lock:
        _stop_cortex()


def _stop_cortex():
    global _runner, _thread

    log.info("Stopping Cortex service")

    _stop_event.set()

    if _runner is not None:
        try:
            _runner.client.close()
        except Exception:
            log.exception("Error while stopping Cortex runner")

    if _thread is not None and _thread.is_alive():
        _thread.join(timeout=5)

    if _thread is not None and _thread.is_alive():
        return
    _thread = None

    log.info("Cortex service stopped")


def get_runner() -> LiveRunner | None:
    global _runner
    return _runner
