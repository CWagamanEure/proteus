"""Experiment execution wiring."""

from __future__ import annotations

from proteus.core.config import ScenarioConfig
from proteus.mechanisms.clob import CLOBMechanism
from proteus.mechanisms.fba import FBAMechanism
from proteus.mechanisms.rfq import RFQMechanism


def build_mechanism(scenario: ScenarioConfig):
    """Create mechanism from scenario config."""

    if scenario.mechanism.name == "clob":
        return CLOBMechanism()
    if scenario.mechanism.name == "fba":
        return FBAMechanism()
    if scenario.mechanism.name == "rfq":
        return RFQMechanism()
    raise ValueError(f"Unsupported mechanism: {scenario.mechanism.name}")
