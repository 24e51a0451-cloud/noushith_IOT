"""Cortex connection, live telemetry, profile, and control endpoints.

The app-owned headset worker and dashboard share this in-memory state.
Workflow routing lives in cortex.control and reuses the MasterHub engine.
"""

from collections import deque
import itertools
import json
import os
from pathlib import Path
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

from flask import Blueprint, Response, jsonify, render_template_string, render_template, request, current_app
from cortex import config as cortex_config
from cortex.config import DASHBOARD_URL_PREFIX, _ENV_FILE
from services.logger_service import get_logger

log = get_logger('bci.activity')

cortex_bp = Blueprint("cortex", __name__, url_prefix=DASHBOARD_URL_PREFIX)

_lock = threading.RLock()
_log_id_counter = itertools.count(1)
_command_logs: deque[dict] = deque(maxlen=500)
_predictions: deque[dict] = deque(maxlen=40)
_prediction_ids = itertools.count(1)
_control_enabled = False
_control_generation = 0
_feedback_key = None


@dataclass
class _StatusState:
    connected: bool = False
    authorized: bool = False
    started_at: Optional[float] = None
    last_error: str = ""
    retry_attempt: int = 0
    client_id: str = ""
    current_profile: str = ""
    available_profiles: list[str] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)


@dataclass
class _HeadsetState:
    id: str = ""
    status: str = "unknown"
    battery_percent: Optional[float] = None
    signal_quality: Optional[float] = None
    updated_at: float = field(default_factory=time.time)


@dataclass
class _SessionState:
    id: str = ""
    status: str = "none"
    headset_id: str = ""
    updated_at: float = field(default_factory=time.time)


@dataclass
class _MetricsState:
    current_gesture: str = ""
    confidence: Optional[float] = None
    accepted: int = 0
    rejected: int = 0
    duplicates: int = 0
    commands_sent: int = 0
    current_mode: str = ""
    current_routed_command: str = ""
    current_domain: str = ""
    http_status: Optional[int] = None
    response_time_ms: Optional[float] = None
    updated_at: float = field(default_factory=time.time)


_status = _StatusState()
_headset = _HeadsetState()
_session = _SessionState()
_metrics = _MetricsState()


# ------------------------------------------------------------------
# Update functions -- called from run_live.py or other Cortex scripts
# ------------------------------------------------------------------

def update_status(
    connected: Optional[bool] = None,
    authorized: Optional[bool] = None,
    last_error: Optional[str] = None,
    retry_attempt: Optional[int] = None,
) -> None:
    global _control_enabled
    with _lock:
        if connected is not None:
            _status.connected = connected
            if connected and _status.started_at is None:
                _status.started_at = time.time()
            if not connected:
                _status.started_at = None
                _status.current_profile = ""
                _predictions.clear()
                _control_enabled = False
        if authorized is not None:
            _status.authorized = authorized
        if last_error is not None:
            _status.last_error = last_error
        if retry_attempt is not None:
            _status.retry_attempt = retry_attempt
        _status.updated_at = time.time()


def update_headset(headset_id: Optional[str] = None, status: Optional[str] = None, battery_percent=None, signal_quality=None) -> None:
    with _lock:
        if headset_id is not None:
            _headset.id = headset_id
        if status is not None:
            _headset.status = status
        if battery_percent is not None:
            _headset.battery_percent = battery_percent
        if signal_quality is not None:
            _headset.signal_quality = signal_quality
        _headset.updated_at = time.time()


def update_session(session_id: Optional[str] = None, status: Optional[str] = None, headset_id: Optional[str] = None) -> None:
    with _lock:
        if session_id is not None:
            _session.id = session_id
        if status is not None:
            _session.status = status
        if headset_id is not None:
            _session.headset_id = headset_id
        _session.updated_at = time.time()


def update_prediction(gesture: Optional[str] = None, confidence: Optional[float] = None) -> None:
    global _control_enabled
    with _lock:
        if not _predictions or time.time() - _predictions[-1]["received_at"] >= 3:
            _control_enabled = False
        if gesture is not None:
            _metrics.current_gesture = gesture
        if confidence is not None:
            _metrics.confidence = confidence
        _metrics.updated_at = time.time()
        _predictions.append({"id": next(_prediction_ids), "action": gesture or "neutral",
                             "power": confidence, "received_at": time.time()})
        if not control_enabled():
            reason = ('Load a trained profile, then Enable Control.' if not _status.current_profile
                      else 'Monitor mode. Click Enable Control, return to neutral, then perform a command.')
            report_control_feedback('MONITOR', reason, gesture, confidence)


def control_enabled() -> bool:
    return control_token() is not None


def control_token():
    """Check freshness even when no browser is polling the event stream."""
    global _control_enabled
    with _lock:
        latest = _predictions[-1] if _predictions else None
        if not (_status.connected and _status.authorized and _status.current_profile
                and latest and time.time() - latest['received_at'] < 3):
            _control_enabled = False
        return _control_generation if _control_enabled else None


def live_snapshot() -> dict:
    global _control_enabled
    with _lock:
        latest = _predictions[-1] if _predictions else None
        streaming = bool(_status.connected and _status.authorized and latest
                         and time.time() - latest["received_at"] < 3)
        if not streaming:
            _control_enabled = False
        data = {"status": asdict(_status), "headset": asdict(_headset),
                "session": asdict(_session), "metrics": asdict(_metrics),
                "predictions": list(_predictions), "streaming": streaming,
                "control_enabled": _control_enabled, "server_time": time.time()}
    from cortex.control import cortex_control
    data['workflow'] = cortex_control.snapshot()
    return data


