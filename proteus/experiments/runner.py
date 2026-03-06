"""Experiment execution wiring."""

from __future__ import annotations

from proteus.core.config import ScenarioConfig
from proteus.experiments.parity import assert_scenario_parity
from proteus.mechanisms.clob import CLOBMechanism
from proteus.mechanisms.dual_flow_batch import DualFlowBatchMechanism
from proteus.mechanisms.fba import FBAMechanism
from proteus.mechanisms.rfq import RFQMechanism


def build_mechanism(
    scenario: ScenarioConfig,
    *,
    parity_reference: ScenarioConfig | None = None,
):
    """Create mechanism from scenario config, with optional parity preflight."""

    if parity_reference is not None:
        assert_scenario_parity(reference=parity_reference, candidate=scenario)

    if scenario.mechanism.name == "clob":
        return CLOBMechanism()
    if scenario.mechanism.name == "fba":
        return FBAMechanism(**dict(scenario.mechanism.params))
    if scenario.mechanism.name == "rfq":
        return RFQMechanism(**dict(scenario.mechanism.params))
    if scenario.mechanism.name == "dual_flow_batch":
        _assert_dual_flow_gate(scenario)
        return DualFlowBatchMechanism(**dict(scenario.mechanism.params))
    raise ValueError(f"Unsupported mechanism: {scenario.mechanism.name}")


def _assert_dual_flow_gate(scenario: ScenarioConfig) -> None:
    gate = scenario.params.get("dual_flow_gate")
    if not isinstance(gate, dict):
        raise ValueError(
            "Dual-flow gate failed: scenario.params.dual_flow_gate is required with "
            "phase2_passed=True and phase3_passed=True."
        )

    phase2_passed = bool(gate.get("phase2_passed"))
    phase3_passed = bool(gate.get("phase3_passed"))
    if not (phase2_passed and phase3_passed):
        raise ValueError(
            "Dual-flow gate failed: requires phase2_passed=True and phase3_passed=True "
            "(PT-014/PT-016 gate)."
        )
