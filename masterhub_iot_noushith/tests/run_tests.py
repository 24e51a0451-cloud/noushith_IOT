#!/usr/bin/env python3
"""
run_tests.py
------------
Entry point for the MasterHub Automated Gesture Validation framework.

Usage (from your MasterHub project root, with the Flask server running):

    python tests/run_tests.py

What it does, end to end:
    1. Loads gesture_map.json / mode_map.json / command_map.json.
    2. Auto-discovers every gesture and every registered mode — nothing
       is hardcoded (see test_generator.py).
    3. Generates every valid (gesture, mode) test case and its expected
       outcome.
    4. Sends each gesture to the live MasterHub API (POST /api/command).
    5. Reads and regex-parses the new lines MasterHub wrote to its log
       file while handling that request.
    6. Validates the API response + log evidence against the expected
       outcome and records PASS / FAIL / SKIPPED.
    7. Prints a full console report and writes report.json / report.csv /
       report.html to tests/reports/.

This script imports its sibling modules directly (config, utils,
test_generator, gesture_sender, log_parser, validator,
report_generator) rather than as a package, specifically so it can sit
inside your project's existing "tests" folder without needing (or
overwriting) an __init__.py.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import masterhub.tests.config as config  # noqa: E402
from masterhub.tests.utils import Color, ensure_dir  # noqa: E402
from masterhub.tests.test_generator import TestGenerator  # noqa: E402
from masterhub.tests.gesture_sender import GestureSender  # noqa: E402
from masterhub.tests.log_parser import LogParser  # noqa: E402
import masterhub.tests.validator as validator  # noqa: E402
import masterhub.tests.report_generator as report_generator  # noqa: E402


def fail_fast(message: str, code: int = 1):
    print(Color.red(f"ERROR: {message}"))
    sys.exit(code)


def main():
    Color.configure(config.COLOR_OUTPUT)
    ensure_dir(config.REPORT_OUTPUT_DIR)

    print(Color.cyan("MasterHub Automated Gesture Validation"))
    print(Color.dim(f"Project root : {config.PROJECT_ROOT}"))
    print(Color.dim(f"API base URL : {config.API_BASE_URL}"))
    print(Color.dim(f"Log file     : {config.LOG_FILE_PATH}"))
    print()

    # ---- 1 & 2 & 3: generate test cases -----------------------------------
    try:
        generator = TestGenerator(
            gesture_map_path=config.GESTURE_MAP_PATH,
            mode_map_path=config.MODE_MAP_PATH,
            command_map_path=config.COMMAND_MAP_PATH,
            exclude_gestures=config.EXCLUDE_GESTURES,
            exclude_modes=config.EXCLUDE_MODES,
        )
    except FileNotFoundError as exc:
        fail_fast(str(exc))
        return

    test_cases = generator.generate()
    if not test_cases:
        fail_fast(
            "No test cases were generated. Check that mappings/gesture_map.json "
            "and mappings/mode_map.json contain at least one gesture and mode."
        )
        return

    print(f"Discovered {len(generator.gestures)} gesture(s) and "
          f"{len(generator.modes)} mode(s) -> {len(test_cases)} test case(s) generated.\n")

    # ---- Pre-flight: is the MasterHub server reachable? -------------------
    sender = GestureSender(
        base_url=config.API_BASE_URL,
        command_endpoint=config.API_COMMAND_ENDPOINT,
        health_endpoint=config.API_HEALTH_ENDPOINT,
        timeout=config.REQUEST_TIMEOUT,
    )
    healthy, detail = sender.check_health()
    if not healthy:
        fail_fast(
            f"Could not reach MasterHub at {config.API_BASE_URL} "
            f"({config.API_HEALTH_ENDPOINT}): {detail}\n"
            f"  -> Make sure MasterHub is running (python app.py) and that "
            f"API_BASE_URL in tests/config.py matches its host/port."
        )
        return

    # ---- Prime the log parser to only see lines from now on --------------
    log_parser = LogParser(config.LOG_FILE_PATH)
    log_parser.prime()
    if not log_parser.file_found:
        print(Color.yellow(
            f"WARNING: log file not found at {config.LOG_FILE_PATH}. "
            f"Tests will still run and PASS/FAIL using the API response, "
            f"but log cross-validation will be unavailable for every test."
        ))
    print()

    # ---- 4-6: execute each test case ---------------------------------------
    results = []
    for tc in test_cases:
        if tc.expected_type == "domain_action" and tc.expected_domain in config.SKIP_DOMAINS:
            result = validator.skipped_result(
                tc, f"Domain '{tc.expected_domain}' is in SKIP_DOMAINS (config.py)"
            )
            results.append(result)
            print(f"[{tc.index:>3}/{len(test_cases)}] {tc.gesture:<12} {tc.mode:<15} "
                  f"-> {str(tc.expected_command):<20} {Color.yellow('SKIPPED')}")
            continue

        send_result = sender.send_gesture(tc.gesture, tc.mode)
        time.sleep(config.LOG_READ_DELAY)
        new_lines = log_parser.read_new_lines()
        evidence = log_parser.parse_chunk(new_lines)

        result = validator.validate(tc, send_result, evidence)
        results.append(result)

        if result.status == "PASS":
            status_str = Color.green("PASS")
        elif result.status == "SKIPPED":
            status_str = Color.yellow("SKIPPED")
        else:
            status_str = Color.red("FAIL")
        print(f"[{tc.index:>3}/{len(test_cases)}] {tc.gesture:<12} {tc.mode:<15} "
              f"-> {str(tc.expected_command):<20} {status_str}")

        time.sleep(config.DELAY_BETWEEN_TESTS)

    print()

    # ---- 7: report ----------------------------------------------------------
    report_generator.print_console_report(results, generator.warnings, verbose=config.VERBOSE_CONSOLE)
    report_generator.write_reports(results, config, generator.warnings)

    print(f"\nDetailed reports written to:")
    print(f"  {config.REPORT_JSON_PATH}")
    print(f"  {config.REPORT_CSV_PATH}")
    print(f"  {config.REPORT_HTML_PATH}")

    failed = sum(1 for r in results if r.status == "FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
