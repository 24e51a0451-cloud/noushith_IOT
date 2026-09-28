"""
api/routes.py
-------------
Minimal Flask API surface. The APrI laye's only job is:
    - parse the HTTP request
    - hand the payload to InputProcessor -> Engine
    - translate results/exceptions into HTTP responses

No business logic, no domain knowledge, no routing decisions live here.
"""

import json
import os
import time
from collections import deque

from flask import Blueprint, jsonify, request

from core.devices import device_registry
from core.engine import engine
from core.input_processor import input_processor
from core.metrics import metrics_tracker
from core.state import state_manager
from services.command_validator import command_validator
from services.logger_service import LOG_FILE, get_logger
from services.mqtt_service import (
    mqtt_service,
    get_all_online_devices,
    get_all_device_states,
    get_all_sensor_data,
    get_robot_car_state,
    get_wheelchair_state,
    LAST_ACKS,
)
from services.usb_service import usb_service

log = get_logger("api.routes")

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/command", methods=["POST"])
def handle_command():
    """
    Main entry point for the whole system.

    Body (JSON), one of:
        { "command": "left_light_on" }
        { "gesture": "push" }
        { "gesture": "push", "mode": "MEDIA_MODE" }
        { "eeg_window": [[...], [...]] }

    Optional:
        { "params": { ... } }   extra parameters for the action
                                 (e.g. {"query": "lofi beats"} for youtube_search)
    """
    t_start = time.perf_counter()
    payload = request.get_json(silent=True)
    if payload is None:
        duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
        metrics_tracker.record_command(False, duration_ms, duration_ms, 0.0)
        return jsonify({
            "success": False,
            "error": "Request body must be valid JSON",
            "response_ms": duration_ms,
            "process_ms": duration_ms,
            "execution_ms": 0.0,
        }), 400

    try:
        normalized_command = input_processor.normalize(payload)
    except ValueError as exc:
        log.warning(f"Input normalization failed: {exc}")
        duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
        metrics_tracker.record_command(False, duration_ms, duration_ms, 0.0)
        return jsonify({
            "success": False,
            "error": str(exc),
            "response_ms": duration_ms,
            "process_ms": duration_ms,
            "execution_ms": 0.0,
        }), 400

    params = payload.get("params", {})
    if not isinstance(params, dict):
        duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
        metrics_tracker.record_command(False, duration_ms, duration_ms, 0.0)
        return jsonify({
            "success": False,
            "error": "'params' must be an object",
            "response_ms": duration_ms,
            "process_ms": duration_ms,
            "execution_ms": 0.0,
        }), 400

    params = dict(params)
    if normalized_command.startswith('mobile_jiosaavn_'):
        for field in ('query', 'confidence', 'Is_Actionable', 'source'):
            if field in payload and field not in params:
                params[field] = payload[field]
    if "target" in payload and "target" not in params:
        params["target"] = payload["target"]
    if "target_node" in payload and "target_node" not in params:
        params["target_node"] = payload["target_node"]

    try:
        result = engine.process(normalized_command, params)
    except Exception as exc:  # unexpected/programmer error
        log.exception(f"Unhandled error processing command '{normalized_command}'")
        duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
        metrics_tracker.record_command(False, duration_ms, duration_ms, 0.0)
        return jsonify({
            "success": False,
            "error": "Internal error",
            "detail": str(exc),
            "response_ms": duration_ms,
            "process_ms": duration_ms,
            "execution_ms": 0.0,
        }), 500

    duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
    result.setdefault("response_ms", duration_ms)
    result.setdefault("process_ms", duration_ms)
    result.setdefault("execution_ms", 0.0)

    status_code = 200 if result.get("success") else 422

    # Log real-time BCI mental command to console and shared activity feed
    try:
        from cortex.dashboard import log_command_event
        gesture = payload.get("gesture") or params.get("gesture")
        conf_raw = params.get("confidence", payload.get("confidence"))
        source_raw = str(params.get("source") or payload.get("source") or "").strip().lower()
        if source_raw in ("manual", "manual_keyboard", "keyboard", "ui", "ui_button", "manual_button", "keyboard_arrow"):
            is_bci = False
        elif source_raw in ("bci", "cortex", "emotiv", "emotiv_cortex", "emotiv-cortex", "emotiv_simulator", "bci_headset", "bci_mental"):
            is_bci = True
        else:
            is_bci = bool(gesture)

        conf_str = "—"
        if conf_raw is not None:
            try:
                c_val = float(conf_raw)
                conf_str = f"{c_val * 100:.1f}%" if c_val <= 1.0 else f"{c_val:.1f}%"
            except (ValueError, TypeError):
                conf_str = str(conf_raw)

        domain = result.get("domain", "system")
        action = result.get("action", normalized_command)
        success_bool = bool(result.get("success"))

        if is_bci:
            log.info(
                f"🧠 [BCI MENTAL COMMAND] Gesture: '{gesture or normalized_command}' "
                f"(Conf: {conf_str}) -> Mapped: '{normalized_command}' "
                f"[{domain} · {action}] -> HTTP {status_code} ({duration_ms:.1f}ms)"
            )
        else:
            log.info(
                f"⚡ [COMMAND] '{normalized_command}' [{domain}] -> HTTP {status_code} ({duration_ms:.1f}ms)"
            )

        ack_msg = f"ACK_RECEIVED · {status_code} OK ({duration_ms:.1f}ms)" if success_bool else f"FAILED · {status_code} ({result.get('error', 'error')})"
        if result.get('status') == 'PENDING':
            ack_msg = 'PENDING · Sent to phone; awaiting execution acknowledgement'
        log_command_event(
            event_type="BCI" if is_bci else "COMMAND",
            gesture=gesture or (normalized_command if is_bci else "—"),
            confidence=conf_str,
            command=normalized_command,
            domain=domain,
            acknowledgement=ack_msg,
            status="SUCCESS" if success_bool else "FAILED",
            detail=f"Mode: {result.get('state', {}).get('mode', 'IDLE')} · Action: {action}",
        )

        if is_bci:
            from services.bci_logger_service import bci_logger
            bci_logger.log_bci_command(
                gesture=gesture or normalized_command,
                confidence=float(conf_raw) if conf_raw is not None else 1.0,
                accepted=success_bool,
                routed_command=normalized_command,
                domain=domain,
                action=action,
                status="SUCCESS" if success_bool else "FAILED",
                response_time_ms=duration_ms,
            )
        else:
            from services.manual_logger_service import manual_logger
            manual_logger.log_manual_command(
                command=normalized_command,
                gesture=gesture,
                input_type=params.get("input_type", "keyboard_arrow" if gesture else "ui_button"),
                keys_pressed=params.get("keys", ""),
                routed_command=normalized_command,
                domain=domain,
                action=action,
                status="SUCCESS" if success_bool else "FAILED",
                response_time_ms=duration_ms,
                mode=result.get("state", {}).get("mode", "IDLE"),
            )
    except Exception as log_exc:
        log.debug(f"Could not record activity log event: {log_exc}")

    return jsonify(result), status_code


