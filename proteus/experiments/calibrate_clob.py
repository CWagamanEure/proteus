"""CLI for PT-010 CLOB calibration harness."""

from __future__ import annotations

import argparse

from proteus.experiments.calibration import CalibrationSearchConfig, run_clob_calibration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PT-010 CLOB calibration harness.")
    parser.add_argument("--out-dir", required=True, help="Directory for calibration report")
    parser.add_argument("--report-name", default="clob_calibration_report.json")
    parser.add_argument("--duration-ms", type=int, default=20_000)
    parser.add_argument("--step-ms", type=int, default=100)
    args = parser.parse_args(argv)

    config = CalibrationSearchConfig(duration_ms=args.duration_ms, step_ms=args.step_ms)
    report = run_clob_calibration(config, out_dir=args.out_dir, report_name=args.report_name)

    if report.report_path is not None:
        print(report.report_path)
    print(f"stable_candidates_found={report.stable_candidates_found}")
    print(f"selected_regime={report.selected_regime}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
