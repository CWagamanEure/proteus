"""Latent probability process interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import exp, log, sqrt
from random import Random


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


@dataclass(frozen=True)
class JumpConfig:
    """
    Configuration for compound jump shocks
    """

    intensity_per_second: float = 0.0  # number jump arrivals per second (Poisson)
    mean: float = 0.0  # average size of one jump
    stddev: float = 0.0  # jump size dispersion

    @property
    def enabled(self) -> bool:
        return (
            self.intensity_per_second > 0.0
            and self.stddev > 0.0
            and (self.stddev > 0.0 or self.mean != 0.0)
        )


class BoundedLogOddsLatentProcess(LatentProcess):
    """
    Bounded latent probability process using a log-odds state

    x_{t+dt} = phi * x_t + eta_t + J_t
    p_t = sigmoid(x_t)
    """

    def __init__(
        self,
        *,
        p0: float = 0.5,  # initial probability
        phi: float = 1.0,  # mean-reversion multiplier
        sigma_eta: float = 0.0,  # volatility of diffusion noise
        jump: JumpConfig | None = None,
    ) -> None:
        if not 0.0 <= p0 < 1.0:
            raise ValueError("p0 must be in [0,1]")
        if not 0.0 <= phi <= 1.0:
            raise ValueError("phi must be in [0,1]")
        if sigma_eta < 0.0:
            raise ValueError("sigma_eta must be non-negative")
        self._p0 = p0
        self._phi = phi
        self._sigma_eta = sigma_eta
        self._jump = jump or JumpConfig()
        if self._jump.intensity_per_second < 0.0:
            raise ValueError("jump intensity_per_second must be non-negative")
        if self._jump.stddev < 0.0:
            raise ValueError("jump stddev must be non-negative")

        self._x = self._logit(p0)
        self._rng = Random(0)

    def reset(self, seed: int) -> None:
        self._x = self._logit(self._p0)
        self._rng = Random(seed)

    def step(self, delta_ms: int) -> float:
        if delta_ms < 0:
            raise ValueError("delta_ms must  be non-negative")
        if delta_ms == 0:
            return self._sigmoid(self._x)

        dt_sec = delta_ms / 1000.0
        eta = self._draw_diffusion_shock(dt_sec)
        jumps = self._draw_jump_shock(dt_sec)
        self._x = (self._phi * self._x) + eta + jumps
        return self._sigmoid(self._x)

    def _draw_diffusion_shock(self, dt_sec: float) -> float:
        if self._sigma_eta == 0.0:
            return 0.0

        return self._rng.gauss(0.0, self._sigma_eta * sqrt(dt_sec))

    def _draw_jump_shock(self, dt_sec: float) -> float:
        if not self._jump.enabled:
            return 0.0

        lam_dt = self._jump.intensity_per_second * dt_sec
        jump_count = self._poisson(lam_dt)
        shock = 0.0
        for _ in range(jump_count):
            shock += self._rng.gauss(self._jump.mean, self._jump.stddev)

        return shock

    def _poisson(self, lam: float) -> int:
        """
        Knuth's Poisson algorithm
        """
        if lam <= 0.0:
            return 0
        threshold = exp(-lam)
        k = 0
        p = 1.0
        while p > threshold:
            k += 1
            p *= self._rng.random()
        return k - 1

    @staticmethod
    def _logit(p: float) -> float:
        eps = 1e-12
        p_bounded = min(1.0 - eps, max(eps, p))
        return log(p_bounded / (1.0 - p_bounded))

    @staticmethod
    def _sigmoid(x: float) -> float:
        if x >= 0.0:
            z = exp(-x)
            return 1.0 / (1.0 + z)
        z = exp(x)
        return z / (1.0 + z)
