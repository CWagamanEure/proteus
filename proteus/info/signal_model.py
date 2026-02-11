"""Per-agent signal model interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from bisect import bisect_right
from dataclasses import dataclass
from random import Random


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


@dataclass(frozen=True)
class AgentSignalConfig:
    """
    Agent-specific delay/noise profile.
    """

    delay_ms: int = 0
    noise_stddev: float = 0.0

    def __post_init__(self) -> None:
        if self.delay_ms < 0:
            raise ValueError("delay_ms must be non-negative")
        if self.noise_stddev < 0.0:
            raise ValueError("noise_stddev must be non-negative")


class HeterogeneousSignalModel(SignalModel):
    """
    Delayed and noisy observation model with per-agent heterogeneity

    Each observation uses p_{t-delay_i} plus Gaussian noise, clipped to [0, 1]
    """

    def __init__(
        self,
        *,
        default: AgentSignalConfig | None = None,
        per_agent: dict[str, AgentSignalConfig] | None = None,
    ) -> None:
        self._default = default or AgentSignalConfig()
        self._per_agent = per_agent or {}
        self._history: list[tuple[int, float]] = []
        self._rng_by_agent: dict[str, Random] = {}
        self._seed = 0

    def reset(self, seed: int) -> None:
        self._history.clear()
        self._rng_by_agent.clear()
        self._seed = seed

    def observe(self, agent_id: str, ts_ms: int, p_t: float) -> float:
        clipped_p = _clip_probability(p_t)
        if ts_ms < 0:
            raise ValueError("ts_ms must be non-negative")
        self._record_truth(ts_ms, clipped_p)

        cfg = self._per_agent.get(agent_id, self._default)
        source_p = self._lookup_delayed_p(ts_ms=ts_ms, delay_ms=cfg.delay_ms)
        if cfg.noise_stddev == 0.0:
            return source_p

        rng = self._rng_by_agent.setdefault(agent_id, Random(_seed_for_agent(self._seed, agent_id)))
        noisy = source_p + rng.gauss(0.0, cfg.noise_stddev)
        return _clip_probability(noisy)

    def _record_truth(self, ts_ms: int, p_t: float) -> None:
        if self._history and ts_ms < self._history[-1][0]:
            raise ValueError("observe calls must be non-decreasing in ts_ms")
        if self._history and ts_ms == self._history[-1][0]:
            self._history[-1] = (ts_ms, p_t)
            return
        self._history.append((ts_ms, p_t))

    def _lookup_delayed_p(self, *, ts_ms: int, delay_ms: int) -> float:
        if not self._history:
            raise ValueError("signal history is empty")
        target_ts = ts_ms - delay_ms
        if target_ts <= self._history[0][0]:
            return self._history[0][1]

        ts_values = [ts for ts, _ in self._history]
        idx = bisect_right(ts_values, target_ts) - 1
        return self._history[idx][1]


def _clip_probability(value: float) -> float:
    return min(1.0, max(0.0, value))


def _seed_for_agent(seed: int, agent_id: str) -> int:
    acc = seed
    for char in agent_id:
        acc = (acc * 1315423911 + ord(char)) & 0xFFFFFFFFFFFFFFFF
    return acc