@api_bp.route("/config/temporal-window", methods=["GET", "POST"])
def temporal_window_config():
    """
    GET /api/config/temporal-window: Return current temporal window framing value.
    POST /api/config/temporal-window: Update temporal window value, bounded between 2.0s and 10.0s.
    """
    if request.method == "GET":
        return jsonify({
            "success": True,
            "temporal_window": metrics_tracker.get_temporal_window(),
            "min": 2.0,
            "max": 10.0,
        }), 200

    payload = request.get_json(silent=True) or {}
    val = payload.get("temporal_window")
    if val is None:
        val = payload.get("value")
    if val is None:
        val = payload.get("window")

    if val is None:
        return jsonify({
            "success": False,
            "error": "Missing 'temporal_window' or 'value' field in JSON request body",
        }), 400

    try:
        updated = metrics_tracker.set_temporal_window(val)
        return jsonify({
            "success": True,
            "temporal_window": updated,
            "min": 2.0,
            "max": 10.0,
        }), 200
    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "min": 2.0,
            "max": 10.0,
        }), 400


@api_bp.route("/metrics", methods=["GET"])
def get_metrics():
    """
    GET /api/metrics: Return real-time performance metrics HUD telemetry.
    """
    return jsonify({
        "success": True,
        "metrics": metrics_tracker.get_metrics(),
    }), 200


@api_bp.route("/metrics/reset", methods=["POST"])
def reset_metrics():
    """Reset accumulated latency and command metrics."""
    metrics_tracker.reset()
    return jsonify({
        "success": True,
        "message": "Metrics reset successfully",
    }), 200


