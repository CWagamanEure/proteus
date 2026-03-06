from __future__ import annotations

import json

import pytest

from proteus.experiments.calibration import CalibrationSearchConfig
from proteus.experiments.rfq_phase3_sweep import (
    RFQPhase3SweepConfig,
    _compute_frontier,
    run_rfq_phase3_sweep,
)
from proteus.experiments.run_rfq_phase3_sweep import main as run_cli


def _minimal_calibration() -> CalibrationSearchConfig:
    return CalibrationSearchConfig(
        seeds=(7, 11),
        duration_ms=500,
        step_ms=100,
        mm_h0_grid=(0.012,),
        mm_kappa_grid=(0.008,),
        mm_min_half_spread_grid=(0.003,),
        informed_activity_grid=(0.06,),
        latency_submission_grid_ms=(1,),
    )


def test_rfq_phase3_sweep_writes_artifacts_rows_and_frontiers(tmp_path) -> None:
    cfg = RFQPhase3SweepConfig(
        base_seed=7,
        repetitions=2,
        duration_ms=500,
        step_ms=100,
        request_ttl_grid_ms=(50, 100),
        response_latency_grid_ms=(0, 10),
        dealer_count_grid=(1, 2),
        calibration=_minimal_calibration(),
    )

    result = run_rfq_phase3_sweep(cfg, out_dir=tmp_path, version_tag="test")

    run_dir = tmp_path / "pt016_rfq_phase3_sweep_test"
    report_path = run_dir / "rfq_phase3_sweep_report.json"
    csv_path = run_dir / "rfq_phase3_sweep_summary.csv"

    assert result.report_path == str(report_path)
    assert result.summary_csv_path == str(csv_path)
    assert report_path.exists()
    assert csv_path.exists()

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    rows = payload["rows"]
    assert len(rows) == 8

    cfg_payload = payload["config"]
    assert len(cfg_payload["effective_repetition_seeds"]) == 2
    assert cfg_payload["calibration"]["seeds"] == cfg_payload["effective_repetition_seeds"]

    required_keys = {
        "mm_as_loss_rfq_mean",
        "mm_as_loss_delta_vs_clob_mean",
        "market_spread_mean_rfq_mean",
        "trader_time_to_execution_ms_rfq_mean",
        "market_price_rmse_rfq_mean",
        "significance_notes",
    }
    for row in rows:
        assert required_keys.issubset(row.keys())

    frontiers = payload["frontiers"]
    assert "protection_vs_price_discovery" in frontiers
    assert "protection_vs_execution_speed" in frontiers
    for item in frontiers["protection_vs_price_discovery"]:
        assert "request_ttl_ms" in item
        assert "response_latency_ms" in item
        assert "dealer_count" in item
        assert "mm_as_loss_delta_vs_clob_mean" in item
        assert "market_price_rmse_delta_vs_clob_mean" in item


def test_rfq_phase3_sweep_reproducible_rows_and_frontiers(tmp_path) -> None:
    cfg = RFQPhase3SweepConfig(
        base_seed=123,
        repetitions=2,
        duration_ms=500,
        step_ms=100,
        request_ttl_grid_ms=(100,),
        response_latency_grid_ms=(5, 15),
        dealer_count_grid=(1, 3),
        calibration=_minimal_calibration(),
    )

    run_rfq_phase3_sweep(cfg, out_dir=tmp_path, version_tag="a")
    run_rfq_phase3_sweep(cfg, out_dir=tmp_path, version_tag="b")

    payload_a = json.loads(
        (tmp_path / "pt016_rfq_phase3_sweep_a" / "rfq_phase3_sweep_report.json").read_text(
            encoding="utf-8"
        )
    )
    payload_b = json.loads(
        (tmp_path / "pt016_rfq_phase3_sweep_b" / "rfq_phase3_sweep_report.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload_a["rows"] == payload_b["rows"]
    assert payload_a["frontiers"] == payload_b["frontiers"]
    assert payload_a["selected_regime"] == payload_b["selected_regime"]


def test_compute_frontier_drops_dominated_points() -> None:
    rows: list[dict[str, float | str]] = [
        {
            "request_ttl_ms": 50.0,
            "response_latency_ms": 0.0,
            "dealer_count": 1.0,
            "mm_as_loss_delta_vs_clob_mean": 0.1,
            "market_price_rmse_delta_vs_clob_mean": 0.1,
        },
        {
            "request_ttl_ms": 100.0,
            "response_latency_ms": 5.0,
            "dealer_count": 2.0,
            "mm_as_loss_delta_vs_clob_mean": 0.05,
            "market_price_rmse_delta_vs_clob_mean": 0.2,
        },
        {
            "request_ttl_ms": 250.0,
            "response_latency_ms": 5.0,
            "dealer_count": 3.0,
            "mm_as_loss_delta_vs_clob_mean": 0.2,
            "market_price_rmse_delta_vs_clob_mean": 0.2,
        },
    ]

    frontier = _compute_frontier(
        rows,
        x_key="mm_as_loss_delta_vs_clob_mean",
        y_key="market_price_rmse_delta_vs_clob_mean",
    )

    assert len(frontier) == 2
    assert frontier[0]["mm_as_loss_delta_vs_clob_mean"] == 0.05
    assert frontier[1]["mm_as_loss_delta_vs_clob_mean"] == 0.1


@pytest.mark.parametrize(
    ("overrides", "error_match"),
    [
        ({"repetitions": 0}, "repetitions must be > 0"),
        ({"request_ttl_grid_ms": ()}, "request_ttl_grid_ms must be non-empty"),
        ({"response_latency_grid_ms": (-1,)}, "response_latency_grid_ms values must be >= 0"),
        ({"dealer_count_grid": (0, 1)}, "dealer_count_grid values must be > 0"),
        (
            {"rfq_request_size_range": (2.0, 1.0)},
            "rfq_request_size_range must satisfy 0 < min_size <= max_size",
        ),
    ],
)
def test_rfq_phase3_sweep_config_validation(tmp_path, overrides, error_match: str) -> None:
    base = RFQPhase3SweepConfig(
        repetitions=1,
        duration_ms=300,
        step_ms=100,
        request_ttl_grid_ms=(100,),
        response_latency_grid_ms=(5,),
        dealer_count_grid=(1,),
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

    config = RFQPhase3SweepConfig(**(base.__dict__ | overrides))
    with pytest.raises(ValueError, match=error_match):
        run_rfq_phase3_sweep(config, out_dir=tmp_path, version_tag="invalid")


def test_rfq_phase3_cli_smoke(tmp_path) -> None:
    out_dir = tmp_path / "artifacts"
    code = run_cli(
        [
            "--out-dir",
            str(out_dir),
            "--repetitions",
            "1",
            "--duration-ms",
            "300",
            "--step-ms",
            "100",
            "--request-ttl-grid-ms",
            "100",
            "--response-latency-grid-ms",
            "5",
            "--dealer-count-grid",
            "1",
            "--version-tag",
            "cli",
        ]
    )

    assert code == 0
    assert (out_dir / "pt016_rfq_phase3_sweep_cli" / "rfq_phase3_sweep_report.json").exists()
