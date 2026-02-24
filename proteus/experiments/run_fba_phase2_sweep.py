"""CLI entrypoint for PT-014 Phase 2 CLOB vs FBA delta sweep."""

from __future__ import annotations

import argparse

from proteus.experiments.fba_phase2_sweep import Phase2SweepConfig, run_fba_phase2_sweep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PT-014 CLOB vs FBA delta sweep")
    parser.add_argument("--out-dir", required=True, help="Output directory for artifacts")
    parser.add_argument("--base-seed", type=int, default=7)
    parser.add_argument("--repetitions", type=int, default=8)
    parser.add_argument("--duration-ms", type=int, default=20_000)
    parser.add_argument("--step-ms", type=int, default=100)
    parser.add_argument(
        "--delta-grid-ms",
        default="50,100,250,500,1000",
        help="Comma-separated FBA batch intervals in ms",
    )
    parser.add_argument("--informed-activity-prob", type=float, default=0.06)
    parser.add_argument("--submission-latency-ms", type=int, default=1)
    parser.add_argument("--version-tag", default="v1")
    args = parser.parse_args(argv)

    delta_grid = tuple(int(part.strip()) for part in args.delta_grid_ms.split(",") if part.strip())

    result = run_fba_phase2_sweep(
        Phase2SweepConfig(
            base_seed=args.base_seed,
            repetitions=args.repetitions,
            duration_ms=args.duration_ms,
            step_ms=args.step_ms,
            batch_intervals_ms=delta_grid,
            informed_activity_prob=args.informed_activity_prob,
            submission_latency_ms=args.submission_latency_ms,
        ),
        out_dir=args.out_dir,
        version_tag=args.version_tag,
    )

    print(result.report_path)
    print(result.summary_csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
