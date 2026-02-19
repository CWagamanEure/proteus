"""PT-011 CLOB baseline experiment pack."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from math import sqrt
from pathlib import Path
from statistics import mean, stdev

from proteus.core.rng import derive_repetition_seed
from proteus.experiments.calibration import (
    CalibrationSearchConfig,
    CandidateRegime,
    RunMetrics,
    run_clob_calibration,
    simulate_clob_regime,
)


@dataclass(frozen=True)
class BaselinePackConfig:
    base_seed: int = 7
    repetitions: int = 20
    duration_ms: int = 20_000
    step_ms: int = 100
    informed_activity_grid: tuple[float, ...] = (0.03, 0.06, 0.12, 0.2)
    latency_submission_grid_ms: tuple[int, ...] = (1, 25, 100, 250)
    baseline_informed_activity_prob: float = 0.06
    baseline_submission_latency_ms: int = 1
    calibration: CalibrationSearchConfig = field(default_factory=CalibrationSearchConfig)


@dataclass(frozen=True)
class BaselinePackResult:
    report_path: str
    summary_csv_path: str
    calibration_report_path: str | None


def run_clob_baseline_pack(
    config: BaselinePackConfig,
    *,
    out_dir: str | Path,
) -> BaselinePackResult:
    _validate_config(config)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    seeds = tuple(derive_repetition_seed(config.base_seed, i) for i in range(config.repetitions))

    cal_cfg = CalibrationSearchConfig(
        seeds=seeds,
        duration_ms=config.calibration.duration_ms,
        step_ms=config.calibration.step_ms,
        mm_h0_grid=config.calibration.mm_h0_grid,
        mm_kappa_grid=config.calibration.mm_kappa_grid,
        mm_min_half_spread_grid=config.calibration.mm_min_half_spread_grid,
        baseline_informed_activity_prob=config.calibration.baseline_informed_activity_prob,
        baseline_submission_latency_ms=config.calibration.baseline_submission_latency_ms,
        informed_activity_grid=config.calibration.informed_activity_grid,
        latency_submission_grid_ms=config.calibration.latency_submission_grid_ms,
        criteria=config.calibration.criteria,
    )

    calibration = run_clob_calibration(
        cal_cfg,
        out_dir=out,
        report_name="clob_calibration_report.json",
    )
    regime = calibration.selected_regime

    baseline_runs = _run_cell(
        seeds=seeds,
        duration_ms=config.duration_ms,
        step_ms=config.step_ms,
        regime=regime,
        informed_activity_prob=config.baseline_informed_activity_prob,
        submission_latency_ms=config.baseline_submission_latency_ms,
    )

    rows: list[dict[str, float]] = []
    for informed_prob in config.informed_activity_grid:
        for submission_latency_ms in config.latency_submission_grid_ms:
            runs = _run_cell(
                seeds=seeds,
                duration_ms=config.duration_ms,
                step_ms=config.step_ms,
                regime=regime,
                informed_activity_prob=informed_prob,
                submission_latency_ms=submission_latency_ms,
            )
            rows.append(
                _summarize_cell(
                    runs=runs,
                    baseline_runs=baseline_runs,
                    informed_activity_prob=informed_prob,
                    submission_latency_ms=submission_latency_ms,
                )
            )

    config_payload = asdict(config)
    config_payload["effective_repetition_seeds"] = list(seeds)
    config_payload["calibration"]["seeds"] = list(seeds)

    payload = {
        "config": config_payload,
        "selected_regime": asdict(regime),
        "calibration_baseline_summary": calibration.baseline_summary,
        "rows": rows,
    }

    report_path = out / "clob_baseline_pack_report.json"
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    summary_csv_path = out / "clob_baseline_pack_summary.csv"
    _write_summary_csv(summary_csv_path, rows)

    return BaselinePackResult(
        report_path=str(report_path),
        summary_csv_path=str(summary_csv_path),
        calibration_report_path=calibration.report_path,
    )


def _validate_config(config: BaselinePackConfig) -> None:
    if config.repetitions <= 0:
        raise ValueError("repetitions must be > 0")
    if config.duration_ms <= 0:
        raise ValueError("duration_ms must be > 0")
    if config.step_ms <= 0:
        raise ValueError("step_ms must be > 0")
    if not config.informed_activity_grid:
        raise ValueError("informed_activity_grid must be non-empty")
    if not config.latency_submission_grid_ms:
        raise ValueError("latency_submission_grid_ms must be non-empty")


def _run_cell(
    *,
    seeds: tuple[int, ...],
    duration_ms: int,
    step_ms: int,
    regime: CandidateRegime,
    informed_activity_prob: float,
    submission_latency_ms: int,
) -> list[RunMetrics]:
    return [
        simulate_clob_regime(
            seed=seed,
            duration_ms=duration_ms,
            step_ms=step_ms,
            regime=regime,
            informed_activity_prob=informed_activity_prob,
            submission_latency_ms=submission_latency_ms,
        )
        for seed in seeds
    ]


def _summarize_cell(
    *,
    runs: list[RunMetrics],
    baseline_runs: list[RunMetrics],
    informed_activity_prob: float,
    submission_latency_ms: int,
) -> dict[str, float]:
    mm_pnl = [row.mm_pnl for row in runs]
    mm_drawdown = [row.mm_max_drawdown for row in runs]
    mm_as_loss = [row.mm_adverse_selection_loss for row in runs]
    spreads = [row.market_spread_mean for row in runs]
    stable = [1.0 if row.stable else 0.0 for row in runs]

    baseline_mm_pnl = [row.mm_pnl for row in baseline_runs]

    mm_pnl_mean, mm_pnl_ci95_low, mm_pnl_ci95_high = _mean_ci95(mm_pnl)
    spread_mean, spread_ci95_low, spread_ci95_high = _mean_ci95(spreads)

    return {
        "informed_activity_prob": informed_activity_prob,
        "submission_latency_ms": float(submission_latency_ms),
        "n_runs": float(len(runs)),
        "mm_pnl_mean": mm_pnl_mean,
        "mm_pnl_ci95_low": mm_pnl_ci95_low,
        "mm_pnl_ci95_high": mm_pnl_ci95_high,
        "mm_drawdown_mean": mean(mm_drawdown),
        "mm_as_loss_mean": mean(mm_as_loss),
        "market_spread_mean": spread_mean,
        "market_spread_ci95_low": spread_ci95_low,
        "market_spread_ci95_high": spread_ci95_high,
        "stable_rate": mean(stable),
        "effect_size_mm_pnl_vs_baseline_d": _cohens_d(mm_pnl, baseline_mm_pnl),
    }


def _mean_ci95(values: list[float]) -> tuple[float, float, float]:
    mu = mean(values)
    if len(values) < 2:
        return (mu, mu, mu)
    half_width = 1.96 * (stdev(values) / sqrt(len(values)))
    return (mu, mu - half_width, mu + half_width)


def _cohens_d(sample: list[float], baseline: list[float]) -> float:
    if len(sample) < 2 or len(baseline) < 2:
        return 0.0

    sample_sd = stdev(sample)
    baseline_sd = stdev(baseline)
    degrees_of_freedom = len(sample) + len(baseline) - 2
    if degrees_of_freedom <= 0:
        return 0.0

    pooled_variance = (
        ((len(sample) - 1) * (sample_sd**2)) + ((len(baseline) - 1) * (baseline_sd**2))
    ) / degrees_of_freedom
    if pooled_variance <= 0.0:
        return 0.0
    return (mean(sample) - mean(baseline)) / sqrt(pooled_variance)


def _write_summary_csv(path: Path, rows: list[dict[str, float]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
