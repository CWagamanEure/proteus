"""CLI for PT-011 CLOB baseline experiment pack."""

from __future__ import annotations

import argparse

from proteus.experiments.baseline_pack import BaselinePackConfig, run_clob_baseline_pack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PT-011 CLOB baseline experiment pack.")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--base-seed", type=int, default=7)
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--duration-ms", type=int, default=20_000)
    parser.add_argument("--step-ms", type=int, default=100)
    args = parser.parse_args(argv)

    config = BaselinePackConfig(
        base_seed=args.base_seed,
        repetitions=args.repetitions,
        duration_ms=args.duration_ms,
        step_ms=args.step_ms,
    )
    result = run_clob_baseline_pack(config, out_dir=args.out_dir)

    print(result.report_path)
    print(result.summary_csv_path)
    if result.calibration_report_path is not None:
        print(result.calibration_report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
