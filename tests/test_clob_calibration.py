from __future__ import annotations

import json

from proteus.experiments.calibration import CalibrationSearchConfig, run_clob_calibration


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
