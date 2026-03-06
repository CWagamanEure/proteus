from __future__ import annotations

import json

import pytest

from proteus.core.config import MechanismConfig, ScenarioConfig
from proteus.experiments.dual_flow_phase4_report import (
    DualFlowPhase4Config,
    run_dual_flow_phase4_report,
)
from proteus.experiments.runner import build_mechanism


def _write_report(path, rows) -> None:
    path.write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")


def test_runner_dual_flow_gate_enforced() -> None:
    scenario = ScenarioConfig(
        scenario_id="df-no-gate",
        seed=7,
        duration_ms=100,
        mechanism=MechanismConfig(name="dual_flow_batch", params={}),
        params={},
    )

    with pytest.raises(ValueError, match="Dual-flow gate failed"):
        build_mechanism(scenario)


def test_runner_dual_flow_gate_allows_build_when_passed() -> None:
    scenario = ScenarioConfig(
        scenario_id="df-gate-ok",
        seed=7,
        duration_ms=100,
        mechanism=MechanismConfig(name="dual_flow_batch", params={"batch_interval_ms": 50}),
        params={"dual_flow_gate": {"phase2_passed": True, "phase3_passed": True}},
    )

    mechanism = build_mechanism(scenario)
    assert mechanism.name == "dual_flow_batch"


def test_phase4_report_fails_without_gate_evidence(tmp_path) -> None:
    phase2 = tmp_path / "phase2.json"
    phase3 = tmp_path / "phase3.json"
    _write_report(phase2, [{"delta_ms": 50}])
    # phase3 intentionally missing

    with pytest.raises(ValueError, match="Dual-flow gate failed"):
        run_dual_flow_phase4_report(
            DualFlowPhase4Config(
                phase2_report_path=phase2,
                phase3_report_path=phase3,
            ),
            out_dir=tmp_path,
            version_tag="blocked",
        )


def test_phase4_report_writes_when_gate_satisfied(tmp_path) -> None:
    phase2 = tmp_path / "phase2.json"
    phase3 = tmp_path / "phase3.json"
    _write_report(phase2, [{"delta_ms": 50}])
    _write_report(phase3, [{"request_ttl_ms": 100}])

    result = run_dual_flow_phase4_report(
        DualFlowPhase4Config(
            phase2_report_path=phase2,
            phase3_report_path=phase3,
            batch_interval_ms=50,
        ),
        out_dir=tmp_path,
        version_tag="ok",
    )

    report_path = tmp_path / "pt017_dual_flow_report_ok" / "dual_flow_phase4_report.json"
    assert result.report_path == str(report_path)
    assert report_path.exists()

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["gate_status"] == {"phase2_passed": True, "phase3_passed": True}

    comparison = payload["comparison"]
    assert set(comparison.keys()) == {"dual_flow_batch", "clob", "fba"}
    assert comparison["dual_flow_batch"]["maker_maker_fill_count"] == 0.0
    assert comparison["dual_flow_batch"]["fill_count"] >= 2.0
