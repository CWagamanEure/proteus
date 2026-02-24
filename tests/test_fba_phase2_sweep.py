from __future__ import annotations

import json

from proteus.experiments.calibration import CalibrationSearchConfig
from proteus.experiments.fba_phase2_sweep import Phase2SweepConfig, run_fba_phase2_sweep


def test_phase2_sweep_writes_artifacts_and_expected_rows(tmp_path) -> None:
    cfg = Phase2SweepConfig(
        base_seed=7,
        repetitions=2,
        duration_ms=500,
        step_ms=100,
        batch_intervals_ms=(50, 100),
        informed_activity_prob=0.06,
        submission_latency_ms=1,
        calibration=CalibrationSearchConfig(
            seeds=(7, 11),
            duration_ms=500,
            step_ms=100,
            mm_h0_grid=(0.012,),
            mm_kappa_grid=(0.008,),
            mm_min_half_spread_grid=(0.003,),
            informed_activity_grid=(0.06,),
            latency_submission_grid_ms=(1,),
        ),
    )

    result = run_fba_phase2_sweep(cfg, out_dir=tmp_path, version_tag="test")

    run_dir = tmp_path / "pt014_phase2_delta_sweep_test"
    report_path = run_dir / "phase2_delta_sweep_report.json"
    csv_path = run_dir / "phase2_delta_sweep_summary.csv"

    assert result.report_path == str(report_path)
    assert result.summary_csv_path == str(csv_path)
    assert report_path.exists()
    assert csv_path.exists()

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    rows = payload["rows"]
    assert len(rows) == 2
    assert [int(row["delta_ms"]) for row in rows] == [50, 100]

    required_keys = {
        "mm_as_loss_fba_mean",
        "mm_as_loss_delta_vs_clob_mean",
        "market_spread_mean_fba_mean",
        "trader_time_to_execution_ms_fba_mean",
        "market_price_rmse_fba_mean",
        "significance_notes",
    }
    for row in rows:
        assert required_keys.issubset(row.keys())


def test_phase2_sweep_significance_notes_present(tmp_path) -> None:
    cfg = Phase2SweepConfig(
        repetitions=1,
        duration_ms=300,
        step_ms=100,
        batch_intervals_ms=(50,),
        calibration=CalibrationSearchConfig(
            seeds=(7,),
            duration_ms=300,
            step_ms=100,
            mm_h0_grid=(0.012,),
            mm_kappa_grid=(0.008,),
            mm_min_half_spread_grid=(0.003,),
            informed_activity_grid=(0.06,),
            latency_submission_grid_ms=(1,),
        ),
    )

    result = run_fba_phase2_sweep(cfg, out_dir=tmp_path, version_tag="notes")
    payload = json.loads(
        (tmp_path / "pt014_phase2_delta_sweep_notes" / "phase2_delta_sweep_report.json").read_text(
            encoding="utf-8"
        )
    )
    row = payload["rows"][0]
    notes = row["significance_notes"]

    assert isinstance(notes, str)
    assert "mm_as_loss" in notes
    assert "market_spread_mean" in notes
    assert "trader_time_to_execution_ms" in notes
    assert "market_price_rmse" in notes
    assert result.calibration_report_path is not None
