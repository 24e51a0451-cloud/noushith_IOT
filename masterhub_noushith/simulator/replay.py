"""
simulator/replay.py
---------------------
Entry point for Phase 1 of the Emotiv Cortex integration.

Reads emotiv_bci_predictions.json and replays it through:

    Prediction Reader -> Confidence Filter -> Gesture Stabilizer -> Sender -> MasterHub (POST /api/command)

exactly like a future live Cortex WebSocket stream will, without ever
importing or modifying MasterHub's own code.

Usage (from the MasterHub project root, i.e. one level above this
simulator/ folder):

    python -m simulator.replay
    python -m simulator.replay --speed 2
    python -m simulator.replay --speed 5 --threshold 0.85
    python -m simulator.replay --real-time
    python -m simulator.replay --file path\\to\\other_predictions.json
    python -m simulator.replay --limit 50

Run `python -m simulator.replay --help` for the full flag list.
"""

from __future__ import annotations

import argparse
import sys
import time

from prediction_pipeline import PredictionPipeline, SendResult
from simulator import config
from simulator.logger import get_logger
from simulator.prediction_reader import PredictionReader, PredictionReaderError
from simulator.utils import C, RunStats, colorize, enable_windows_ansi, fmt_ms, fmt_pct, pad

log = get_logger("replay")

# Column widths for the live console table.
_COLS = [
    ("#", 5),
    ("Timestamp", 15),
    ("Gesture", 9),
    ("Conf", 6),
    ("Mode", 14),
    ("Resolved Cmd", 16),
    ("Domain", 9),
    ("Action", 16),
    ("HTTP", 5),
    ("Resp", 7),
    ("Status", 8),
]

# Domain -> human summary bucket, per config.KNOWN_DOMAINS / router.py VALID_DOMAINS.
_DOMAIN_LABELS = {
    "desktop": "Desktop Commands",
    "iot": "IoT Commands",
    "embedded": "Embedded Commands",
    "ai_ml": "Media Commands",  # MEDIA_MODE is driven by the ai_ml domain, per mode_map.json
}


def _print_table_header() -> None:
    header = " | ".join(pad(name, w) for name, w in _COLS)
    print(colorize(header, C.BOLD + C.CYAN))
    print(colorize("-" * len(header), C.GRAY))


def _print_table_row(
    index: int,
    raw_timestamp: str,
    gesture: str,
    confidence: float,
    mode: str,
    resolved_command: str,
    domain: str,
    action: str,
    http_status,
    response_time_ms,
    status_label: str,
    status_color: str,
) -> None:
    ts_short = raw_timestamp.split(" ")[-1] if raw_timestamp else "-"
    row_values = [
        str(index),
        ts_short,
        gesture,
        fmt_pct(confidence),
        mode or "-",
        resolved_command or "-",
        domain or "-",
        action or "-",
        str(http_status) if http_status is not None else "-",
        fmt_ms(response_time_ms),
        status_label,
    ]
    cells = [pad(v, w) for v, (_, w) in zip(row_values, _COLS)]
    line = " | ".join(cells[:-1]) + " | " + colorize(cells[-1], status_color)
    print(line)


