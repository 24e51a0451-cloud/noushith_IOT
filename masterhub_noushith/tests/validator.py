"""
validator.py
------------
Compares each TestCase's expected outcome against two independent sources
of truth:

    1. The MasterHub API's own JSON response (authoritative — it's the
       system telling you directly what it did).
    2. The regex-parsed log lines written by MasterHub while handling
       that same request (an independent, out-of-band confirmation).

PASS/FAIL is decided from the API response (source #1), since it's always
present and immediate. Log evidence (#2) is cross-checked for agreement
and surfaced as "log_verified" + "log_notes" — if the log doesn't confirm
what the API already told us (e.g. because of a flush delay), that's
reported as a WARNING, not a false FAIL, so a slow disk doesn't produce a
misleading test failure.
"""


class TestResult:
    def __init__(self, test_case, actual_command=None, actual_success=None,
                 actual_domain=None, actual_action=None, actual_type=None,
                 error=None, status="FAIL", reasons=None, log_verified=False,
                 log_notes=None, elapsed_ms=0.0, http_status=None, skipped=False):
        self.test_case = test_case
        self.actual_command = actual_command
        self.actual_success = actual_success
        self.actual_domain = actual_domain
        self.actual_action = actual_action
        self.actual_type = actual_type
        self.error = error
        self.status = status  # "PASS" | "FAIL" | "SKIPPED"
        self.reasons = reasons or []
        self.log_verified = log_verified
        self.log_notes = log_notes or []
        self.elapsed_ms = elapsed_ms
        self.http_status = http_status
        self.skipped = skipped

    def to_dict(self):
        tc = self.test_case
        return {
            "index": tc.index,
            "gesture": tc.gesture,
            "mode": tc.mode,
            "expected_command": tc.expected_command,
            "actual_command": self.actual_command,
            "expected_type": tc.expected_type,
            "expected_domain": tc.expected_domain,
            "actual_domain": self.actual_domain,
            "expected_action": tc.expected_action,
            "actual_action": self.actual_action,
            "expected_success": tc.expected_success,
            "actual_success": self.actual_success,
            "status": self.status,
            "reasons": self.reasons,
            "log_verified": self.log_verified,
            "log_notes": self.log_notes,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "http_status": self.http_status,
            "error": self.error,
            "note": tc.note,
        }


def validate(test_case, send_result, evidence) -> TestResult:
    reasons = []
    log_notes = []
    log_verified = False

    if not send_result.get("ok"):
        return TestResult(
            test_case,
            error=send_result.get("error"),
            status="FAIL",
            reasons=[f"HTTP request failed: {send_result.get('error')}"],
            elapsed_ms=send_result.get("elapsed", 0.0) * 1000,
            http_status=send_result.get("status_code"),
        )

    api_json = send_result.get("json") or {}
    actual_command = api_json.get("command")
    actual_success = api_json.get("success")
    actual_domain = api_json.get("domain")
    actual_action = api_json.get("action")
    actual_type = api_json.get("type")
    error = api_json.get("error") or send_result.get("error")

    tc = test_case

    # --- Universal checks -------------------------------------------------
    if actual_success != tc.expected_success:
        reasons.append(
            f"Execution success mismatch: expected {tc.expected_success}, got {actual_success}"
        )

    if tc.expected_command is not None and actual_command not in (tc.expected_command, None):
        # Some error paths (400-level, before normalization succeeds) never
        # get a 'command' field back; only flag a mismatch when one IS present.
        if actual_command != tc.expected_command:
            reasons.append(
                f"Command mismatch: expected '{tc.expected_command}', got '{actual_command}'"
            )

    # --- Type-specific checks ----------------------------------------------
    if tc.expected_type == "domain_action":
        if actual_domain != tc.expected_domain:
            reasons.append(f"Domain mismatch: expected '{tc.expected_domain}', got '{actual_domain}'")
        if actual_action != tc.expected_action:
            reasons.append(f"Action mismatch: expected '{tc.expected_action}', got '{actual_action}'")

        processed = evidence.get("processed_line")
        if processed:
            log_verified = True
            if processed.get("command") != tc.expected_command:
                log_notes.append(
                    f"Log 'Processed command' line shows command "
                    f"'{processed.get('command')}', expected '{tc.expected_command}'"
                )
            if processed.get("domain") != tc.expected_domain:
                log_notes.append(
                    f"Log 'Processed command' line shows domain "
                    f"'{processed.get('domain')}', expected '{tc.expected_domain}'"
                )
            if processed.get("success") != tc.expected_success:
                log_notes.append("Log 'Processed command' line success flag disagrees with expectation")
        else:
            log_notes.append("No 'Processed command' log line found in the read window")

        routed = evidence.get("routed_line")
        if routed and (routed.get("domain") != tc.expected_domain or routed.get("action") != tc.expected_action):
            log_notes.append("Log 'Routed: RouteResult(...)' line disagrees with expected domain/action")

    elif tc.expected_type == "mode_switch":
        if actual_type not in (None, "mode_switch"):
            reasons.append(f"Expected response type 'mode_switch', got '{actual_type}'")

        mode_switch_line = evidence.get("mode_switch_line")
        if mode_switch_line:
            log_verified = True
            if mode_switch_line.get("command") != tc.expected_command:
                log_notes.append(
                    f"Log 'Mode switch handled' line shows command "
                    f"'{mode_switch_line.get('command')}', expected '{tc.expected_command}'"
                )
        else:
            log_notes.append("No 'Mode switch handled' log line found in the read window")

        # A "State transition" log line is informational only — MasterHub's
        # StateManager treats a switch to the mode it's already in as a
        # successful no-op WITHOUT logging a transition line, so its
        # absence must never fail a mode_switch test.
        transition = evidence.get("transition_line")
        if transition:
            log_notes.append(
                f"Observed real FSM transition {transition.get('from_mode')} -> {transition.get('to_mode')}"
            )

    elif tc.expected_type == "unknown_command":
        if not error or "Unknown command" not in str(error):
            reasons.append(f"Expected an 'Unknown command' error, got: {error!r}")

        unknown_line = evidence.get("unknown_line")
        if unknown_line:
            log_verified = True
            if unknown_line.get("command") != tc.expected_command:
                log_notes.append(
                    f"Log 'rejected unknown command' line shows command "
                    f"'{unknown_line.get('command')}', expected '{tc.expected_command}'"
                )
        else:
            log_notes.append("No 'Engine rejected unknown command' log line found in the read window")

    else:  # "unresolvable"
        input_fail_line = evidence.get("input_fail_line")
        if input_fail_line:
            log_verified = True
        else:
            log_notes.append("No 'Input normalization failed' log line found in the read window")

    status = "PASS" if not reasons else "FAIL"

    return TestResult(
        tc,
        actual_command=actual_command,
        actual_success=actual_success,
        actual_domain=actual_domain,
        actual_action=actual_action,
        actual_type=actual_type,
        error=error,
        status=status,
        reasons=reasons,
        log_verified=log_verified,
        log_notes=log_notes,
        elapsed_ms=send_result.get("elapsed", 0.0) * 1000,
        http_status=send_result.get("status_code"),
    )


def skipped_result(test_case, reason: str) -> TestResult:
    return TestResult(test_case, status="SKIPPED", reasons=[reason], skipped=True)