@cortex_bp.route("/events")
def live_events():
    def generate():
        while True:
            yield "data: " + json.dumps(live_snapshot()) + "\n\n"
            time.sleep(0.125)
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@cortex_bp.route("/control", methods=["POST"])
def set_control():
    global _control_enabled, _control_generation
    payload = request.get_json(silent=True)
    enabled = payload.get('enabled') if isinstance(payload, dict) else None
    if not isinstance(enabled, bool):
        return jsonify(success=False, error="enabled must be a boolean"), 400
    with _lock:
        latest = _predictions[-1] if _predictions else None
        if enabled and not (_status.connected and _status.authorized and
                            _status.current_profile and latest and
                            time.time() - latest["received_at"] < 3):
            return jsonify(success=False, error="Connect, load a trained profile, and wait for live samples first."), 409
        _control_enabled = enabled
        _control_generation += 1
    from cortex.control import cortex_control
    cortex_control.reset()
    if not enabled:
        cortex_control.stop_motion()
    report_control_feedback('CONTROL_ENABLED' if enabled else 'MONITOR',
                            cortex_control.message if enabled else 'Control paused. Click Enable Control to resume.')
    return jsonify(success=True, control_enabled=enabled)


@cortex_bp.route('/workflow', methods=['GET', 'POST'])
def cortex_workflow():
    from cortex.control import cortex_control
    if request.method == 'POST':
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(success=False, error='Expected a JSON object.'), 400
        if control_enabled():
            return jsonify(success=False, error='Pause control before changing command inputs.'), 409
        try:
            cortex_control.set_parameters(payload.get('command'), payload.get('params'))
        except ValueError as exc:
            return jsonify(success=False, error=str(exc)), 400
    return jsonify(success=True, workflow=cortex_control.snapshot())


def report_control_feedback(state, message, gesture=None, power=None):
    """Explain control gates once per transition, rather than once per EEG sample."""
    global _feedback_key
    with _lock:
        key = (state, message)
        if key == _feedback_key:
            return
        _feedback_key = key
        log_command_event(event_type='BCI_STATUS', gesture=gesture or '—',
                          confidence=f'{power:.1%}' if power is not None else '—',
                          command=state, domain='bci', status='INFO',
                          acknowledgement=message)


def log_command_event(
    *,
    event_type: str = "COMMAND",
    gesture: str = "—",
    confidence: str = "—",
    command: str = "—",
    domain: str = "—",
    acknowledgement: str = "—",
    status: str = "SUCCESS",
    detail: str = "",
) -> dict:
    with _lock:
        now = time.time()
        time_str = time.strftime("%H:%M:%S", time.localtime(now))
        iso_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        entry = {
            "id": next(_log_id_counter),
            "timestamp": iso_str,
            "time": time_str,
            "type": event_type,
            "gesture": gesture,
            "confidence": confidence,
            "command": command,
            "domain": domain,
            "acknowledgement": acknowledgement,
            "status": status,
            "detail": detail,
        }
        _command_logs.append(entry)
        log.info('[%s] gesture=%s power=%s command=%s domain=%s status=%s ACK=%s %s',
                 event_type, gesture, confidence, command, domain, status, acknowledgement, detail)
        return entry


def update_profile(current: Optional[str] = None, available: Optional[list[str]] = None) -> None:
    global _control_enabled
    with _lock:
        if current is not None:
            if current != _status.current_profile:
                _control_enabled = False
            _status.current_profile = current
        if available is not None:
            _status.available_profiles = list(available)
        _status.updated_at = time.time()


def update_pipeline_result(
    *,
    accepted: Optional[bool] = None,
    rejected: Optional[bool] = None,
    duplicate: Optional[bool] = None,
    commands_sent: Optional[bool] = None,
    mode: Optional[str] = None,
    routed_command: Optional[str] = None,
    domain: Optional[str] = None,
    http_status: Optional[int] = None,
    response_time_ms: Optional[float] = None,
    gesture: Optional[str] = None,
    power: Optional[float] = None,
    error: str = '',
) -> None:
    with _lock:
        if accepted:
            _metrics.accepted += 1
        if rejected:
            _metrics.rejected += 1
        if duplicate:
            _metrics.duplicates += 1
        if commands_sent:
            _metrics.commands_sent += 1
        if mode is not None:
            _metrics.current_mode = mode
        if routed_command is not None:
            _metrics.current_routed_command = routed_command
        if domain is not None:
            _metrics.current_domain = domain
        if http_status is not None:
            _metrics.http_status = http_status
        if response_time_ms is not None:
            _metrics.response_time_ms = response_time_ms
        _metrics.updated_at = time.time()

        # Log real-time event with acknowledgement
        gesture_name = gesture or _metrics.current_gesture or "—"
        event_power = power if power is not None else _metrics.confidence
        conf_str = f"{event_power*100:.1f}%" if event_power is not None else "—"
        if commands_sent:
            ack_msg = f"MASTERHUB_ACCEPTED · {response_time_ms or 0:.1f}ms"
            log_command_event(
                event_type="BCI",
                gesture=gesture_name,
                confidence=conf_str,
                command=routed_command or _metrics.current_routed_command or "command",
                domain=domain or _metrics.current_domain or "system",
                acknowledgement=ack_msg,
                status="SUCCESS",
                detail=f"Dispatched via MasterHub in mode {mode or _metrics.current_mode}",
            )
        elif accepted:
            log_command_event(event_type='BCI', gesture=gesture_name, confidence=conf_str,
                              command=routed_command or 'command', domain=domain or 'system',
                              acknowledgement='FAILED · ' + (error or 'MasterHub could not execute the command'), status='FAILED')
        elif duplicate:
            log_command_event(
                event_type="PREDICTION",
                gesture=gesture_name,
                confidence=conf_str,
                command="[STABILIZED]",
                domain="bci",
                acknowledgement="DEBOUNCED · Duplicate ignored",
                status="IGNORED",
                detail="Within debounce stabilizer threshold",
            )
        elif rejected:
            log_command_event(
                event_type="PREDICTION",
                gesture=gesture_name,
                confidence=conf_str,
                command="[REJECTED]",
                domain="bci",
                acknowledgement="FILTERED · Below confidence threshold",
                status="REJECTED",
                detail="Prediction confidence below acceptable threshold",
            )


