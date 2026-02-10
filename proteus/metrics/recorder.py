"""Metric recorder and event sink."""

from __future__ import annotations

from dataclasses import dataclass, field

from proteus.core.events import Event


@dataclass
class Recorder:
    """Mechanism-agnostic event recorder."""

    events: list[Event] = field(default_factory=list)

    def record(self, event: Event) -> None:
        self.events.append(event)
