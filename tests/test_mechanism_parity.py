from __future__ import annotations

import pytest

from proteus.core.config import MechanismConfig, ScenarioConfig
from proteus.experiments.parity import assert_scenario_parity, diff_scenario_parity_keys
from proteus.experiments.runner import build_mechanism


def _scenario(
    *,
    scenario_id: str,
    mechanism_name: str,
    mechanism_params: dict | None = None,
    seed: int = 7,
    duration_ms: int = 1_000,
    params: dict | None = None,
) -> ScenarioConfig:
    return ScenarioConfig(
        scenario_id=scenario_id,
        seed=seed,
        duration_ms=duration_ms,
        mechanism=MechanismConfig(name=mechanism_name, params=mechanism_params or {}),
        params=params or {},
    )


def test_parity_ignores_scenario_id_and_mechanism_fields() -> None:
    ref = _scenario(
        scenario_id="baseline-clob",
        mechanism_name="clob",
        mechanism_params={},
        params={"latency": {"submission_ms": 10}, "agents": {"n_noise": 4}},
    )
    cand = _scenario(
        scenario_id="treatment-fba-100",
        mechanism_name="fba",
        mechanism_params={"batch_interval_ms": 100, "allocation_policy": "pro_rata"},
        params={"latency": {"submission_ms": 10}, "agents": {"n_noise": 4}},
    )

    assert diff_scenario_parity_keys(ref, cand) == []
    assert_scenario_parity(reference=ref, candidate=cand)


def test_parity_reports_exact_differing_keys_for_nested_params() -> None:
    ref = _scenario(
        scenario_id="clob",
        mechanism_name="clob",
        params={"latency": {"submission_ms": 10, "ack_ms": 5}},
    )
    cand = _scenario(
        scenario_id="fba",
        mechanism_name="fba",
        mechanism_params={"batch_interval_ms": 100},
        params={"latency": {"submission_ms": 10, "ack_ms": 7}},
    )

    diffs = diff_scenario_parity_keys(ref, cand)
    assert diffs == ["params.latency.ack_ms"]

    with pytest.raises(ValueError) as exc_info:
        assert_scenario_parity(reference=ref, candidate=cand)

    assert "params.latency.ack_ms" in str(exc_info.value)


def test_parity_reports_multiple_top_level_differences() -> None:
    ref = _scenario(scenario_id="clob", mechanism_name="clob", seed=7, duration_ms=1000)
    cand = _scenario(
        scenario_id="fba",
        mechanism_name="fba",
        mechanism_params={"batch_interval_ms": 100},
        seed=8,
        duration_ms=900,
    )

    diffs = diff_scenario_parity_keys(ref, cand)
    assert diffs == ["duration_ms", "seed"]


def test_runner_preflight_fails_before_build_on_parity_violation() -> None:
    ref = _scenario(
        scenario_id="clob",
        mechanism_name="clob",
        params={"shared": {"step_ms": 100}},
    )
    cand = _scenario(
        scenario_id="fba",
        mechanism_name="fba",
        mechanism_params={"batch_interval_ms": 100},
        params={"shared": {"step_ms": 50}},
    )

    with pytest.raises(ValueError) as exc_info:
        build_mechanism(cand, parity_reference=ref)

    assert "Mechanism parity preflight failed" in str(exc_info.value)
    assert "params.shared.step_ms" in str(exc_info.value)
