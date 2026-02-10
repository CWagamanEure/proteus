"""Latent probability process interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LatentProcess(ABC):
    """State process that produces latent fundamental probability p_t."""

    @abstractmethod
    def reset(self, seed: int) -> None:
        """Reset process state for a new run."""

    @abstractmethod
    def step(self, delta_ms: int) -> float:
        """Advance process and return current p_t in [0, 1]."""


class StaticLatentProcess(LatentProcess):
    """Simple placeholder process for bootstrap tests."""

    def __init__(self, p0: float = 0.5) -> None:
        if not 0.0 <= p0 <= 1.0:
            raise ValueError("p0 must be in [0, 1]")
        self._p = p0

    def reset(self, seed: int) -> None:
        _ = seed

    def step(self, delta_ms: int) -> float:
        _ = delta_ms
        return self._p
