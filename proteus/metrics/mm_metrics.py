"""Market-maker metric interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod


class MMMetric(ABC):
    """Computes one market-maker metric from run artifacts."""

    @abstractmethod
    def compute(self) -> float:
        """Return metric value."""
