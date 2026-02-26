"""Experiment execution wiring."""

from __future__ import annotations

from proteus.core.config import ScenarioConfig
from proteus.experiments.parity import assert_scenario_parity
from proteus.mechanisms.clob import CLOBMechanism
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
    raise ValueError(f"Unsupported mechanism: {scenario.mechanism.name}")
