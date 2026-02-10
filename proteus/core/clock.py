"""Simulation clock primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Clock(ABC):
    """Abstract simulation clock."""

    @property
    @abstractmethod
    def now_ms(self) -> int:
        """Current simulation time in milliseconds."""

    @abstractmethod
    def advance(self, delta_ms: int) -> int:
        """Advance clock and return the new timestamp."""


class EventClock(Clock):
    """Minimal deterministic clock implementation."""

    def __init__(self) -> None:
        self._now_ms = 0

    @property
    def now_ms(self) -> int:
        return self._now_ms

    def advance(self, delta_ms: int) -> int:
        if delta_ms < 0:
            raise ValueError("delta_ms must be non-negative")
        self._now_ms += delta_ms
        return self._now_ms
