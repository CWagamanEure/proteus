"""Per-agent signal model interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SignalModel(ABC):
    """Maps latent truth to an agent-specific observation."""

    @abstractmethod
    def observe(self, agent_id: str, ts_ms: int, p_t: float) -> float:
        """Return agent observation in [0, 1]."""


class IdentitySignalModel(SignalModel):
    """Placeholder signal model that exposes p_t directly."""

    def observe(self, agent_id: str, ts_ms: int, p_t: float) -> float:
        _ = (agent_id, ts_ms)
        return min(1.0, max(0.0, p_t))