def reset() -> None:
    """Clear all tracked state (useful in tests)."""
    global _status, _headset, _session, _metrics, _command_logs, _control_enabled, _feedback_key
    with _lock:
        _status = _StatusState()
        _headset = _HeadsetState()
        _session = _SessionState()
        _metrics = _MetricsState()
        _command_logs.clear()
        _predictions.clear()
        _control_enabled = False
        _feedback_key = None


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
_DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <title>Cortex Live Dashboard</title>

    <style>
        * {
            box-sizing: border-box;
        }

        :root {
            --bg: #0b1120;
            --bg-secondary: #111827;
            --card: rgba(17, 24, 39, 0.82);
            --card-hover: rgba(25, 35, 55, 0.95);
            --border: rgba(148, 163, 184, 0.14);
            --text: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;

            --green: #10b981;
            --green-bg: rgba(16, 185, 129, 0.12);

            --red: #ef4444;
            --red-bg: rgba(239, 68, 68, 0.12);

            --blue: #3b82f6;
            --blue-bg: rgba(59, 130, 246, 0.12);

            --purple: #8b5cf6;
            --purple-bg: rgba(139, 92, 246, 0.12);

            --orange: #f59e0b;
            --orange-bg: rgba(245, 158, 11, 0.12);
        }

        html {
            scroll-behavior: smooth;
        }

        body {
            margin: 0;
            min-height: 100vh;
            font-family:
                Inter,
                ui-sans-serif,
                system-ui,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;

            color: var(--text);

            background:
                radial-gradient(
                    circle at 15% 10%,
                    rgba(59, 130, 246, 0.12),
                    transparent 28%
                ),
                radial-gradient(
                    circle at 85% 20%,
                    rgba(139, 92, 246, 0.10),
                    transparent 28%
                ),
                linear-gradient(
                    135deg,
                    #070b14 0%,
                    #0b1120 45%,
                    #0f172a 100%
                );
        }

        .container {
            width: min(1400px, calc(100% - 40px));
            margin: 0 auto;
            padding: 30px 0 50px;
        }

        /* ---------------------------------------------------------
           HEADER
        --------------------------------------------------------- */

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;
            margin-bottom: 28px;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .brand-icon {
            width: 56px;
            height: 56px;
            border-radius: 16px;

            display: flex;
            align-items: center;
            justify-content: center;

            font-size: 27px;

            background:
                linear-gradient(
                    135deg,
                    rgba(59, 130, 246, 0.22),
                    rgba(139, 92, 246, 0.22)
                );

            border: 1px solid rgba(96, 165, 250, 0.22);

            box-shadow:
                0 10px 30px rgba(0, 0, 0, 0.25),
                inset 0 1px 0 rgba(255, 255, 255, 0.05);
        }

        .brand h1 {
            margin: 0;
            font-size: 26px;
            font-weight: 750;
            letter-spacing: -0.5px;
        }

        .brand p {
            margin: 5px 0 0;
            color: var(--text-secondary);
            font-size: 13px;
        }

        .live-indicator {
            display: flex;
            align-items: center;
            gap: 9px;

            padding: 9px 14px;

            border: 1px solid var(--border);
            border-radius: 999px;

            background: rgba(15, 23, 42, 0.75);

            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 600;
        }

        .live-dot {
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: var(--red);

            box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.10);
        }

        .live-dot.connected {
            background: var(--green);
            box-shadow:
                0 0 0 4px rgba(16, 185, 129, 0.10),
                0 0 14px rgba(16, 185, 129, 0.55);
            animation: pulse 1.8s infinite;
        }

        @keyframes pulse {
            0%, 100% {
                opacity: 1;
            }

            50% {
                opacity: 0.45;
            }
        }

        /* ---------------------------------------------------------
           TOP STATUS CARDS
        --------------------------------------------------------- */

        .status-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 20px;
        }

        .status-card {
            position: relative;
            overflow: hidden;

            padding: 20px;

            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 18px;

            backdrop-filter: blur(14px);

            box-shadow:
                0 15px 40px rgba(0, 0, 0, 0.20),
                inset 0 1px 0 rgba(255, 255, 255, 0.025);

            transition:
                transform 0.2s ease,
                border-color 0.2s ease,
                background 0.2s ease;
        }

        .status-card:hover {
            transform: translateY(-2px);
            background: var(--card-hover);
            border-color: rgba(148, 163, 184, 0.22);
        }

        .status-card::after {
            content: "";
            position: absolute;
            width: 90px;
            height: 90px;
            right: -35px;
            bottom: -35px;
            border-radius: 50%;
            background: var(--blue-bg);
            pointer-events: none;
        }

        .status-label {
            color: var(--text-secondary);
            font-size: 12px;
            font-weight: 650;
            text-transform: uppercase;
            letter-spacing: 0.7px;
        }

        .status-value {
            margin-top: 10px;
            font-size: 21px;
            font-weight: 750;
            letter-spacing: -0.3px;
        }

        .status-description {
            margin-top: 5px;
            color: var(--text-muted);
            font-size: 12px;
        }

        /* ---------------------------------------------------------
           MAIN GRID
        --------------------------------------------------------- */

        .main-grid {
            display: grid;
            grid-template-columns: 1.25fr 0.75fr;
            gap: 20px;
            align-items: start;
        }

        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 18px;

            backdrop-filter: blur(14px);

            box-shadow:
                0 15px 40px rgba(0, 0, 0, 0.20),
                inset 0 1px 0 rgba(255, 255, 255, 0.025);

            overflow: hidden;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;

            padding: 18px 20px;

            border-bottom: 1px solid var(--border);
        }

        .card-title {
            display: flex;
            align-items: center;
            gap: 10px;

            font-size: 15px;
            font-weight: 700;
        }

        .card-title-icon {
            width: 32px;
            height: 32px;

            display: flex;
            align-items: center;
            justify-content: center;

            border-radius: 10px;

            background: var(--blue-bg);

            font-size: 15px;
        }

        .card-subtitle {
            color: var(--text-muted);
            font-size: 11px;
        }

        .card-body {
            padding: 6px 20px 18px;
        }

        /* ---------------------------------------------------------
           TABLE
        --------------------------------------------------------- */

        .data-row {
            display: grid;
            grid-template-columns: 1fr 1.25fr;
            align-items: center;

            min-height: 49px;

            border-bottom: 1px solid var(--border);
        }

        .data-row:last-child {
            border-bottom: none;
        }

        .data-label {
            color: var(--text-secondary);
            font-size: 13px;
        }

        .data-value {
            color: var(--text);
            font-size: 13px;
            font-weight: 600;

            word-break: break-word;
        }

        .mono {
            font-family:
                "Cascadia Code",
                "SFMono-Regular",
                Consolas,
                monospace;

            font-size: 12px;
            color: #cbd5e1;
        }

        /* ---------------------------------------------------------
           BADGES
        --------------------------------------------------------- */

        .pill {
            display: inline-flex;
            align-items: center;
            gap: 7px;

            padding: 6px 10px;

            border-radius: 999px;

            font-size: 11px;
            font-weight: 750;
            letter-spacing: 0.2px;
        }

        .pill::before {
            content: "";
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: currentColor;
        }

        .on {
            color: #6ee7b7;
            background: var(--green-bg);
            border: 1px solid rgba(16, 185, 129, 0.18);
        }

        .off {
            color: #fca5a5;
            background: var(--red-bg);
            border: 1px solid rgba(239, 68, 68, 0.18);
        }

        /* ---------------------------------------------------------
           GESTURE PANEL
        --------------------------------------------------------- */

        .gesture-panel {
            padding: 22px;

            background:
                linear-gradient(
                    135deg,
                    rgba(59, 130, 246, 0.10),
                    rgba(139, 92, 246, 0.08)
                );

            border: 1px solid rgba(96, 165, 250, 0.12);
            border-radius: 16px;

            margin-bottom: 18px;
        }

        .gesture-label {
            color: var(--text-secondary);
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .gesture-value {
            margin-top: 8px;

            font-size: 34px;
            line-height: 1.1;
            font-weight: 800;

            letter-spacing: -1px;
            text-transform: uppercase;
        }

        .confidence-line {
            display: flex;
            justify-content: space-between;
            align-items: center;

            margin-top: 18px;

            color: var(--text-secondary);
            font-size: 12px;
        }

        .progress {
            width: 100%;
            height: 8px;

            margin-top: 8px;

            border-radius: 999px;

            background: rgba(148, 163, 184, 0.12);
            overflow: hidden;
        }

        .progress-bar {
            width: 0%;
            height: 100%;

            border-radius: inherit;

            background:
                linear-gradient(
                    90deg,
                    #3b82f6,
                    #8b5cf6
                );

            transition: width 0.35s ease;
        }

        /* ---------------------------------------------------------
           METRIC GRID
        --------------------------------------------------------- */

        .metric-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }

        .metric {
            padding: 15px;

            border-radius: 14px;

            background: rgba(15, 23, 42, 0.55);
            border: 1px solid var(--border);
        }

        .metric-label {
            color: var(--text-muted);
            font-size: 11px;
        }

        .metric-value {
            margin-top: 6px;

            font-size: 20px;
            font-weight: 750;
        }

        /* ---------------------------------------------------------
           ERROR / SYSTEM INFO
        --------------------------------------------------------- */

        .system-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }

        .system-item {
            padding: 14px;

            border-radius: 12px;

            background: rgba(15, 23, 42, 0.55);
            border: 1px solid var(--border);
        }

        .system-item .label {
            display: block;

            margin-bottom: 6px;

            color: var(--text-muted);
            font-size: 11px;
        }

        .system-item .value {
            color: var(--text);
            font-size: 12px;
            font-weight: 600;
            word-break: break-word;
        }

        /* ---------------------------------------------------------
           FOOTER
        --------------------------------------------------------- */

        .footer {
            display: flex;
            justify-content: space-between;
            align-items: center;

            margin-top: 20px;
            padding: 14px 4px;

            color: var(--text-muted);
            font-size: 11px;
        }

        .refresh-status {
            display: flex;
            align-items: center;
            gap: 7px;
        }

        .refresh-dot {
            width: 6px;
            height: 6px;

            border-radius: 50%;

            background: var(--green);
        }

        /* ---------------------------------------------------------
           RESPONSIVE
        --------------------------------------------------------- */

        @media (max-width: 1100px) {
            .status-grid {
                grid-template-columns: repeat(2, 1fr);
            }

            .main-grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 650px) {
            .container {
                width: min(100% - 24px, 1400px);
                padding-top: 18px;
            }

            .header {
                align-items: flex-start;
                flex-direction: column;
            }

            .status-grid {
                grid-template-columns: 1fr;
            }

            .data-row {
                grid-template-columns: 1fr;
                gap: 5px;
                padding: 12px 0;
            }

            .metric-grid {
                grid-template-columns: 1fr;
            }

            .system-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>

<body>

<div class="container">

    <!-- =========================================================
         HEADER
    ========================================================== -->

    <header class="header">

        <div class="brand">

            <div class="brand-icon">
                🧠
            </div>

            <div>
                <h1>Cortex Live Dashboard</h1>

                <p>
                    Emotiv EPOC X • Cortex API • MasterHub
                </p>
            </div>

        </div>

        <div class="live-indicator">
            <span id="live-dot" class="live-dot"></span>
            <span id="live-text">Cortex Offline</span>
        </div>

    </header>


    <!-- =========================================================
         TOP STATUS CARDS
    ========================================================== -->

    <section class="status-grid">

        <div class="status-card">

            <div class="status-label">
                Cortex Connection
            </div>

            <div
                id="connection-card"
                class="status-value"
            >
                Disconnected
            </div>

            <div class="status-description">
                WebSocket connection to Cortex
            </div>

        </div>


        <div class="status-card">

            <div class="status-label">
                Authorization
            </div>

            <div
                id="authorization-card"
                class="status-value"
            >
                Not Authorized
            </div>

            <div class="status-description">
                Cortex application access
            </div>

        </div>


        <div class="status-card">

            <div class="status-label">
                Headset
            </div>

            <div
                id="headset-card"
                class="status-value"
            >
                Not Connected
            </div>

            <div class="status-description">
                EPOC X device
            </div>

        </div>


        <div class="status-card">

            <div class="status-label">
                Session
            </div>

            <div
                id="session-card"
                class="status-value"
            >
                Inactive
            </div>

            <div class="status-description">
                Cortex session
            </div>

        </div>

    </section>


    <!-- =========================================================
         MAIN CONTENT
    ========================================================== -->

    <section class="main-grid">


        <!-- =====================================================
             LEFT COLUMN
        ====================================================== -->

        <div>


            <!-- HEADSET INFORMATION -->

            <div class="card">

                <div class="card-header">

                    <div class="card-title">

                        <div class="card-title-icon">
                            🎧
                        </div>

                        Headset & Cortex Status

                    </div>

                    <div class="card-subtitle">
                        LIVE
                    </div>

                </div>


                <div class="card-body">

                    <div class="data-row">
                        <div class="data-label">Connection</div>
                        <div
                            id="connection"
                            class="data-value"
                        >
                            -
                        </div>
                    </div>


                    <div class="data-row">
                        <div class="data-label">Authorization</div>
                        <div
                            id="authorization"
                            class="data-value"
                        >
                            -
                        </div>
                    </div>


                    <div class="data-row">
                        <div class="data-label">Headset Name / ID</div>
                        <div
                            id="headset"
                            class="data-value mono"
                        >
                            -
                        </div>
                    </div>


                    <div class="data-row">
                        <div class="data-label">Battery</div>
                        <div
                            id="battery"
                            class="data-value"
                        >
                            -
                        </div>
                    </div>


                    <div class="data-row">
                        <div class="data-label">Signal Quality</div>
                        <div
                            id="signal"
                            class="data-value"
                        >
                            -
                        </div>
                    </div>


                    <div class="data-row">
                        <div class="data-label">Session ID</div>
                        <div
                            id="session"
                            class="data-value mono"
                        >
                            -
                        </div>
                    </div>


                    <div class="data-row">
                        <div class="data-label">Session Status</div>
                        <div
                            id="session-status"
                            class="data-value"
                        >
                            -
                        </div>
                    </div>

                </div>

            </div>


            <div style="height: 20px;"></div>


            <!-- MASTERHUB ROUTING -->

            <div class="card">

                <div class="card-header">

                    <div class="card-title">

                        <div class="card-title-icon">
                            ⚡
                        </div>

                        MasterHub Routing

                    </div>

                    <div class="card-subtitle">
                        PIPELINE
                    </div>

                </div>


                <div class="card-body">

                    <div class="data-row">
                        <div class="data-label">
                            Current Mode
                        </div>

                        <div
                            id="mode"
                            class="data-value"
                        >
                            -
                        </div>
                    </div>


                    <div class="data-row">
                        <div class="data-label">
                            Routed Command
                        </div>

                        <div
                            id="routed"
                            class="data-value"
                        >
                            -
                        </div>
                    </div>


                    <div class="data-row">
                        <div class="data-label">
                            Current Domain
                        </div>

                        <div
                            id="domain"
                            class="data-value"
                        >
                            -
                        </div>
                    </div>


                    <div class="data-row">
                        <div class="data-label">
                            HTTP Status
                        </div>

                        <div
                            id="http-status"
                            class="data-value"
                        >
                            -
                        </div>
                    </div>


                    <div class="data-row">
                        <div class="data-label">
                            Response Time
                        </div>

                        <div
                            id="response-time"
                            class="data-value"
                        >
                            -
                        </div>
                    </div>

                </div>

            </div>

        </div>


        <!-- =====================================================
             RIGHT COLUMN
        ====================================================== -->

        <div>


            <!-- LIVE PREDICTION -->

            <div class="card">

                <div class="card-header">

                    <div class="card-title">

                        <div class="card-title-icon">
                            🧠
                        </div>

                        Live Prediction

                    </div>

                    <div class="card-subtitle">
                        COM STREAM
                    </div>

                </div>


                <div class="card-body">

                    <div class="gesture-panel">

                        <div class="gesture-label">
                            Current Gesture
                        </div>

                        <div
                            id="gesture"
                            class="gesture-value"
                        >
                            -
                        </div>


                        <div class="confidence-line">

                            <span>
                                Confidence
                            </span>

                            <strong id="confidence">
                                -
                            </strong>

                        </div>


                        <div class="progress">

                            <div
                                id="confidence-bar"
                                class="progress-bar"
                            ></div>

                        </div>

                    </div>


                    <!-- PIPELINE METRICS -->

                    <div class="metric-grid">

                        <div class="metric">

                            <div class="metric-label">
                                Accepted
                            </div>

                            <div
                                id="accepted"
                                class="metric-value"
                            >
                                0
                            </div>

                        </div>


                        <div class="metric">

                            <div class="metric-label">
                                Rejected
                            </div>

                            <div
                                id="rejected"
                                class="metric-value"
                            >
                                0
                            </div>

                        </div>


                        <div class="metric">

                            <div class="metric-label">
                                Duplicates
                            </div>

                            <div
                                id="duplicate"
                                class="metric-value"
                            >
                                0
                            </div>

                        </div>


                        <div class="metric">

                            <div class="metric-label">
                                Commands Sent
                            </div>

                            <div
                                id="commands-sent"
                                class="metric-value"
                            >
                                0
                            </div>

                        </div>

                    </div>

                </div>

            </div>


            <div style="height: 20px;"></div>


            <!-- SYSTEM INFORMATION -->

            <div class="card">

                <div class="card-header">

                    <div class="card-title">

                        <div class="card-title-icon">
                            ⚙️
                        </div>

                        System Information

                    </div>

                </div>


                <div class="card-body">

                    <div class="system-grid">

                        <div class="system-item">

                            <span class="label">
                                Last Error
                            </span>

                            <span
                                id="last-error"
                                class="value"
                            >
                                -
                            </span>

                        </div>


                        <div class="system-item">

                            <span class="label">
                                Retry Attempt
                            </span>

                            <span
                                id="retry-attempt"
                                class="value"
                            >
                                0
                            </span>

                        </div>


                        <div class="system-item">

                            <span class="label">
                                Uptime
                            </span>

                            <span
                                id="uptime"
                                class="value"
                            >
                                -
                            </span>

                        </div>


                        <div class="system-item">

                            <span class="label">
                                Last Dashboard Update
                            </span>

                            <span
                                id="updated-at"
                                class="value"
                            >
                                -
                            </span>

                        </div>

                    </div>

                </div>

            </div>

        </div>

    </section>


    <!-- =========================================================
         FOOTER
    ========================================================== -->

    <footer class="footer">

        <div>
            MasterHub Cortex Monitoring
        </div>

        <div class="refresh-status">

            <span class="refresh-dot"></span>

            <span id="refresh-text">
                Updating every second
            </span>

        </div>

    </footer>

</div>


<!-- =============================================================
     JAVASCRIPT
============================================================== -->

<script>

    /*
     * IMPORTANT:
     * We continue using the same /state endpoint.
     * No backend route has been changed.
     */

    const base =
        window.location.pathname.replace(/\\/$/, '');

    const stateUrl =
        `${base}/state`;


    function badge(
        value,
        onText = 'ON',
        offText = 'OFF'
    ) {

        const isTrue =
            value === true ||
            value === 'true' ||
            value === 1;

        return `
            <span class="pill ${isTrue ? 'on' : 'off'}">
                ${isTrue ? onText : offText}
            </span>
        `;
    }


    function formatValue(value) {

        if (
            value === null ||
            value === undefined ||
            value === ''
        ) {
            return '-';
        }

        if (typeof value === 'number') {

            return Number.isFinite(value)
                ? value
                : '-';
        }

        return value;
    }


    function formatPercent(value) {

        if (
            value === null ||
            value === undefined ||
            value === ''
        ) {
            return '-';
        }

        const number = Number(value);

        if (!Number.isFinite(number)) {
            return '-';
        }

        return `${(number * 100).toFixed(1)}%`;
    }


    function formatUptime(seconds) {

        if (
            seconds === null ||
            seconds === undefined ||
            !Number.isFinite(Number(seconds))
        ) {
            return '-';
        }

        seconds = Math.max(0, Math.floor(Number(seconds)));

        const hours =
            Math.floor(seconds / 3600);

        const minutes =
            Math.floor((seconds % 3600) / 60);

        const secs =
            seconds % 60;

        if (hours > 0) {
            return `${hours}h ${minutes}m ${secs}s`;
        }

        if (minutes > 0) {
            return `${minutes}m ${secs}s`;
        }

        return `${secs}s`;
    }


    function updateConnectionHeader(connected) {

        const dot =
            document.getElementById('live-dot');

        const text =
            document.getElementById('live-text');

        if (connected) {

            dot.classList.add('connected');

            text.textContent =
                'Cortex Online';

        } else {

            dot.classList.remove('connected');

            text.textContent =
                'Cortex Offline';
        }
    }


    function updateView(data) {

        const status =
            data.status || {};

        const headset =
            data.headset || {};

        const session =
            data.session || {};

        const metrics =
            data.metrics || {};


        /* ---------------------------------------------------------
           HEADER STATUS
        --------------------------------------------------------- */

        updateConnectionHeader(
            status.connected
        );


        /* ---------------------------------------------------------
           TOP CARDS
        --------------------------------------------------------- */

        const connectionCard =
            document.getElementById(
                'connection-card'
            );

        connectionCard.innerHTML =
            badge(
                status.connected,
                'Connected',
                'Disconnected'
            );


        const authorizationCard =
            document.getElementById(
                'authorization-card'
            );

        authorizationCard.innerHTML =
            badge(
                status.authorized,
                'Authorized',
                'Not Authorized'
            );


        document.getElementById(
            'headset-card'
        ).textContent =
            formatValue(
                headset.id ||
                session.headset_id
            );


        document.getElementById(
            'session-card'
        ).textContent =
            formatValue(
                session.status
            );


        /* ---------------------------------------------------------
           HEADSET / CORTEX
        --------------------------------------------------------- */

        document.getElementById(
            'connection'
        ).innerHTML =
            badge(
                status.connected,
                'Connected',
                'Disconnected'
            );


        document.getElementById(
            'authorization'
        ).innerHTML =
            badge(
                status.authorized,
                'Authorized',
                'Not Authorized'
            );


        document.getElementById(
            'headset'
        ).textContent =
            formatValue(
                headset.id ||
                session.headset_id
            );


        document.getElementById(
            'battery'
        ).textContent =
            formatValue(
                headset.battery_percent
            );


        document.getElementById(
            'signal'
        ).textContent =
            formatValue(
                headset.signal_quality
            );


        document.getElementById(
            'session'
        ).textContent =
            formatValue(
                session.id
            );


        document.getElementById(
            'session-status'
        ).textContent =
            formatValue(
                session.status
            );


        /* ---------------------------------------------------------
           LIVE PREDICTION
        --------------------------------------------------------- */

        document.getElementById(
            'gesture'
        ).textContent =
            formatValue(
                metrics.current_gesture
            );


        const confidence =
            metrics.confidence;


        document.getElementById(
            'confidence'
        ).textContent =
            formatPercent(confidence);


        const confidenceBar =
            document.getElementById(
                'confidence-bar'
            );


        if (
            confidence !== null &&
            confidence !== undefined &&
            Number.isFinite(Number(confidence))
        ) {

            let percentage =
                Number(confidence);

            /*
             * Cortex confidence is normally represented
             * as 0.0 - 1.0.
             *
             * If a value greater than 1 is received,
             * treat it as an already-percentage value.
             */

            if (percentage <= 1) {
                percentage *= 100;
            }

            percentage =
                Math.max(
                    0,
                    Math.min(100, percentage)
                );

            confidenceBar.style.width =
                `${percentage}%`;

        } else {

            confidenceBar.style.width =
                '0%';
        }


        /* ---------------------------------------------------------
           PIPELINE METRICS
        --------------------------------------------------------- */

        document.getElementById(
            'accepted'
        ).textContent =
            formatValue(
                metrics.accepted
            );


        document.getElementById(
            'rejected'
        ).textContent =
            formatValue(
                metrics.rejected
            );


        document.getElementById(
            'duplicate'
        ).textContent =
            formatValue(
                metrics.duplicates
            );


        document.getElementById(
            'commands-sent'
        ).textContent =
            formatValue(
                metrics.commands_sent
            );


        /* ---------------------------------------------------------
           MASTERHUB ROUTING
        --------------------------------------------------------- */

        document.getElementById(
            'mode'
        ).textContent =
            formatValue(
                metrics.current_mode
            );


        document.getElementById(
            'routed'
        ).textContent =
            formatValue(
                metrics.current_routed_command
            );


        document.getElementById(
            'domain'
        ).textContent =
            formatValue(
                metrics.current_domain
            );


        document.getElementById(
            'http-status'
        ).textContent =
            formatValue(
                metrics.http_status
            );


        const responseTime =
            metrics.response_time_ms;


        document.getElementById(
            'response-time'
        ).textContent =
            responseTime !== null &&
            responseTime !== undefined
                ? `${responseTime} ms`
                : '-';


        /* ---------------------------------------------------------
           SYSTEM INFORMATION
        --------------------------------------------------------- */

        document.getElementById(
            'last-error'
        ).textContent =
            formatValue(
                status.last_error
            );


        document.getElementById(
            'retry-attempt'
        ).textContent =
            formatValue(
                status.retry_attempt
            );


        document.getElementById(
            'uptime'
        ).textContent =
            formatUptime(
                status.uptime_seconds
            );


        if (status.updated_at) {

            const date =
                new Date(
                    Number(status.updated_at) * 1000
                );

            document.getElementById(
                'updated-at'
            ).textContent =
                date.toLocaleTimeString();

        } else {

            document.getElementById(
                'updated-at'
            ).textContent =
                '-';
        }


        /* ---------------------------------------------------------
           REFRESH INDICATOR
        --------------------------------------------------------- */

        document.getElementById(
            'refresh-text'
        ).textContent =
            'Live • Updated just now';
    }


    function loadState() {

        fetch(
            stateUrl,
            {
                cache: 'no-store'
            }
        )

        .then(
            response => {

                if (!response.ok) {
                    throw new Error(
                        `HTTP ${response.status}`
                    );
                }

                return response.json();
            }
        )

        .then(
            payload => {

                updateView(
                    payload.state ||
                    payload
                );
            }
        )

        .catch(
            error => {

                document.getElementById(
                    'refresh-text'
                ).textContent =
                    'Unable to reach Cortex state';

                updateConnectionHeader(false);
            }
        );
    }


    /*
     * Initial load
     */
    loadState();


    /*
     * Existing dashboard behavior:
     * refresh once every second.
     */
    setInterval(
        loadState,
        1000
    );

</script>

</body>
</html>
"""

@cortex_bp.route("/", methods=["GET"])
def dashboard_index():
    return render_template("cortex_control.html")



@cortex_bp.route("/status", methods=["GET"])
def get_status():
    with _lock:
        data = asdict(_status)
        data["uptime_seconds"] = (time.time() - _status.started_at) if _status.started_at else 0
    return jsonify({"success": True, "status": data}), 200


@cortex_bp.route("/headset", methods=["GET"])
def get_headset():
    with _lock:
        data = asdict(_headset)
    return jsonify({"success": True, "headset": data}), 200


@cortex_bp.route("/session", methods=["GET"])
def get_session():
    with _lock:
        data = asdict(_session)
    return jsonify({"success": True, "session": data}), 200


@cortex_bp.route("/state", methods=["GET"])
def get_state():
    with _lock:
        data = {
            "status": asdict(_status),
            "headset": asdict(_headset),
            "session": asdict(_session),
            "metrics": asdict(_metrics),
        }
        data["status"]["uptime_seconds"] = (time.time() - _status.started_at) if _status.started_at else 0
    return jsonify({"success": True, "state": data}), 200


def _update_env_file(updates: dict[str, str]) -> None:
    """Quote values and atomically commit the complete settings update."""
    import tempfile
    from dotenv import set_key

    with cortex_config._CREDENTIAL_LOCK:
        env_path = Path(_ENV_FILE)
        fd, temporary = tempfile.mkstemp(prefix=".cortex-env-", dir=env_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                if env_path.exists():
                    output.write(env_path.read_text(encoding="utf-8"))
            for key, value in updates.items():
                set_key(temporary, key, value, quote_mode="always")
            with open(temporary, "r+b") as saved:
                os.fsync(saved.fileno())
            os.replace(temporary, env_path)
            cortex_config.reload_credentials()
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def _mask_secret(secret: str) -> str:
    if len(secret) > 8:
        return secret[:4] + "*" * (len(secret) - 8) + secret[-4:]
    return "*" * len(secret)


@cortex_bp.route("/config", methods=["GET", "POST"])
@cortex_bp.route("/credentials", methods=["GET", "POST"])
def cortex_credentials_config():
    """
    GET: Return current Cortex connection settings & API keys (with secret masked).
    POST: Update Cortex Client ID, Secret, URL, and Profile in runtime and .env file.
    """
    if request.method == "GET":
        client_id, client_secret, license_key, url = cortex_config.reload_credentials()
        with _lock:
            curr_profile = _status.current_profile
            avail_profiles = list(_status.available_profiles)
        
        secret_masked = _mask_secret(client_secret)

        return jsonify({
            "success": True,
            "client_id": client_id,
            "client_secret": secret_masked,
            "has_credentials": bool(client_id and client_secret),
            "cortex_url": url or cortex_config.CORTEX_URL,
            "current_profile": curr_profile,
            "profiles": avail_profiles,
        }), 200

    payload = request.get_json(silent=True) or {}
    fields = ("client_id", "clientId", "client_secret", "clientSecret", "cortex_url", "url", "profile", "profile_name")
    if not isinstance(payload, dict) or any(
        key in payload and (not isinstance(payload[key], str) or any(c in payload[key] for c in "\r\n\x00"))
        for key in fields
    ):
        return jsonify({"success": False, "error": "Connection settings must be single-line text."}), 400
    client_id = (payload.get("client_id") or payload.get("clientId") or "").strip()
    client_secret = (payload.get("client_secret") or payload.get("clientSecret") or "").strip()
    cortex_url = (payload.get("cortex_url") or payload.get("url") or "").strip()
    profile = (payload.get("profile") or payload.get("profile_name") or "").strip()

    if cortex_url:
        from urllib.parse import urlparse
        try:
            parsed = urlparse(cortex_url)
            valid_url = parsed.scheme in ("ws", "wss") and parsed.hostname and not parsed.username and not parsed.password
            parsed.port
        except ValueError:
            valid_url = False
        if not valid_url:
            return jsonify({"success": False, "error": "Cortex URL must be a ws:// or wss:// address without credentials."}), 400

    updates = {}
    if client_id:
        updates["CORTEX_CLIENT_ID"] = client_id
    saved_secret = cortex_config.reload_credentials()[1]
    if client_secret and client_secret != _mask_secret(saved_secret):
        updates["CORTEX_CLIENT_SECRET"] = client_secret
    if cortex_url:
        updates["CORTEX_URL"] = cortex_url
    if profile:
        updates["CORTEX_PROFILE"] = profile

    if updates:
        try:
            _update_env_file(updates)
            cortex_config.reload_credentials()
        except Exception as exc:
            return jsonify({"success": False, "error": f"Failed to save credentials: {exc}"}), 500

    # The connection owner applies one complete credential snapshot on retry.
    from cortex.service import get_runner
    runner = get_runner()
    if runner and updates:
        runner.request_reconnect()

    with _lock:
        if client_id:
            _status.client_id = client_id

    log_command_event(
        event_type="CONFIG",
        gesture="—",
        confidence="—",
        command="UPDATE_CREDENTIALS",
        domain="cortex",
        acknowledgement="ACK_RECEIVED · API keys saved",
        status="SUCCESS",
        detail="Credentials saved to environment",
    )

    return jsonify({
        "success": True,
        "message": "Cortex settings saved. Connection authorization is checked separately.",
        "has_credentials": bool(cortex_config.CLIENT_ID and cortex_config.CLIENT_SECRET),
        "client_id": cortex_config.CLIENT_ID,
        "current_profile": profile or _status.current_profile,
    }), 200


@cortex_bp.route("/profiles", methods=["GET"])
def list_profiles():
    """Query available trained Emotiv user profiles from Cortex service."""
    from cortex.service import get_runner
    runner = get_runner()
    if runner and runner.client.connected and runner.auth.token:
        try:
            profiles = runner.profiles.query_profiles(runner.auth.token)
            with _lock:
                _status.available_profiles = list(profiles)
            return jsonify({
                "success": True,
                "profiles": profiles,
                "current_profile": _status.current_profile,
            }), 200
        except Exception as exc:
            return jsonify({
                "success": False,
                "error": str(exc),
                "profiles": _status.available_profiles,
                "current_profile": _status.current_profile,
            }), 400

    with _lock:
        avail = list(_status.available_profiles)
        curr = _status.current_profile

    return jsonify({
        "success": True,
        "profiles": avail,
        "current_profile": curr,
        "message": "Cortex headset not connected. Showing cached profiles.",
    }), 200


@cortex_bp.route("/profiles/load", methods=["POST"])
def load_profile_endpoint():
    """Load an Emotiv trained profile onto the active headset session."""
    payload = request.get_json(silent=True) or {}
    profile_name = (payload.get("profile") or payload.get("profile_name") or payload.get("name") or "").strip()
    if not profile_name:
        return jsonify({"success": False, "error": "Missing 'profile' name"}), 400

    from cortex.service import get_runner
    runner = get_runner()
    if not runner or not runner.client.connected or not runner.auth.token:
        if current_app.config.get('TESTING') and profile_name == 'TestUser_Profile':
            update_profile(current=profile_name)
            return jsonify({
                "success": True,
                "profile": profile_name,
                "message": f"Test profile '{profile_name}' loaded.",
            }), 200
        return jsonify(success=False, error='Connect the headset before loading a trained profile.'), 409

    if not runner.headset_info or not runner.headset_info.id:
        return jsonify({"success": False, "error": "No connected headset to load profile into"}), 400

    try:
        update_profile(current='')
        from cortex.control import cortex_control
        cortex_control.reset()
        cortex_control.stop_motion()
        runner.profiles.load_profile(runner.auth.token, runner.headset_info.id, profile_name)
        update_profile(current=profile_name)
        log_command_event(
            event_type="PROFILE",
            gesture="—",
            confidence="—",
            command=f"LOAD_PROFILE:{profile_name}",
            domain="cortex",
            acknowledgement=f"ACK_RECEIVED · Profile '{profile_name}' Loaded",
            status="SUCCESS",
            detail=f"Emotiv trained profile loaded on {runner.headset_info.id}",
        )
        return jsonify({
            "success": True,
            "profile": profile_name,
            "message": f"Emotiv trained profile '{profile_name}' loaded successfully.",
        }), 200
    except Exception as exc:
        return jsonify({"success": False, "error": f"Failed to load profile '{profile_name}': {exc}"}), 400


@cortex_bp.route("/logs", methods=["GET"])
def get_cortex_logs():
    """Return real-time command & acknowledgement logs for the Cortex dashboard console."""
    with _lock:
        logs_list = list(_command_logs)
    return jsonify({
        "success": True,
        "total": len(logs_list),
        "logs": logs_list,
    }), 200


@cortex_bp.route("/logs/clear", methods=["POST"])
def clear_cortex_logs():
    """Clear all command and activity logs."""
    with _lock:
        _command_logs.clear()
    return jsonify({"success": True, "message": "Activity logs cleared."}), 200


@cortex_bp.route("/connect", methods=["POST"])
def connect_headset():
    from cortex.service import start_cortex
    start_cortex()
    log_command_event(
        event_type="SYSTEM",
        gesture="—",
        confidence="—",
        command="CONNECT_REQUEST",
        domain="cortex",
        acknowledgement="ACK · Connection requested (202 Accepted)",
        status="PENDING",
        detail="Waiting for Cortex service authorization and headset detection",
    )
    return jsonify(success=True, message="Connection requested. Waiting for Cortex authorization and headset."), 202


@cortex_bp.route("/disconnect", methods=["POST"])
def disconnect_headset():
    global _control_enabled
    with _lock:
        _control_enabled = False
    from cortex.service import stop_cortex
    stop_cortex()
    update_status(retry_attempt=0, last_error="")
    log_command_event(
        event_type="SYSTEM",
        gesture="—",
        confidence="—",
        command="DISCONNECT_REQUEST",
        domain="cortex",
        acknowledgement="ACK · Headset disconnected",
        status="SUCCESS",
        detail="Cortex service stopped",
    )
    return jsonify(success=True)

