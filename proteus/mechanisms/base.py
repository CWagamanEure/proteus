"""Execution mechanism interface definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from proteus.core.events import CancelIntent, Fill, OrderIntent


class Mechanism(ABC):
    """Common interface for market mechanisms."""

    name: str

    @abstractmethod
    def submit(self, intent: OrderIntent) -> None:
        """Submit one order intent into the mechanism."""

    @abstractmethod
    def cancel(self, intent: CancelIntent) -> None:
        """Cancel an existing order according to mechanism rules."""

    @abstractmethod
    def clear(self, ts_ms: int) -> Iterable[Fill]:
        """Execute matching/clearing and emit fills."""


class NullMechanism(Mechanism):
    """No-op mechanism used for bootstrap tests."""

    def __init__(self, name: str) -> None:
        self.name = name

    def submit(self, intent: OrderIntent) -> None:
        _ = intent

    def cancel(self, intent: CancelIntent) -> None:
        _ = intent

    def clear(self, ts_ms: int) -> Iterable[Fill]:
        _ = ts_ms
        return ()
