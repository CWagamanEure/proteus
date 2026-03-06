from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from proteus.experiments import cli
from proteus.experiments.baseline_pack import BaselinePackConfig
from proteus.experiments.dual_flow_phase4_report import DualFlowPhase4Config
from proteus.experiments.fba_phase2_sweep import Phase2SweepConfig
from proteus.experiments.rfq_phase3_sweep import RFQPhase3SweepConfig


def test_cli_run_phase3_quick_preset_dispatch(monkeypatch, tmp_path, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        config: RFQPhase3SweepConfig,
        *,
        out_dir: Path,
        version_tag: str,
        show_progress: bool,
    ):
        captured["config"] = config
        captured["out_dir"] = out_dir
        captured["version_tag"] = version_tag
        captured["show_progress"] = show_progress
        return SimpleNamespace(report_path="/tmp/report.json", summary_csv_path="/tmp/summary.csv")

    monkeypatch.setattr(cli, "run_rfq_phase3_sweep", fake_run)

    code = cli.main(["run", "phase3", "--out-dir", str(tmp_path)])
    assert code == 0

    config = captured["config"]
    assert isinstance(config, RFQPhase3SweepConfig)
    assert config.repetitions == 2
    assert config.request_ttl_grid_ms == (50, 150)
    assert config.response_latency_grid_ms == (0, 10)
    assert config.dealer_count_grid == (1, 3)
    assert captured["version_tag"] == "quick"
    assert captured["show_progress"] is True

    out = capsys.readouterr().out
    assert "/tmp/report.json" in out
    assert "/tmp/summary.csv" in out


def test_cli_run_phase2_ci_preset_with_overrides(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    def fake_run(config: Phase2SweepConfig, *, out_dir: Path, version_tag: str):
        captured["config"] = config
        captured["out_dir"] = out_dir
        captured["version_tag"] = version_tag
        return SimpleNamespace(
            report_path="/tmp/p2-report.json",
            summary_csv_path="/tmp/p2-summary.csv",
        )

    monkeypatch.setattr(cli, "run_fba_phase2_sweep", fake_run)

    code = cli.main(
        [
            "run",
            "phase2",
            "--out-dir",
            str(tmp_path),
            "--preset",
            "ci",
            "--repetitions",
            "4",
            "--delta-grid-ms",
            "50,100,250",
            "--version-tag",
            "mytag",
        ]
    )
    assert code == 0

    config = captured["config"]
    assert isinstance(config, Phase2SweepConfig)
    assert config.repetitions == 4
    assert config.batch_intervals_ms == (50, 100, 250)
    assert captured["version_tag"] == "mytag"


def test_cli_run_phase3_no_progress_flag(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        config: RFQPhase3SweepConfig,
        *,
        out_dir: Path,
        version_tag: str,
        show_progress: bool,
    ):
        _ = config, out_dir, version_tag
        captured["show_progress"] = show_progress
        return SimpleNamespace(report_path="/tmp/report.json", summary_csv_path="/tmp/summary.csv")

    monkeypatch.setattr(cli, "run_rfq_phase3_sweep", fake_run)

    code = cli.main(
        [
            "run",
            "phase3",
            "--out-dir",
            str(tmp_path),
            "--no-progress",
        ]
    )
    assert code == 0
    assert captured["show_progress"] is False


def test_cli_run_baseline_paper_with_grid_overrides(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    def fake_run(config: BaselinePackConfig, *, out_dir: Path):
        captured["config"] = config
        captured["out_dir"] = out_dir
        return SimpleNamespace(
            report_path="/tmp/base-report.json",
            summary_csv_path="/tmp/base-summary.csv",
        )

    monkeypatch.setattr(cli, "run_clob_baseline_pack", fake_run)

    code = cli.main(
        [
            "run",
            "baseline",
            "--out-dir",
            str(tmp_path),
            "--preset",
            "paper",
            "--informed-activity-grid",
            "0.03,0.06",
            "--latency-grid-ms",
            "1,25",
        ]
    )
    assert code == 0

    config = captured["config"]
    assert isinstance(config, BaselinePackConfig)
    assert config.informed_activity_grid == (0.03, 0.06)
    assert config.latency_submission_grid_ms == (1, 25)


def test_cli_run_phase4_dispatch(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    def fake_run(config: DualFlowPhase4Config, *, out_dir: Path, version_tag: str):
        captured["config"] = config
        captured["out_dir"] = out_dir
        captured["version_tag"] = version_tag
        return SimpleNamespace(report_path="/tmp/phase4-report.json")

    monkeypatch.setattr(cli, "run_dual_flow_phase4_report", fake_run)

    code = cli.main(
        [
            "run",
            "phase4",
            "--out-dir",
            str(tmp_path),
            "--phase2-report",
            "/tmp/phase2.json",
            "--phase3-report",
            "/tmp/phase3.json",
            "--duration-ms",
            "500",
        ]
    )
    assert code == 0

    config = captured["config"]
    assert isinstance(config, DualFlowPhase4Config)
    assert config.phase2_report_path == "/tmp/phase2.json"
    assert config.phase3_report_path == "/tmp/phase3.json"
    assert config.duration_ms == 500
    assert captured["version_tag"] == "quick"


def test_cli_run_phase4_requires_gate_reports(tmp_path) -> None:
    with pytest.raises(SystemExit):
        cli.main(["run", "phase4", "--out-dir", str(tmp_path)])


def test_cli_requires_run_subcommand() -> None:
    with pytest.raises(SystemExit):
        cli.main([])
