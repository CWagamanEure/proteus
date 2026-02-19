from __future__ import annotations

import json

from proteus.experiments.calibration import (
    CalibrationSearchConfig,
    CandidateRegime,
    run_clob_calibration,
    simulate_clob_regime,
)


def test_calibration_generates_report_with_selected_regime(tmp_path) -> None:
    config = CalibrationSearchConfig(
        seeds=(7, 11),
        duration_ms=3_000,
        step_ms=100,
        mm_h0_grid=(0.01, 0.015),
        mm_kappa_grid=(0.004, 0.008),
        mm_min_half_spread_grid=(0.0025, 0.0035),
        informed_activity_grid=(0.04, 0.08),
        latency_submission_grid_ms=(1, 5),
    )

    report = run_clob_calibration(config, out_dir=tmp_path)
    assert report.report_path is not None
    assert report.selected_regime is not None
    assert len(report.sensitivity_rows) == 4

    payload = json.loads((tmp_path / "clob_calibration_report.json").read_text(encoding="utf-8"))
    assert "selected_regime" in payload
    assert "baseline_rationale" in payload
    assert "sensitivity_rows" in payload
    assert payload["report_path"] == report.report_path


def test_sensitivity_rows_cover_grid(tmp_path) -> None:
    config = CalibrationSearchConfig(
        seeds=(7,),
        duration_ms=2_000,
        step_ms=100,
        informed_activity_grid=(0.03, 0.06, 0.12),
        latency_submission_grid_ms=(1, 3, 7),
    )

    report = run_clob_calibration(config, out_dir=tmp_path)
    assert len(report.sensitivity_rows) == 9


def test_large_submission_latency_changes_simulation_outputs() -> None:
    regime = CandidateRegime(h0=0.012, kappa_inventory=0.004, min_half_spread=0.002)

    low_latency = simulate_clob_regime(
        seed=7,
        duration_ms=2_000,
        step_ms=100,
        regime=regime,
        informed_activity_prob=0.06,
        submission_latency_ms=1,
    )
    high_latency = simulate_clob_regime(
        seed=7,
        duration_ms=2_000,
        step_ms=100,
        regime=regime,
        informed_activity_prob=0.06,
        submission_latency_ms=250,
    )

    assert low_latency.mm_pnl != high_latency.mm_pnl
    assert low_latency.market_spread_mean != high_latency.market_spread_mean
