"""CLI entrypoint for PT-017 gated dual-flow comparative report."""

from __future__ import annotations

import argparse

from proteus.experiments.dual_flow_phase4_report import (
    DualFlowPhase4Config,
    run_dual_flow_phase4_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PT-017 dual-flow comparative report")
    parser.add_argument("--out-dir", required=True, help="Output directory for artifacts")
    parser.add_argument("--phase2-report", required=True, help="Path to PT-014 report JSON")
    parser.add_argument("--phase3-report", required=True, help="Path to PT-016 report JSON")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--duration-ms", type=int, default=1_000)
    parser.add_argument("--batch-interval-ms", type=int, default=100)
    parser.add_argument("--version-tag", default="v1")
    args = parser.parse_args(argv)

    result = run_dual_flow_phase4_report(
        DualFlowPhase4Config(
            phase2_report_path=args.phase2_report,
            phase3_report_path=args.phase3_report,
            seed=args.seed,
            duration_ms=args.duration_ms,
            batch_interval_ms=args.batch_interval_ms,
        ),
        out_dir=args.out_dir,
        version_tag=args.version_tag,
    )

    print(result.report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
