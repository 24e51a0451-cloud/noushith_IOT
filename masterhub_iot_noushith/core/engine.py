"""
engine.py
---------
The Engine is the orchestrator. It does NOT know how to control Notepad,
publish MQTT, or move a wheelchair. It only:

    1. Validates the normalized command (via command_validator)
    2. Lets StateManager process mode-switch commands
    3. Asks the Router which domain/action the command belongs to
    4. Dispatches to the correct domain handler via a lookup table
       (NOT an if/elif chain)
    5. Records the result in StateManager history and returns it

Adding a 5th domain later = add one entry to _DOMAIN_HANDLERS, nothing
else in this file changes.
"""

import json
import os
import random
import time

from core.input_processor import input_processor
from core.router import router
from core.state import state_manager
from core.metrics import metrics_tracker
from services.command_validator import command_validator
from services.logger_service import get_logger

from actions.iot.handler import iot_handler
from actions.desktop.handler import desktop_handler
from actions.embedded.handler import embedded_handler
from actions.ai_ml.handler import ai_ml_handler

log = get_logger("core.engine")

# domain name -> object exposing .execute(action, params) -> dict
_DOMAIN_HANDLERS = {
    "iot": iot_handler,
    "desktop": desktop_handler,
    "embedded": embedded_handler,
    "ai_ml": ai_ml_handler,
}


