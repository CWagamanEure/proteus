"""Information leakage policy interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from proteus.core.events import Event


class LeakagePolicy(ABC):
    """Defines visibility of events to each agent."""

    @abstractmethod
    def is_visible(self, event: Event, agent_id: str) -> bool:
        """Return whether the agent can observe this event."""


@dataclass(frozen=True)
class PublicTapeLeakagePolicy(LeakagePolicy):
    """Default policy where all events are publicly visible."""

    def is_visible(self, event: Event, agent_id: str) -> bool:
        _ = (event, agent_id)
        return True