@api_bp.route("/state", methods=["GET"])
def get_state():
    """Read-only snapshot of the current FSM state — useful for debugging/UI."""
    return jsonify({"success": True, "state": state_manager.snapshot()}), 200


@api_bp.route("/commands", methods=["GET"])
def list_commands():
    """List all commands the system currently recognizes."""
    return jsonify({"success": True, "commands": command_validator.all_commands()}), 200


@api_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"success": True, "status": "ok"}), 200


@api_bp.route("/stats", methods=["GET"])
def get_stats():
    """Return a lightweight runtime stats snapshot for dashboards and telemetry."""
    return jsonify({
        "success": True,
        "stats": {
            "state": state_manager.snapshot(),
            "commands_total": len(command_validator.all_commands()),
        },
    }), 200


@api_bp.route("/iot/status", methods=["GET"])
def get_iot_status():
    """Return live IoT device registration, actuator states, and sensor telemetry."""
    return jsonify({
        "success": True,
        "mqtt_connected": mqtt_service._connected,
        "broker": f"{mqtt_service.host}:{mqtt_service.port}",
        "online_devices": get_all_online_devices(),
        "states": get_all_device_states(),
        "sensors": get_all_sensor_data(),
        "last_acks": LAST_ACKS,
    }), 200


@api_bp.route("/iot/devices", methods=["GET"])
def list_iot_devices():
    """Return all active online IoT devices."""
    return jsonify({
        "success": True,
        "devices": get_all_online_devices(),
    }), 200


@api_bp.route("/iot/ping", methods=["POST", "GET"])
def ping_iot_device():
    """Send a PING to the ESP32 node."""
    ok = mqtt_service.ping_esp32()
    return jsonify({"success": ok, "message": "PING sent to iot/esp32/ping"}), 200


@api_bp.route("/embedded/status", methods=["GET"])
def get_embedded_status():
    """Return live status, obstacle alerts, motion state, and last ACKs for Embedded mobility nodes."""
    return jsonify({
        "success": True,
        "mqtt_connected": mqtt_service._connected,
        "robot_car": get_robot_car_state(),
        "wheelchair": get_wheelchair_state(),
        "online_devices": get_all_online_devices(),
        "last_acks": LAST_ACKS,
    }), 200


@api_bp.route("/embedded/car", methods=["POST"])
def control_robot_car():
    """Directly send movement action to the ESP32-C6 Robot Car Slave."""
    payload = request.get_json(silent=True) or {}
    action = payload.get("action") or payload.get("command") or "car_stop"
    from actions.embedded.handler import embedded_handler
    result = embedded_handler.execute(action, params=payload)
    status_code = 200 if result.get("success") else 422
    return jsonify(result), status_code


# -------------------------------------------------------------
# PC AGENT & TARGET NODE DEVICE REGISTRY
# -------------------------------------------------------------

@api_bp.route("/devices", methods=["GET"])
def list_devices():
    """Return all registered target PC devices and active target node."""
    from services.mobile_mqtt_service import mobile_mqtt_service
    return jsonify({
        "success": True,
        "active_target": device_registry.get_active_target(),
        "devices": mobile_mqtt_service.merge_target_presence(device_registry.list_all()),
    }), 200


@api_bp.route("/devices", methods=["POST"])
@api_bp.route("/devices/register", methods=["POST"])
def register_device():
    """Register or update a target PC node (matches pc_agent _register_with_masterhub)."""
    payload = request.get_json(silent=True) or {}
    device_id = payload.get("device_id") or payload.get("deviceId")
    if not device_id:
        return jsonify({"success": False, "error": "Missing 'device_id'"}), 400

    name = payload.get("name") or payload.get("device_name")
    transport = payload.get("transport", "mqtt")
    capabilities = payload.get("capabilities", ["desktop", "ai_ml"])
    status = payload.get("status", "OFFLINE")
    device_type = payload.get("device_type", "computer")
    platform = payload.get("platform", "windows")

    device = device_registry.register(
        device_id=device_id,
        name=name,
        transport=transport,
        capabilities=capabilities,
        status=status,
        device_type=device_type,
        platform=platform,
    )
    return jsonify({
        "success": True,
        "device": device,
        "active_target": device_registry.get_active_target(),
    }), 201


