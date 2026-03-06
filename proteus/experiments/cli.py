"""Unified experiment CLI with presets for PT-011/PT-014/PT-016 workflows."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from proteus.experiments.baseline_pack import BaselinePackConfig, run_clob_baseline_pack
from proteus.experiments.dual_flow_phase4_report import (
    DualFlowPhase4Config,
    run_dual_flow_phase4_report,
)
from proteus.experiments.fba_phase2_sweep import Phase2SweepConfig, run_fba_phase2_sweep
from proteus.experiments.rfq_phase3_sweep import RFQPhase3SweepConfig, run_rfq_phase3_sweep


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command != "run":
        parser.error("unsupported command")

    out_dir = Path(args.out_dir)

    if args.experiment == "baseline":
        print(f"[proteus] starting baseline run (preset={args.preset})")
        config = _baseline_config_for_preset(args.preset)
        config = replace(
            config,
            base_seed=args.base_seed if args.base_seed is not None else config.base_seed,
            repetitions=args.repetitions if args.repetitions is not None else config.repetitions,
            duration_ms=args.duration_ms if args.duration_ms is not None else config.duration_ms,
            step_ms=args.step_ms if args.step_ms is not None else config.step_ms,
            informed_activity_grid=(
                _parse_float_grid(args.informed_activity_grid)
                if args.informed_activity_grid is not None
                else config.informed_activity_grid
            ),
            latency_submission_grid_ms=(
                _parse_int_grid(args.latency_grid_ms)
                if args.latency_grid_ms is not None
                else config.latency_submission_grid_ms
            ),
        )
        result = run_clob_baseline_pack(config, out_dir=out_dir)
        print("[proteus] baseline run complete")
        print(result.report_path)
        print(result.summary_csv_path)
        return 0

    if args.experiment == "phase2":
        print(f"[proteus] starting phase2 run (preset={args.preset})")
        config = _phase2_config_for_preset(args.preset)
        config = replace(
            config,
            base_seed=args.base_seed if args.base_seed is not None else config.base_seed,
            repetitions=args.repetitions if args.repetitions is not None else config.repetitions,
            duration_ms=args.duration_ms if args.duration_ms is not None else config.duration_ms,
            step_ms=args.step_ms if args.step_ms is not None else config.step_ms,
            batch_intervals_ms=(
                _parse_int_grid(args.delta_grid_ms)
                if args.delta_grid_ms is not None
                else config.batch_intervals_ms
            ),
            informed_activity_prob=(
                args.informed_activity_prob
                if args.informed_activity_prob is not None
                else config.informed_activity_prob
            ),
            submission_latency_ms=(
                args.submission_latency_ms
                if args.submission_latency_ms is not None
                else config.submission_latency_ms
            ),
        )
        result = run_fba_phase2_sweep(
            config,
            out_dir=out_dir,
            version_tag=args.version_tag or args.preset,
        )
        print("[proteus] phase2 run complete")
        print(result.report_path)
        print(result.summary_csv_path)
        return 0

    if args.experiment == "phase3":
        print(f"[proteus] starting phase3 run (preset={args.preset})")
        config = _phase3_config_for_preset(args.preset)
        config = replace(
            config,
            base_seed=args.base_seed if args.base_seed is not None else config.base_seed,
            repetitions=args.repetitions if args.repetitions is not None else config.repetitions,
            duration_ms=args.duration_ms if args.duration_ms is not None else config.duration_ms,
            step_ms=args.step_ms if args.step_ms is not None else config.step_ms,
            request_ttl_grid_ms=(
                _parse_int_grid(args.request_ttl_grid_ms)
                if args.request_ttl_grid_ms is not None
                else config.request_ttl_grid_ms
            ),
            response_latency_grid_ms=(
                _parse_int_grid(args.response_latency_grid_ms)
                if args.response_latency_grid_ms is not None
                else config.response_latency_grid_ms
            ),
            dealer_count_grid=(
                _parse_int_grid(args.dealer_count_grid)
                if args.dealer_count_grid is not None
                else config.dealer_count_grid
            ),
            informed_activity_prob=(
                args.informed_activity_prob
                if args.informed_activity_prob is not None
                else config.informed_activity_prob
            ),
            submission_latency_ms=(
                args.submission_latency_ms
                if args.submission_latency_ms is not None
                else config.submission_latency_ms
            ),
        )
        result = run_rfq_phase3_sweep(
            config,
            out_dir=out_dir,
            version_tag=args.version_tag or args.preset,
            show_progress=args.progress,
        )
        print("[proteus] phase3 run complete")
        print(result.report_path)
        print(result.summary_csv_path)
        return 0

    if args.experiment == "phase4":
        print(f"[proteus] starting phase4 run (preset={args.preset})")
        if args.phase2_report is None or args.phase3_report is None:
            parser.error("--phase2-report and --phase3-report are required for phase4")
        result = run_dual_flow_phase4_report(
            DualFlowPhase4Config(
                phase2_report_path=args.phase2_report,
                phase3_report_path=args.phase3_report,
                seed=args.base_seed if args.base_seed is not None else 7,
                duration_ms=args.duration_ms if args.duration_ms is not None else 1_000,
                batch_interval_ms=(
                    args.batch_interval_ms if args.batch_interval_ms is not None else 100
                ),
            ),
            out_dir=out_dir,
            version_tag=args.version_tag or args.preset,
        )
        print("[proteus] phase4 run complete")
        print(result.report_path)
        return 0

    parser.error(f"unsupported experiment: {args.experiment}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proteus",
        description="Unified runner for Proteus experiment workflows",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="Run a named experiment workflow")
    run_parser.add_argument(
        "experiment",
        choices=("baseline", "phase2", "phase3", "phase4"),
        help="Experiment workflow to execute",
    )
    run_parser.add_argument("--out-dir", required=True, help="Directory for run artifacts")
    run_parser.add_argument(
        "--preset",
        choices=("quick", "ci", "paper"),
        default="quick",
        help="Preset parameter profile (defaults to quick)",
    )
    run_parser.add_argument("--base-seed", type=int)
    run_parser.add_argument("--repetitions", type=int)
    run_parser.add_argument("--duration-ms", type=int)
    run_parser.add_argument("--step-ms", type=int)
    run_parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable progress display for long-running sweeps",
    )

    # Baseline-specific optional overrides
    run_parser.add_argument(
        "--informed-activity-grid",
        help="Comma-separated informed-activity values for baseline workflow",
    )
    run_parser.add_argument(
        "--latency-grid-ms",
        help="Comma-separated submission-latency values for baseline workflow",
    )

    # Phase2-specific optional overrides
    run_parser.add_argument(
        "--delta-grid-ms",
        help="Comma-separated FBA batch-interval values for phase2 workflow",
    )

    # Phase3-specific optional overrides
    run_parser.add_argument(
        "--request-ttl-grid-ms",
        help="Comma-separated RFQ request TTL values for phase3 workflow",
    )
    run_parser.add_argument(
        "--response-latency-grid-ms",
        help="Comma-separated RFQ response latency values for phase3 workflow",
    )
    run_parser.add_argument(
        "--dealer-count-grid",
        help="Comma-separated dealer-count values for phase3 workflow",
    )
    run_parser.add_argument("--phase2-report", help="Path to PT-014 report JSON for phase4 gate")
    run_parser.add_argument("--phase3-report", help="Path to PT-016 report JSON for phase4 gate")
    run_parser.add_argument("--batch-interval-ms", type=int, help="Batch interval for phase4")

    # Shared phase2/phase3 overrides
    run_parser.add_argument(
        "--informed-activity-prob",
        type=float,
        help="Per-step informed activity probability override",
    )
    run_parser.add_argument(
        "--submission-latency-ms",
        type=int,
        help="Submission latency override",
    )
    run_parser.add_argument(
        "--version-tag",
        default=None,
        help="Version tag override for phase2/phase3 outputs",
    )

    return parser


def _baseline_config_for_preset(preset: str) -> BaselinePackConfig:
    if preset == "quick":
        return BaselinePackConfig(
            repetitions=2,
            duration_ms=2_000,
            step_ms=100,
            informed_activity_grid=(0.06, 0.12),
            latency_submission_grid_ms=(1, 25),
        )
    if preset == "ci":
        return BaselinePackConfig(
            repetitions=1,
            duration_ms=1_000,
            step_ms=100,
            informed_activity_grid=(0.06,),
            latency_submission_grid_ms=(1,),
        )
    if preset == "paper":
        return BaselinePackConfig()
    raise ValueError(f"unknown preset: {preset}")


def _phase2_config_for_preset(preset: str) -> Phase2SweepConfig:
    if preset == "quick":
        return Phase2SweepConfig(
            repetitions=2,
            duration_ms=2_000,
            step_ms=100,
            batch_intervals_ms=(50, 250),
        )
    if preset == "ci":
        return Phase2SweepConfig(
            repetitions=1,
            duration_ms=1_000,
            step_ms=100,
            batch_intervals_ms=(100,),
        )
    if preset == "paper":
        return Phase2SweepConfig()
    raise ValueError(f"unknown preset: {preset}")


def _phase3_config_for_preset(preset: str) -> RFQPhase3SweepConfig:
    if preset == "quick":
        return RFQPhase3SweepConfig(
            repetitions=2,
            duration_ms=2_000,
            step_ms=100,
            request_ttl_grid_ms=(50, 150),
            response_latency_grid_ms=(0, 10),
            dealer_count_grid=(1, 3),
        )
    if preset == "ci":
        return RFQPhase3SweepConfig(
            repetitions=1,
            duration_ms=1_000,
            step_ms=100,
            request_ttl_grid_ms=(100,),
            response_latency_grid_ms=(5,),
            dealer_count_grid=(1,),
        )
    if preset == "paper":
        return RFQPhase3SweepConfig()
    raise ValueError(f"unknown preset: {preset}")


def _parse_int_grid(raw: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in raw.split(",") if part.strip())


def _parse_float_grid(raw: str) -> tuple[float, ...]:
    return tuple(float(part.strip()) for part in raw.split(",") if part.strip())


if __name__ == "__main__":
    raise SystemExit(main())
