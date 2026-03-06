"""CLI entrypoint for PT-016 RFQ scenario sweeps + analysis."""

from __future__ import annotations

import argparse

from proteus.experiments.rfq_phase3_sweep import RFQPhase3SweepConfig, run_rfq_phase3_sweep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PT-016 RFQ phase-3 sweep")
    parser.add_argument("--out-dir", required=True, help="Output directory for artifacts")
    parser.add_argument("--base-seed", type=int, default=7)
    parser.add_argument("--repetitions", type=int, default=8)
    parser.add_argument("--duration-ms", type=int, default=20_000)
    parser.add_argument("--step-ms", type=int, default=100)
    parser.add_argument(
        "--request-ttl-grid-ms",
        default="50,100,250,500",
        help="Comma-separated RFQ request TTL values in ms",
    )
    parser.add_argument(
        "--response-latency-grid-ms",
        default="0,5,10,25",
        help="Comma-separated RFQ dealer response latency values in ms",
    )
    parser.add_argument(
        "--dealer-count-grid",
        default="1,2,3",
        help="Comma-separated dealer-count values",
    )
    parser.add_argument("--informed-activity-prob", type=float, default=0.06)
    parser.add_argument("--submission-latency-ms", type=int, default=1)
    parser.add_argument("--version-tag", default="v1")
    args = parser.parse_args(argv)

    ttl_grid = tuple(
        int(part.strip()) for part in args.request_ttl_grid_ms.split(",") if part.strip()
    )
    latency_grid = tuple(
        int(part.strip()) for part in args.response_latency_grid_ms.split(",") if part.strip()
    )
    dealer_grid = tuple(
        int(part.strip()) for part in args.dealer_count_grid.split(",") if part.strip()
    )

    result = run_rfq_phase3_sweep(
        RFQPhase3SweepConfig(
            base_seed=args.base_seed,
            repetitions=args.repetitions,
            duration_ms=args.duration_ms,
            step_ms=args.step_ms,
            request_ttl_grid_ms=ttl_grid,
            response_latency_grid_ms=latency_grid,
            dealer_count_grid=dealer_grid,
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
