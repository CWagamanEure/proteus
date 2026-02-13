"""Agent interface definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from proteus.core.events import Event, OrderIntent


@dataclass(frozen=True)
class AgentDecisionDiagnostic:
    """
    Agent decision trace row used for future rationality research metrics.
    """

    decision_id: str
    agent_id: str
    ts_ms: int
    action_type: str
    context: dict[str, Any]
    expected_value: float | None = None
    realized_value: float | None = None
    belief: float | None = None
    outcome: float | None = None


class Agent(ABC):
    """Base interface for all trading agents."""

    agent_id: str

    @abstractmethod
    def on_event(self, event: Event) -> None:
        """Update internal state from a market event."""

    @abstractmethod
    def generate_intents(self, ts_ms: int) -> Iterable[OrderIntent]:
        """Produce zero or more order intents at the current time."""

    def emit_diagnostics(self, ts_ms: int) -> Iterable[AgentDecisionDiagnostic]:
        """
        Optional diagnostic stream for research instrumentation.

        Implementations can emit decision-level data for metrics such as
        calibration or ex-post regret without coupling strategies to metrics.
        """

        _ = ts_ms
        return ()


class NullAgent(Agent):
    """No-op agent for wiring and smoke tests."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    def on_event(self, event: Event) -> None:
        _ = event

    def generate_intents(self, ts_ms: int) -> Iterable[OrderIntent]:
        _ = ts_ms
        return ()
