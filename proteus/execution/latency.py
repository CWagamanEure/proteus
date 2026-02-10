"""Execution latency models."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LatencyModel(ABC):
    """Computes delays for simulation events."""

    @abstractmethod
    def submission_delay_ms(self) -> int:
        """Delay from intent creation to mechanism submit."""

    @abstractmethod
    def fill_delay_ms(self) -> int:
        """Delay from match to fill confirmation."""


class ConstantLatencyModel(LatencyModel):
    """Fixed delay latency model for bootstrap tests."""

    def __init__(self, submission_ms: int = 1, fill_ms: int = 1) -> None:
        self._submission_ms = submission_ms
        self._fill_ms = fill_ms

    def submission_delay_ms(self) -> int:
        return self._submission_ms

    def fill_delay_ms(self) -> int:
        return self._fill_ms
