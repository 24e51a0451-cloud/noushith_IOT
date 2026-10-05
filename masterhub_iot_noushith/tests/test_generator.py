"""
test_generator.py
------------------
Builds the full set of gesture/mode test cases entirely from MasterHub's
own configuration files:

    mappings/gesture_map.json   -> which gestures exist
    mappings/mode_map.json      -> which modes exist, and which commands
                                    switch the FSM into them
    mappings/command_map.json   -> which commands are real domain actions,
                                    and what domain/action they resolve to

NOTHING here is hardcoded. If you add a new gesture, a new mode, or a new
command mapping to MasterHub's JSON files, re-running this framework
automatically picks it up with zero code changes — that's the whole point
of MasterHub's "config-driven" design (see core/state.py's docstring) and
this test framework mirrors it exactly.

For every (gesture, mode) pair, the expected outcome is classified as
exactly one of:

    "domain_action"   -> resolves to a command in command_map.json;
                          expect success=True with a matching domain/action.
    "mode_switch"      -> resolves to one of mode_map.json's switch_command
                          values; expect success=True, type="mode_switch".
    "unknown_command"  -> resolves to a string that is in neither
                          command_map.json nor the switch-command set;
                          MasterHub's CommandValidator will reject it, so
                          expect success=False with an "Unknown command"
                          error (this is CORRECT behaviour, not a bug —
                          e.g. gesture_map.json's "neutral" entries are
                          intentionally not real commands).
    "unresolvable"     -> the gesture has no entry for this mode AND no
                          "default" fallback; MasterHub's InputProcessor
                          raises ValueError before reaching the engine at
                          all, so expect an HTTP 400 with an error message.
"""

import os

from tests.utils import load_json


class TestCase:
    __slots__ = (
        "index", "gesture", "mode", "expected_command", "expected_type",
        "expected_domain", "expected_action", "expected_success", "note",
    )

    def __init__(self, index, gesture, mode, expected_command, expected_type,
                 expected_domain=None, expected_action=None,
                 expected_success=True, note=None):
        self.index = index
        self.gesture = gesture
        self.mode = mode
        self.expected_command = expected_command
        self.expected_type = expected_type
        self.expected_domain = expected_domain
        self.expected_action = expected_action
        self.expected_success = expected_success
        self.note = note

    def to_dict(self):
        return {
            "index": self.index,
            "gesture": self.gesture,
            "mode": self.mode,
            "expected_command": self.expected_command,
            "expected_type": self.expected_type,
            "expected_domain": self.expected_domain,
            "expected_action": self.expected_action,
            "expected_success": self.expected_success,
            "note": self.note,
        }


class TestGenerator:
    def __init__(self, gesture_map_path, mode_map_path, command_map_path,
                 exclude_gestures=None, exclude_modes=None):
        for label, path in (
            ("gesture_map.json", gesture_map_path),
            ("mode_map.json", mode_map_path),
            ("command_map.json", command_map_path),
        ):
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"Could not find {label} at expected path: {path}\n"
                    f"Check GESTURE_MAP_PATH / MODE_MAP_PATH / COMMAND_MAP_PATH "
                    f"in config.py, or confirm the 'tests' folder sits directly "
                    f"inside your MasterHub project root."
                )

        gesture_data = load_json(gesture_map_path)
        mode_data = load_json(mode_map_path)
        command_data = load_json(command_map_path)

        self.exclude_gestures = set(exclude_gestures or [])
        self.exclude_modes = set(exclude_modes or [])

        # Strip "_comment"-style metadata keys, keep only real entries.
        self.gestures = {
            k: v for k, v in gesture_data.items()
            if not k.startswith("_") and k not in self.exclude_gestures
        }

        modes_section = mode_data.get("modes", {})
        self.modes = [
            name for name in modes_section
            if name not in self.exclude_modes
        ]

        self.command_map = {k: v for k, v in command_data.items() if not k.startswith("_")}

        # command string -> mode name it switches into
        self.mode_switch_commands = {
            entry.get("switch_command"): name
            for name, entry in modes_section.items()
            if isinstance(entry, dict) and entry.get("switch_command")
        }

        self.warnings = self._detect_orphaned_mode_keys()

    def _detect_orphaned_mode_keys(self):
        """
        Flag gesture_map.json mode-keys that don't correspond to any mode
        registered in mode_map.json. These entries are dead configuration —
        they can never be reached because InputProcessor validates any
        explicit mode override against the Mode enum built from
        mode_map.json, and the FSM can never enter an unregistered mode.
        Surfaced as a warning, not an error or a test failure.
        """
        known = set(self.modes) | {"default"}
        orphans = []
        for gesture, rules in self.gestures.items():
            if not isinstance(rules, dict):
                continue
            for key in rules:
                if key.startswith("_"):
                    continue
                if key not in known:
                    orphans.append((gesture, key))
        return orphans

    def generate(self):
        cases = []
        index = 1
        for gesture, rules in self.gestures.items():
            if not isinstance(rules, dict):
                continue
            for mode in self.modes:
                expected_command = rules.get(mode, rules.get("default"))
                cases.append(self._build_case(index, gesture, mode, expected_command))
                index += 1
        return cases

    def _build_case(self, index, gesture, mode, expected_command):
        if expected_command is None:
            return TestCase(
                index, gesture, mode, None, "unresolvable",
                expected_success=False,
                note=(f"Gesture '{gesture}' has no mapping for mode '{mode}' "
                      f"and no 'default' fallback in gesture_map.json"),
            )

        if expected_command in self.mode_switch_commands:
            return TestCase(
                index, gesture, mode, expected_command, "mode_switch",
                expected_success=True,
            )

        if expected_command in self.command_map:
            entry = self.command_map[expected_command]
            return TestCase(
                index, gesture, mode, expected_command, "domain_action",
                expected_domain=entry.get("domain"),
                expected_action=entry.get("action"),
                expected_success=True,
            )

        return TestCase(
            index, gesture, mode, expected_command, "unknown_command",
            expected_success=False,
            note=(f"Resolved command '{expected_command}' is not present in "
                  f"command_map.json — CommandValidator is expected to reject it"),
        )