@api_bp.route("/devices/target", methods=["POST"])
def set_active_target():
    """Select the active target node for Desktop and AI/ML command dispatch."""
    payload = request.get_json(silent=True) or {}
    target = payload.get("target") or payload.get("device_id") or payload.get("target_node")
    if not target:
        return jsonify({"success": False, "error": "Missing 'target' or 'device_id'"}), 400

    active = device_registry.set_active_target(str(target))
    return jsonify({
        "success": True,
        "active_target": active,
    }), 200


@api_bp.route("/devices/<device_id>", methods=["DELETE"])
def unregister_device(device_id: str):
    """Unregister a target PC node."""
    ok = device_registry.unregister(device_id)
    if not ok:
        return jsonify({"success": False, "error": f"Device '{device_id}' cannot be removed or not found"}), 404
    return jsonify({
        "success": True,
        "message": f"Device '{device_id}' removed",
        "active_target": device_registry.get_active_target(),
    }), 200


@api_bp.route("/usb/ports", methods=["GET"])
def get_usb_ports():
    """List available USB COM serial ports."""
    ports = usb_service.list_ports()
    status = usb_service.get_status()
    return jsonify({
        "success": True,
        "ports": ports,
        "connected_port": status.get("port"),
        "is_connected": status.get("connected", False),
        "status": status,
    }), 200


@api_bp.route("/usb/status", methods=["GET"])
def get_usb_status():
    """Get current USB connection state, telemetry and metrics."""
    return jsonify(usb_service.get_status()), 200


@api_bp.route("/usb/connect", methods=["POST"])
def connect_usb():
    """Connect to a USB Serial COM port."""
    payload = request.get_json(silent=True) or {}
    port = payload.get("port")
    if not port:
        return jsonify({"success": False, "error": "Missing 'port' parameter"}), 400
    baudrate = payload.get("baudrate", 115200)
    try:
        baudrate = int(baudrate)
    except (ValueError, TypeError):
        baudrate = 115200

    result = usb_service.connect(port=port, baudrate=baudrate)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@api_bp.route("/usb/disconnect", methods=["POST"])
def disconnect_usb():
    """Disconnect active USB serial link."""
    result = usb_service.disconnect()
    return jsonify(result), 200


def _read_log_lines(path: str, lines: int = 50) -> list[str]:
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return list(deque(handle, maxlen=lines))


@api_bp.route("/logs", methods=["GET"])
def get_logs():
    """Return the most recent lines from the MasterHub runtime log file."""
    try:
        lines = int(request.args.get("lines", 50))
    except (TypeError, ValueError):
        lines = 50

    if lines <= 0 or lines > 200:
        lines = 50

    raw_lines = _read_log_lines(LOG_FILE, lines)
    return jsonify({
        "success": True,
        "logs": [line.rstrip("\n") for line in raw_lines],
    }), 200


@api_bp.route("/activity-logs", methods=["GET"])
def get_activity_logs():
    """Return real-time BCI and system activity events for MasterHub console and telemetry."""
    from cortex.dashboard import _command_logs, _lock
    since_id = request.args.get("since_id", 0)
    try:
        since_id = int(since_id)
    except (ValueError, TypeError):
        since_id = 0

    with _lock:
        all_logs = list(_command_logs)

    if since_id > 0:
        filtered = [item for item in all_logs if item.get("id", 0) > since_id]
    else:
        filtered = all_logs

    return jsonify({
        "success": True,
        "total": len(all_logs),
        "count": len(filtered),
        "logs": filtered,
    }), 200


@api_bp.route("/activity-logs/clear", methods=["POST"])
def clear_activity_logs():
    """Clear all real-time activity events."""
    from cortex.dashboard import _command_logs, _lock
    with _lock:
        _command_logs.clear()
    return jsonify({"success": True, "message": "Activity logs cleared."}), 200


@api_bp.route("/bci/logs", methods=["GET"])
def get_bci_logs():
    """Return all stored BCI mental command log entries and recent events."""
    from services.bci_logger_service import bci_logger
    try:
        limit = int(request.args.get("limit", 100))
    except (TypeError, ValueError):
        limit = 100

    raw_lines = bci_logger.get_raw_log_lines(lines=limit)
    events = bci_logger.get_recent_events(limit=limit)

    return jsonify({
        "success": True,
        "total_events": len(events),
        "events": events,
        "raw_logs": [l.rstrip("\n") for l in raw_lines],
        "log_file": bci_logger.text_log_file,
        "jsonl_file": bci_logger.jsonl_log_file,
    }), 200


