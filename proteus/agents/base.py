"""Agent interface definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from proteus.core.events import Event, OrderIntent


class Agent(ABC):
    """Base interface for all trading agents."""

    agent_id: str

    @abstractmethod
    def on_event(self, event: Event) -> None:
        """Update internal state from a market event."""

    @abstractmethod
    def generate_intents(self, ts_ms: int) -> Iterable[OrderIntent]:
        """Produce zero or more order intents at the current time."""


class NullAgent(Agent):
    """No-op agent for wiring and smoke tests."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    def on_event(self, event: Event) -> None:
        _ = event

    def generate_intents(self, ts_ms: int) -> Iterable[OrderIntent]:
        _ = ts_ms
        return ()