class Engine:
    def _load_json_payload(self, source):
        if isinstance(source, (dict, list)):
            return source

        if isinstance(source, os.PathLike):
            source = os.fspath(source)

        if isinstance(source, str):
            if os.path.exists(source):
                with open(source, "r", encoding="utf-8") as handle:
                    return json.load(handle)

            try:
                return json.loads(source)
            except json.JSONDecodeError:
                return None

        return None

    def execute_from_json(self, source) -> dict:
        """
        Load a JSON payload from a file path or raw JSON data and execute each
        command entry through the engine.

        Supported formats:
            - a JSON array of command objects/strings
            - a JSON object with a top-level "commands" list
            - a single command object or string
        """
        data = self._load_json_payload(source)
        if data is None:
            return {"success": False, "error": "Invalid JSON payload"}

        if isinstance(data, dict):
            if isinstance(data.get("commands"), list):
                items = data["commands"]
            elif isinstance(data.get("items"), list):
                items = data["items"]
            else:
                items = [data]
        elif isinstance(data, list):
            items = data
        else:
            return {"success": False, "error": "JSON payload must be an object or array"}

        results = []
        for item in items:
            if isinstance(item, str):
                command = item.strip()
                params = {}
                normalized = command
                result = self.process(normalized, params)
                results.append({"command": command, "result": result})
                continue

            if not isinstance(item, dict):
                continue

            command = item.get("command")
            if isinstance(command, str) and command.strip():
                normalized = command
                params = item.get("params", {}) or {}
                if not isinstance(params, dict):
                    params = {}
                if "confidence" in item:
                    params["confidence"] = item.get("confidence")
                if "confidence_threshold" in item:
                    params["confidence_threshold"] = item.get("confidence_threshold")
                result = self.process(normalized, params)
                results.append({
                    "command": command,
                    "confidence": item.get("confidence"),
                    "threshold": item.get("confidence_threshold"),
                    "result": result,
                })
                continue

            try:
                normalized = input_processor.normalize(item)
            except Exception as exc:
                result = {"success": False, "error": str(exc)}
                results.append({
                    "input": item,
                    "normalized_command": None,
                    "result": result,
                })
                continue

            params = item.get("params", {}) or {}
            if not isinstance(params, dict):
                params = {}
            if "confidence" in item:
                params["confidence"] = item.get("confidence")
            if "confidence_threshold" in item:
                params["confidence_threshold"] = item.get("confidence_threshold")

            try:
                result = self.process(normalized, params)
            except Exception as exc:
                result = {"success": False, "error": str(exc)}

            results.append({
                "input": item,
                "normalized_command": normalized,
                "result": result,
            })

        return {"success": True, "processed": len(results), "results": results}

    def execute_random_from_json(self, source) -> dict:
        """
        Load a JSON payload, pick one eligible item at random, and execute it.
        """
        data = self._load_json_payload(source)
        if data is None:
            return {"success": False, "error": "Invalid JSON payload"}

        if isinstance(data, dict):
            items = data.get("commands") if isinstance(data.get("commands"), list) else data.get("items")
            if not isinstance(items, list):
                items = [data]
        elif isinstance(data, list):
            items = data
        else:
            return {"success": False, "error": "JSON payload must be an object or array"}

        if not items:
            return {"success": False, "error": "No commands found in JSON payload"}

        selected_item = random.choice(items)
        if isinstance(selected_item, str):
            command = selected_item.strip()
            params = {}
            result = self.process(command, params)
            return {
                "success": True,
                "selected_command": command,
                "source": "random_json",
                "result": result,
            }

        if not isinstance(selected_item, dict):
            return {"success": False, "error": "Selected JSON item is not a valid object"}

        command = selected_item.get("command")
        if isinstance(command, str) and command.strip():
            params = selected_item.get("params", {}) or {}
            if not isinstance(params, dict):
                params = {}
            if "confidence" in selected_item:
                params["confidence"] = selected_item.get("confidence")
            if "confidence_threshold" in selected_item:
                params["confidence_threshold"] = selected_item.get("confidence_threshold")
            result = self.process(command, params)
            return {
                "success": True,
                "selected_command": command,
                "source": "random_json",
                "result": result,
            }

        try:
            normalized = input_processor.normalize(selected_item)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        params = selected_item.get("params", {}) or {}
        if not isinstance(params, dict):
            params = {}
        if "confidence" in selected_item:
            params["confidence"] = selected_item.get("confidence")
        if "confidence_threshold" in selected_item:
            params["confidence_threshold"] = selected_item.get("confidence_threshold")

        result = self.process(normalized, params)
        return {
            "success": True,
            "selected_command": normalized,
            "source": "random_json",
            "result": result,
        }

    def process(self, normalized_command: str, params: dict = None) -> dict:
        """
        Main entry point used by the API layer. Takes an already-normalized
        command string (see core/input_processor.py) and runs it through
        the full pipeline. Returns a structured result dict, never raises
        for "expected" failure modes (unknown command, handler error) —
        only for programmer errors / unexpected exceptions, which the API
        layer converts to a 500.
        """
        t_start = time.perf_counter()
        params = params or {}

        def _finalize(result: dict, t_exec: float = 0.0) -> dict:
            t_end = time.perf_counter()
            total_ms = round((t_end - t_start) * 1000, 2)
            exec_ms = round(t_exec * 1000, 2)
            proc_ms = round(max(0.0, total_ms - exec_ms), 2)
            result.setdefault("response_ms", total_ms)
            result.setdefault("process_ms", proc_ms)
            result.setdefault("execution_ms", exec_ms)
            metrics_tracker.record_command(
                result.get("success", False),
                result["response_ms"],
                result["process_ms"],
                result["execution_ms"],
            )
            return result

        confidence = params.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                return _finalize({
                    "success": False,
                    "command": normalized_command,
                    "error": "confidence must be numeric",
                })

            default_thresh = float(os.getenv("BCI_CONFIDENCE_THRESHOLD", os.getenv("CONFIDENCE_THRESHOLD", "0.20")))
            threshold = params.get("confidence_threshold", default_thresh)
            try:
                threshold = float(threshold)
            except (TypeError, ValueError):
                threshold = default_thresh

            if confidence < threshold:
                state_manager.record_command(normalized_command)
                return _finalize({
                    "success": False,
                    "command": normalized_command,
                    "reason": "confidence_below_threshold",
                    "confidence": confidence,
                    "threshold": threshold,
                    "state": state_manager.snapshot(),
                })

        if normalized_command == 'neutral':
            return _finalize({'success': True, 'type': 'no_op', 'state': state_manager.snapshot()})

        # 1. Mode-switch commands are handled entirely by StateManager and
        #    short-circuit here — they don't route to a domain handler.
        if state_manager.maybe_switch_mode(normalized_command):
            state_manager.record_command(normalized_command)
            result = {
                "success": True,
                "type": "mode_switch",
                "command": normalized_command,
                "state": state_manager.snapshot(),
            }
            # Selecting an application through a gesture or a button opens the same target app.
            workflow_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mappings', 'workflow_map.json')
            with open(workflow_path, encoding='utf-8') as handle:
                workflow = json.load(handle)
            selected = next((info for info in workflow['devices'].values()
                             if info.get('mode') == state_manager.mode.value), None)
            if selected and selected.get('launch_command'):
                route = router.route(selected['launch_command'])
                launch = _DOMAIN_HANDLERS[route.domain].execute(route.action, params)
                result['launch'] = launch
                if not launch.get('success'):
                    result.update(success=False, error=launch.get('error', 'Application could not be opened'))
            log.info(f"Mode switch handled: {normalized_command}")
            return _finalize(result)

        # 2. Validate the command is known before doing anything else.
        if not command_validator.is_valid(normalized_command):
            log.warning(f"Engine rejected unknown command: '{normalized_command}'")
            return _finalize({
                "success": False,
                "command": normalized_command,
                "error": f"Unknown command: '{normalized_command}'",
            })

        # 3. Route to find domain + action.
        try:
            route = router.route(normalized_command)
        except ValueError as exc:
            log.error(str(exc))
            return _finalize({"success": False, "command": normalized_command, "error": str(exc)})

        # 4. Dispatch to the correct domain handler.
        handler = _DOMAIN_HANDLERS.get(route.domain)
        if handler is None:
            log.error(f"No handler registered for domain '{route.domain}'")
            return _finalize({
                "success": False,
                "command": normalized_command,
                "error": f"No handler registered for domain '{route.domain}'",
            })

        t_exec_start = time.perf_counter()
        result = handler.execute(route.action, params)
        t_exec_duration = time.perf_counter() - t_exec_start

        # 5. Record + enrich the result with routing context.
        state_manager.record_command(normalized_command)
        result.setdefault("domain", route.domain)
        result.setdefault("action", route.action)
        result["command"] = normalized_command
        result["state"] = state_manager.snapshot()

        log.info(f"Processed command '{normalized_command}' -> domain={route.domain} success={result.get('success')}")
        return _finalize(result, t_exec_duration)


engine = Engine()