@api_bp.route("/bci/logs/export", methods=["GET"])
def export_bci_logs():
    """Export all stored BCI mental command records in JSON format."""
    from services.bci_logger_service import bci_logger
    events = bci_logger.get_recent_events(limit=0)
    return jsonify({
        "success": True,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_records": len(events),
        "records": events,
    }), 200


@api_bp.route("/bci/logs/clear", methods=["POST"])
def clear_bci_logs():
    """Clear stored BCI mental command log files."""
    from services.bci_logger_service import bci_logger
    bci_logger.clear_logs()
    return jsonify({"success": True, "message": "BCI command log files cleared."}), 200


@api_bp.route("/manual/logs", methods=["GET"])
def get_manual_logs():
    """Return all stored Manual & keyboard command log entries and recent events."""
    from services.manual_logger_service import manual_logger
    try:
        limit = int(request.args.get("limit", 100))
    except (TypeError, ValueError):
        limit = 100

    raw_lines = manual_logger.get_raw_log_lines(lines=limit)
    events = manual_logger.get_recent_events(limit=limit)

    return jsonify({
        "success": True,
        "total_events": len(events),
        "events": events,
        "raw_logs": [l.rstrip("\n") for l in raw_lines],
        "log_file": manual_logger.text_log_file,
        "jsonl_file": manual_logger.jsonl_log_file,
    }), 200


@api_bp.route("/manual/logs/export", methods=["GET"])
def export_manual_logs():
    """Export all stored Manual & keyboard command records in JSON format."""
    from services.manual_logger_service import manual_logger
    events = manual_logger.get_recent_events(limit=0)
    return jsonify({
        "success": True,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_records": len(events),
        "records": events,
    }), 200


@api_bp.route("/manual/logs/clear", methods=["POST"])
def clear_manual_logs():
    """Clear stored Manual command log files."""
    from services.manual_logger_service import manual_logger
    manual_logger.clear_logs()
    return jsonify({"success": True, "message": "Manual command log files cleared."}), 200


@api_bp.route("/random-json", methods=["POST", "GET"])
def execute_random_json():
    """Pick one command item from a JSON payload at random and execute it."""
    if request.method == "GET":
        payload = request.args.get("file", "data/sample_signals.json")
    else:
        payload = request.get_json(silent=True)

    if payload is None:
        payload = "data/sample_signals.json"

    try:
        result = engine.execute_random_from_json(payload)
    except Exception as exc:
        return jsonify({"success": False, "error": "Internal error", "detail": str(exc)}), 500

    status_code = 200 if result.get("success") else 422
    return jsonify(result), status_code


@api_bp.route("/eeg", methods=["GET", "POST"])
def process_eeg_file():
    """Read EEG command samples from a JSON file and run them through the engine."""
    file_path = request.args.get("file", "data/eeg_samples.json")
    full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), file_path)

    if not os.path.exists(full_path):
        return jsonify({"success": False, "error": f"File not found: {file_path}"}), 404

    try:
        with open(full_path, "r", encoding="utf-8") as handle:
            samples = json.load(handle)
    except json.JSONDecodeError as exc:
        return jsonify({"success": False, "error": f"Invalid JSON: {exc}"}), 400

    if not isinstance(samples, list):
        return jsonify({"success": False, "error": "EEG file must contain a JSON array"}), 400

    try:
        result = engine.execute_from_json(samples)
    except Exception as exc:
        return jsonify({"success": False, "error": "Internal error", "detail": str(exc)}), 500

    return jsonify(result), 200


@api_bp.route("/hardware/config", methods=["GET", "POST"])
def hardware_config():
    from services.hardware_config import read_config, save_config
    if request.method == "GET":
        return jsonify(success=True, config=read_config())
    try:
        config = save_config(request.get_json(silent=True))
    except ValueError as exc:
        return jsonify(success=False, error=str(exc)), 400
    mqtt_service.disconnect()
    mqtt_service.host, mqtt_service.port = config['host'], config['port']
    connected = mqtt_service.connect()
    return jsonify(success=True, connected=connected, config=config)


@api_bp.route("/hardware/connect", methods=["POST"])
def hardware_connect():
    connected = mqtt_service.connect()
    return jsonify(success=connected, broker=f"{mqtt_service.host}:{mqtt_service.port}"), (200 if connected else 503)


@api_bp.route('/workflow', methods=['GET'])
def get_workflow():
    from services.workflow_service import build_workflow
    return jsonify(success=True, **build_workflow())
