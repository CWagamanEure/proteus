from __future__ import annotations

import csv
import json

import pytest

from proteus.experiments.baseline_pack import BaselinePackConfig, run_clob_baseline_pack
from proteus.experiments.calibration import CalibrationSearchConfig
from proteus.experiments.run_clob_baseline_pack import main as run_baseline_pack_main


def test_baseline_pack_outputs_ci_and_effect_size(tmp_path) -> None:
    calibration = CalibrationSearchConfig(
        seeds=(7, 11),
        duration_ms=2_000,
        step_ms=100,
        mm_h0_grid=(0.01, 0.015),
        mm_kappa_grid=(0.004, 0.008),
        mm_min_half_spread_grid=(0.0025, 0.0035),
        informed_activity_grid=(0.04, 0.08),
        latency_submission_grid_ms=(1, 5),
    )
    config = BaselinePackConfig(
        base_seed=7,
        repetitions=4,
        duration_ms=2_000,
        step_ms=100,
        informed_activity_grid=(0.04, 0.08),
        latency_submission_grid_ms=(1, 5),
        calibration=calibration,
    )

    result = run_clob_baseline_pack(config, out_dir=tmp_path)
    assert result.report_path
    assert result.summary_csv_path

    payload = json.loads((tmp_path / "clob_baseline_pack_report.json").read_text(encoding="utf-8"))

    assert "selected_regime" in payload
    assert "rows" in payload
    assert len(payload["rows"]) == 4

    first_row = payload["rows"][0]
    assert "mm_pnl_ci95_low" in first_row
    assert "mm_pnl_ci95_high" in first_row
    assert "effect_size_mm_pnl_vs_baseline_d" in first_row


def test_baseline_pack_records_effective_seed_metadata(tmp_path) -> None:
    config = BaselinePackConfig(
        base_seed=7,
        repetitions=3,
        duration_ms=1_000,
        step_ms=100,
        informed_activity_grid=(0.04,),
        latency_submission_grid_ms=(1, 250),
    )

    run_clob_baseline_pack(config, out_dir=tmp_path)
    payload = json.loads((tmp_path / "clob_baseline_pack_report.json").read_text(encoding="utf-8"))

    effective = payload["config"]["effective_repetition_seeds"]
    calibration_seeds = payload["config"]["calibration"]["seeds"]
    assert len(effective) == config.repetitions
    assert effective == calibration_seeds


def test_baseline_pack_latency_grid_shows_metric_divergence_for_multi_step_delay(
    tmp_path,
) -> None:
    config = BaselinePackConfig(
        base_seed=7,
        repetitions=6,
        duration_ms=2_000,
        step_ms=100,
        informed_activity_grid=(0.06,),
        latency_submission_grid_ms=(1, 100, 250),
    )

    run_clob_baseline_pack(config, out_dir=tmp_path)
    payload = json.loads((tmp_path / "clob_baseline_pack_report.json").read_text(encoding="utf-8"))
    rows = payload["rows"]
    mm_pnls = [round(float(row["mm_pnl_mean"]), 12) for row in rows]

    assert len(rows) == 3
    assert len(set(mm_pnls)) >= 2


def test_baseline_pack_row_count_and_numeric_invariants(tmp_path) -> None:
    config = BaselinePackConfig(
        base_seed=7,
        repetitions=4,
        duration_ms=1_200,
        step_ms=100,
        informed_activity_grid=(0.03, 0.06),
        latency_submission_grid_ms=(1, 100, 250),
    )

    run_clob_baseline_pack(config, out_dir=tmp_path)
    payload = json.loads((tmp_path / "clob_baseline_pack_report.json").read_text(encoding="utf-8"))
    rows = payload["rows"]

    assert len(rows) == len(config.informed_activity_grid) * len(config.latency_submission_grid_ms)
    for row in rows:
        assert 0.0 <= float(row["stable_rate"]) <= 1.0
        assert (
            float(row["mm_pnl_ci95_low"])
            <= float(row["mm_pnl_mean"])
            <= float(row["mm_pnl_ci95_high"])
        )
        assert (
            float(row["market_spread_ci95_low"])
            <= float(row["market_spread_mean"])
            <= float(row["market_spread_ci95_high"])
        )


def test_baseline_pack_csv_matches_json_rows(tmp_path) -> None:
    config = BaselinePackConfig(
        base_seed=7,
        repetitions=3,
        duration_ms=1_000,
        step_ms=100,
        informed_activity_grid=(0.04, 0.08),
        latency_submission_grid_ms=(1, 250),
    )
    result = run_clob_baseline_pack(config, out_dir=tmp_path)

    payload = json.loads((tmp_path / "clob_baseline_pack_report.json").read_text(encoding="utf-8"))
    json_rows = payload["rows"]
    csv_path = tmp_path / "clob_baseline_pack_summary.csv"
    csv_rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))

    assert result.report_path
    assert result.summary_csv_path
    assert len(csv_rows) == len(json_rows)
    assert set(csv_rows[0].keys()) == set(json_rows[0].keys())


def test_baseline_pack_deterministic_for_same_config(tmp_path) -> None:
    config = BaselinePackConfig(
        base_seed=7,
        repetitions=4,
        duration_ms=1_200,
        step_ms=100,
        informed_activity_grid=(0.06, 0.12),
        latency_submission_grid_ms=(1, 100, 250),
    )
    out_a = tmp_path / "run_a"
    out_b = tmp_path / "run_b"

    run_clob_baseline_pack(config, out_dir=out_a)
    run_clob_baseline_pack(config, out_dir=out_b)

    report_a = json.loads((out_a / "clob_baseline_pack_report.json").read_text(encoding="utf-8"))
    report_b = json.loads((out_b / "clob_baseline_pack_report.json").read_text(encoding="utf-8"))
    assert report_a["selected_regime"] == report_b["selected_regime"]
    assert report_a["rows"] == report_b["rows"]


def test_baseline_pack_cli_writes_expected_artifacts(tmp_path) -> None:
    out_dir = tmp_path / "cli"
    exit_code = run_baseline_pack_main(
        [
            "--out-dir",
            str(out_dir),
            "--repetitions",
            "3",
            "--duration-ms",
            "1000",
            "--step-ms",
            "100",
        ]
    )
    assert exit_code == 0
    assert (out_dir / "clob_baseline_pack_report.json").exists()
    assert (out_dir / "clob_baseline_pack_summary.csv").exists()
    assert (out_dir / "clob_calibration_report.json").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("repetitions", 0),
        ("duration_ms", 0),
        ("step_ms", 0),
        ("informed_activity_grid", ()),
        ("latency_submission_grid_ms", ()),
    ],
)
def test_baseline_pack_invalid_config_raises(tmp_path, field, value) -> None:
    base = BaselinePackConfig()
    kwargs = {
        "base_seed": base.base_seed,
        "repetitions": base.repetitions,
        "duration_ms": base.duration_ms,
        "step_ms": base.step_ms,
        "informed_activity_grid": base.informed_activity_grid,
        "latency_submission_grid_ms": base.latency_submission_grid_ms,
        "baseline_informed_activity_prob": base.baseline_informed_activity_prob,
        "baseline_submission_latency_ms": base.baseline_submission_latency_ms,
        "calibration": base.calibration,
    }
    kwargs[field] = value
    with pytest.raises(ValueError):
        run_clob_baseline_pack(BaselinePackConfig(**kwargs), out_dir=tmp_path)
