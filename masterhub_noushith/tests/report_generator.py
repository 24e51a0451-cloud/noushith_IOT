"""
report_generator.py
--------------------
Produces the console report plus report.json / report.csv / report.html
in REPORT_OUTPUT_DIR.
"""

import datetime
import html
import os

from masterhub.tests.utils import Color, save_csv, save_json, truncate

BANNER_WIDTH = 70


def print_banner(title: str):
    print("=" * BANNER_WIDTH)
    print(Color.bold(title.center(BANNER_WIDTH)))
    print("=" * BANNER_WIDTH)


def print_console_report(results: list, generation_warnings: list, verbose: bool = True):
    print_banner("MASTERHUB AUTOMATED GESTURE VALIDATION")
    print()

    if generation_warnings:
        for gesture, mode_key in generation_warnings:
            print(Color.yellow(
                f"WARNING  gesture_map.json entry '{gesture}' -> '{mode_key}' does not "
                f"correspond to any mode registered in mode_map.json (unreachable, skipped)."
            ))
        print()

    if verbose:
        for r in results:
            tc = r.test_case
            print(f"Test {tc.index}")
            print(f"{'-' * 50}")
            print(f"Gesture           : {tc.gesture}")
            print(f"Current Mode      : {tc.mode}")
            print(f"Expected Command  : {tc.expected_command}")
            print(f"Actual Command    : {r.actual_command}")
            if tc.expected_type == "domain_action":
                print(f"Expected Domain   : {tc.expected_domain}")
                print(f"Actual Domain     : {r.actual_domain}")
                print(f"Expected Action   : {tc.expected_action}")
                print(f"Actual Action     : {r.actual_action}")
            print(f"Expected Success  : {tc.expected_success}")
            print(f"Actual Success    : {r.actual_success}")
            print(f"HTTP Status       : {r.http_status}")
            print(f"Execution Time    : {r.elapsed_ms:.1f} ms")

            if r.status == "PASS":
                status_str = Color.green("PASS")
            elif r.status == "SKIPPED":
                status_str = Color.yellow("SKIPPED")
            else:
                status_str = Color.red("FAIL")
            print(f"Result            : {status_str}")

            if r.reasons:
                for reason in r.reasons:
                    print(Color.red(f"  - {reason}"))
            if not r.log_verified and r.status != "SKIPPED":
                print(Color.yellow("  ! Log evidence incomplete for this test (see log_notes in report)"))
            if r.error and r.status != "PASS":
                print(Color.dim(f"  error: {truncate(r.error, 120)}"))
            print("-" * 50)
            print()

    print_summary(results)


def print_summary(results: list):
    total = len(results)
    skipped = sum(1 for r in results if r.status == "SKIPPED")
    executed = total - skipped
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    accuracy = (passed / executed * 100) if executed else 0.0
    total_time = sum(r.elapsed_ms for r in results) / 1000

    print("=" * BANNER_WIDTH)
    print(Color.bold("SUMMARY"))
    print(f"Total Tests       : {total}")
    print(f"Executed          : {executed}")
    print(f"Skipped           : {skipped}")
    print(f"Passed            : {Color.green(str(passed))}")
    print(f"Failed            : {Color.red(str(failed)) if failed else '0'}")
    print(f"Accuracy          : {accuracy:.2f}%")
    print(f"Execution Time    : {total_time:.2f}s")
    print("=" * BANNER_WIDTH)


def write_reports(results: list, config, generation_warnings: list):
    rows = [r.to_dict() for r in results]

    total = len(results)
    skipped = sum(1 for r in results if r.status == "SKIPPED")
    executed = total - skipped
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    accuracy = (passed / executed * 100) if executed else 0.0
    total_time = sum(r.elapsed_ms for r in results) / 1000

    summary = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "total_tests": total,
        "executed": executed,
        "skipped": skipped,
        "passed": passed,
        "failed": failed,
        "accuracy_percent": round(accuracy, 2),
        "execution_time_seconds": round(total_time, 2),
        "generation_warnings": [
            {"gesture": g, "orphaned_mode_key": m} for g, m in generation_warnings
        ],
    }

    save_json(config.REPORT_JSON_PATH, {"summary": summary, "results": rows})

    fieldnames = [
        "index", "gesture", "mode", "expected_command", "actual_command",
        "expected_type", "expected_domain", "actual_domain",
        "expected_action", "actual_action", "expected_success",
        "actual_success", "status", "reasons", "log_verified", "log_notes",
        "elapsed_ms", "http_status", "error", "note",
    ]
    csv_rows = []
    for row in rows:
        flat = dict(row)
        flat["reasons"] = "; ".join(row["reasons"])
        flat["log_notes"] = "; ".join(row["log_notes"])
        csv_rows.append(flat)
    save_csv(config.REPORT_CSV_PATH, csv_rows, fieldnames)

    _write_html_report(config.REPORT_HTML_PATH, summary, rows)


