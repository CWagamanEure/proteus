"""Market-level metric interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod


class MarketMetric(ABC):
    """Computes one market-level metric from run artifacts."""

    @abstractmethod
    def compute(self) -> float:
        """Return metric value."""