class ReplayEngine:
    """
    Orchestrates a full replay run: wires the reader, filter,
    stabilizer, and sender together, drives the console table, and
    produces the end-of-run summary.
    """

    def __init__(
        self,
        predictions_file: str,
        speed: float = config.DEFAULT_SPEED,
        real_time: bool = False,
        threshold: float = config.DEFAULT_CONFIDENCE_THRESHOLD,
        cooldown_ms: int = config.DEFAULT_STABILIZER_COOLDOWN_MS,
        command_url: str = config.COMMAND_URL,
        limit: int | None = None,
    ):
        self.predictions_file = predictions_file
        self.speed = speed
        self.real_time = real_time
        self.limit = limit

        self.reader = PredictionReader(predictions_file)
        self.pipeline = PredictionPipeline(threshold=threshold, cooldown_ms=cooldown_ms, url=command_url)
        self.confidence_filter = self.pipeline.confidence_filter
        self.stabilizer = self.pipeline.stabilizer
        self.sender = self.pipeline.sender

        self.stats = RunStats()
        self._last_mode = "-"

    def _sleep_between(self, prev_ts, curr_ts) -> None:
        if self.real_time and prev_ts is not None and curr_ts is not None:
            delay = (curr_ts - prev_ts).total_seconds()
            delay = max(0.0, delay)
        else:
            # Fixed-cadence fallback: MasterHub's own recordings run at
            # roughly 4Hz; scale that base interval by playback speed.
            base_interval = 0.25
            delay = base_interval / max(self.speed, 0.001)
        time.sleep(delay)

    def run(self) -> RunStats:
        total = len(self.reader)
        log.info(
            f"Starting replay: file={self.predictions_file} total={total} "
            f"speed={self.speed}x real_time={self.real_time} "
            f"threshold={self.confidence_filter.threshold} cooldown={self.stabilizer.cooldown_ms}ms "
            f"target={self.sender.url}"
        )
        print(colorize(f"\nReplaying {total} predictions from {self.predictions_file}", C.BOLD))
        print(colorize(f"Target: {self.sender.url}  |  Speed: {self.speed}x  |  Threshold: {self.confidence_filter.threshold}  |  Cooldown: {self.stabilizer.cooldown_ms}ms\n", C.DIM))
        _print_table_header()

        prev_ts = None
        pipeline = self.pipeline
        for prediction in self.reader.read():
            if self.limit is not None and prediction.index > self.limit:
                break

            self.stats.total_predictions += 1
            self.stats.confidences.append(prediction.confidence)

            pipeline_result = pipeline.process(prediction)
            filter_result = pipeline_result.filter_result
            if filter_result is not None and not filter_result.accepted:
                self.stats.rejected += 1
                _print_table_row(
                    prediction.index, prediction.raw_timestamp, prediction.gesture,
                    prediction.confidence, self._last_mode, None, None, None,
                    None, None, "REJECT", C.YELLOW,
                )
                log.info(
                    f"RESULT #{prediction.index} timestamp={prediction.raw_timestamp} "
                    f"gesture={prediction.gesture} confidence={prediction.confidence} "
                    f"mode={self._last_mode} resolved_command=- api_response=- success=False "
                    f"reason=below_confidence_threshold"
                )
                prev_ts = prediction.timestamp or prev_ts
                self._sleep_between(prev_ts, prediction.timestamp)
                continue

            self.stats.accepted += 1

            stabilizer_result = pipeline_result.stabilizer_result
            if stabilizer_result is not None and not stabilizer_result.accepted:
                self.stats.duplicates_skipped += 1
                _print_table_row(
                    prediction.index, prediction.raw_timestamp, prediction.gesture,
                    prediction.confidence, self._last_mode, None, None, None,
                    None, None, "SKIP", C.GRAY,
                )
                log.info(
                    f"RESULT #{prediction.index} timestamp={prediction.raw_timestamp} "
                    f"gesture={prediction.gesture} confidence={prediction.confidence} "
                    f"mode={self._last_mode} resolved_command=- api_response=- success=False "
                    f"reason=duplicate_within_cooldown"
                )
                prev_ts = prediction.timestamp or prev_ts
                self._sleep_between(prev_ts, prediction.timestamp)
                continue

            result: SendResult = pipeline_result.send_result
            assert result is not None
            self.stats.response_times_ms.append(result.response_time_ms)

            if result.success:
                self.stats.commands_executed += 1
                self.stats.record_domain(result.domain)
                self._last_mode = result.mode or self._last_mode
                status_label, status_color = "PASS", C.GREEN
            else:
                self.stats.failures += 1
                status_label, status_color = "FAIL", C.RED

            _print_table_row(
                prediction.index, prediction.raw_timestamp, prediction.gesture,
                prediction.confidence, result.mode or self._last_mode,
                result.resolved_command, result.domain, result.action,
                result.http_status, result.response_time_ms, status_label, status_color,
            )
            log.info(
                f"RESULT #{prediction.index} timestamp={prediction.raw_timestamp} "
                f"gesture={prediction.gesture} confidence={prediction.confidence} "
                f"mode={result.mode or self._last_mode} resolved_command={result.resolved_command or '-'} "
                f"api_response={result.http_status} success={result.success} "
                f"response_time_ms={result.response_time_ms:.1f}"
                + (f" error={result.error}" if result.error else "")
            )

            prev_ts = prediction.timestamp or prev_ts
            self._sleep_between(prev_ts, prediction.timestamp)

        self._print_summary()
        log.info("Replay finished")
        return self.stats

    def _print_summary(self) -> None:
        s = self.stats
        skipped_total = s.rejected + s.duplicates_skipped
        lines = [
            "",
            "=" * 50,
            colorize("Simulation Finished", C.BOLD),
            f"Total Predictions      : {s.total_predictions}",
            f"Accepted               : {s.accepted}",
            f"Rejected               : {s.rejected}",
            f"Commands Executed      : {s.commands_executed}",
            f"Skipped                : {skipped_total} ({s.rejected} low-confidence, {s.duplicates_skipped} duplicate)",
            f"Average Confidence     : {fmt_pct(s.avg_confidence)}",
            f"Average Response Time  : {fmt_ms(s.avg_response_time_ms)}",
            f"Desktop Commands       : {s.domain_counts.get('desktop', 0)}",
            f"IoT Commands           : {s.domain_counts.get('iot', 0)}",
            f"Embedded Commands      : {s.domain_counts.get('embedded', 0)}",
            f"Media Commands         : {s.domain_counts.get('ai_ml', 0)}",
            f"Failures               : {s.failures}",
            "=" * 50,
            "",
        ]
        print("\n".join(lines))
        log.info(
            "SUMMARY total=%d accepted=%d rejected=%d executed=%d skipped=%d "
            "avg_confidence=%.3f avg_response_ms=%.1f desktop=%d iot=%d embedded=%d media=%d failures=%d"
            % (
                s.total_predictions, s.accepted, s.rejected, s.commands_executed, skipped_total,
                s.avg_confidence, s.avg_response_time_ms,
                s.domain_counts.get("desktop", 0), s.domain_counts.get("iot", 0),
                s.domain_counts.get("embedded", 0), s.domain_counts.get("ai_ml", 0), s.failures,
            )
        )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="simulator.replay",
        description="Phase 1 Emotiv Cortex simulator: replays a recorded prediction JSON file into MasterHub over HTTP.",
    )
    parser.add_argument(
        "--file", default=config.DEFAULT_PREDICTIONS_FILE,
        help=f"Path to the prediction JSON file (default: {config.DEFAULT_PREDICTIONS_FILE})",
    )
    parser.add_argument(
        "--speed", type=float, choices=list(config.SUPPORTED_SPEEDS), default=config.DEFAULT_SPEED,
        help="Fixed playback speed multiplier (1, 2, or 5). Ignored if --real-time is set.",
    )
    parser.add_argument(
        "--real-time", action="store_true",
        help="Replay using the actual gaps between recorded timestamps instead of a fixed speed.",
    )
    parser.add_argument(
        "--threshold", type=float, default=config.DEFAULT_CONFIDENCE_THRESHOLD,
        help=f"Confidence filter threshold, 0.0-1.0 (default: {config.DEFAULT_CONFIDENCE_THRESHOLD}).",
    )
    parser.add_argument(
        "--cooldown", type=int, default=config.DEFAULT_STABILIZER_COOLDOWN_MS,
        help=f"Gesture stabilizer cooldown in milliseconds (default: {config.DEFAULT_STABILIZER_COOLDOWN_MS}).",
    )
    parser.add_argument(
        "--base-url", default=config.MASTERHUB_BASE_URL,
        help=f"MasterHub base URL (default: {config.MASTERHUB_BASE_URL}).",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only replay the first N predictions (useful for quick smoke tests).",
    )
    return parser


def main(argv=None) -> int:
    enable_windows_ansi()
    args = _build_arg_parser().parse_args(argv)

    command_url = f"{args.base_url}{config.COMMAND_ENDPOINT}"

    try:
        engine = ReplayEngine(
            predictions_file=args.file,
            speed=args.speed,
            real_time=args.real_time,
            threshold=args.threshold,
            cooldown_ms=args.cooldown,
            command_url=command_url,
            limit=args.limit,
        )
    except PredictionReaderError as exc:
        print(colorize(f"Failed to load predictions: {exc}", C.RED), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(colorize(f"Invalid configuration: {exc}", C.RED), file=sys.stderr)
        return 1

    try:
        engine.run()
    except KeyboardInterrupt:
        print(colorize("\nReplay interrupted by user.", C.YELLOW))
        engine._print_summary()
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())
