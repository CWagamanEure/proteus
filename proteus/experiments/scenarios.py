"""Scenario definitions and basic presets."""

from __future__ import annotations

from proteus.core.config import MechanismConfig, ScenarioConfig


def clob_smoke_scenario(seed: int = 1) -> ScenarioConfig:
    """Tiny default scenario used by the smoke runner."""

    return ScenarioConfig(
        scenario_id="smoke-clob",
        seed=seed,
        duration_ms=10,
        mechanism=MechanismConfig(name="clob", params={}),
        params={},
    )
