"""Experiment and scenario configuration types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MechanismConfig:
    """Mechanism selection and mechanism-specific settings."""

    name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScenarioConfig:
    """Single scenario configuration for one simulation run."""

    scenario_id: str
    seed: int
    duration_ms: int
    mechanism: MechanismConfig
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentConfig:
    """Batch execution definition with one or more scenarios."""

    experiment_id: str
    scenarios: tuple[ScenarioConfig, ...]
    repetitions: int = 1
