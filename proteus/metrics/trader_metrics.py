"""Trader metric interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod


class TraderMetric(ABC):
    """Computes one trader metric from run artifacts."""

    @abstractmethod
    def compute(self) -> float:
        """Return metric value."""