def _write_html_report(path: str, summary: dict, rows: list):
    def esc(value):
        return html.escape(str(value)) if value is not None else ""

    table_rows = []
    for row in rows:
        status_class = {
            "PASS": "pass",
            "FAIL": "fail",
            "SKIPPED": "skipped",
        }.get(row["status"], "")
        reasons = "<br>".join(esc(r) for r in row["reasons"]) if row["reasons"] else ""
        log_notes = "<br>".join(esc(n) for n in row["log_notes"]) if row["log_notes"] else ""
        table_rows.append(f"""
        <tr class="{status_class}">
            <td>{esc(row['index'])}</td>
            <td>{esc(row['gesture'])}</td>
            <td>{esc(row['mode'])}</td>
            <td>{esc(row['expected_command'])}</td>
            <td>{esc(row['actual_command'])}</td>
            <td>{esc(row['expected_domain'])}</td>
            <td>{esc(row['actual_domain'])}</td>
            <td>{esc(row['expected_action'])}</td>
            <td>{esc(row['actual_action'])}</td>
            <td>{esc(row['expected_success'])}</td>
            <td>{esc(row['actual_success'])}</td>
            <td>{esc(row['elapsed_ms'])} ms</td>
            <td class="status-cell">{esc(row['status'])}</td>
            <td>{reasons}</td>
            <td>{'yes' if row['log_verified'] else 'no'}<br>{log_notes}</td>
        </tr>""")

    warnings_html = ""
    if summary.get("generation_warnings"):
        items = "".join(
            f"<li>gesture <code>{esc(w['gesture'])}</code> -> "
            f"<code>{esc(w['orphaned_mode_key'])}</code> (unreachable, no such mode registered)</li>"
            for w in summary["generation_warnings"]
        )
        warnings_html = f"""
        <div class="warning-box">
            <strong>Configuration warnings</strong>
            <ul>{items}</ul>
        </div>"""

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MasterHub Automated Gesture Validation Report</title>
<style>
    body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 2rem; background: #0f1115; color: #e6e6e6; }}
    h1 {{ font-size: 1.4rem; }}
    .summary {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
    .card {{ background: #1b1e26; border-radius: 8px; padding: 1rem 1.5rem; min-width: 120px; }}
    .card .label {{ font-size: 0.75rem; color: #9aa0aa; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card .value {{ font-size: 1.6rem; font-weight: 700; margin-top: 0.25rem; }}
    .value.green {{ color: #4ade80; }}
    .value.red {{ color: #f87171; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; }}
    th, td {{ border: 1px solid #2a2e38; padding: 0.4rem 0.6rem; text-align: left; vertical-align: top; }}
    th {{ background: #1b1e26; position: sticky; top: 0; }}
    tr.pass {{ background: rgba(74, 222, 128, 0.06); }}
    tr.fail {{ background: rgba(248, 113, 113, 0.08); }}
    tr.skipped {{ background: rgba(250, 204, 21, 0.06); }}
    .status-cell {{ font-weight: 700; }}
    tr.pass .status-cell {{ color: #4ade80; }}
    tr.fail .status-cell {{ color: #f87171; }}
    tr.skipped .status-cell {{ color: #facc15; }}
    .warning-box {{ background: rgba(250, 204, 21, 0.08); border: 1px solid #facc15; border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem; }}
    code {{ background: #262b35; padding: 0.1rem 0.3rem; border-radius: 4px; }}
    footer {{ margin-top: 1.5rem; color: #6b7280; font-size: 0.8rem; }}
</style>
</head>
<body>
<h1>MasterHub Automated Gesture Validation Report</h1>
<div class="summary">
    <div class="card"><div class="label">Total</div><div class="value">{summary['total_tests']}</div></div>
    <div class="card"><div class="label">Executed</div><div class="value">{summary['executed']}</div></div>
    <div class="card"><div class="label">Skipped</div><div class="value">{summary['skipped']}</div></div>
    <div class="card"><div class="label">Passed</div><div class="value green">{summary['passed']}</div></div>
    <div class="card"><div class="label">Failed</div><div class="value red">{summary['failed']}</div></div>
    <div class="card"><div class="label">Accuracy</div><div class="value">{summary['accuracy_percent']}%</div></div>
    <div class="card"><div class="label">Time</div><div class="value">{summary['execution_time_seconds']}s</div></div>
</div>
{warnings_html}
<table>
<thead>
<tr>
    <th>#</th><th>Gesture</th><th>Mode</th><th>Expected Cmd</th><th>Actual Cmd</th>
    <th>Expected Domain</th><th>Actual Domain</th><th>Expected Action</th><th>Actual Action</th>
    <th>Expected Success</th><th>Actual Success</th><th>Time</th><th>Result</th><th>Reasons</th><th>Log Verified</th>
</tr>
</thead>
<tbody>
{"".join(table_rows)}
</tbody>
</table>
<footer>Generated {esc(summary['generated_at'])}</footer>
</body>
</html>"""

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html_doc)
