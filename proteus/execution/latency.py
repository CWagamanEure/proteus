"""Execution latency models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from random import Random


@dataclass(frozen=True)
class LatencyProfile:
    """
    Latency parameters for one mechanism
    """

    submission_ms: int = 1
    ack_ms: int = 1
    fill_ms: int = 1
    jitter_ms: int = 0

    def __post_init__(self) -> None:
        if self.submission_ms < 0:
            raise ValueError("submission_ms must be non-negative")
        if self.ack_ms < 0:
            raise ValueError("ack_ms must be non-negative")
        if self.fill_ms < 0:
            raise ValueError("fill_ms must be non-negative")
        if self.jitter_ms < 0:
            raise ValueError("jitter_ms must be non-negative")


class LatencyModel(ABC):
    """Computes delays for simulation events."""

    @abstractmethod
    def submission_delay_ms(self) -> int:
        """Delay from intent creation to mechanism submit."""

    @abstractmethod
    def ack_delay_ms(self, mechanism_name: str = "clob") -> int:
        """Delay from submit to acknowledgement"""

    @abstractmethod
    def fill_delay_ms(self) -> int:
        """Delay from match to fill confirmation."""


class ConstantLatencyModel(LatencyModel):
    """Fixed delay latency model."""

    def __init__(self, submission_ms: int = 1, ack_ms: int = 1, fill_ms: int = 1) -> None:
        if submission_ms < 0 or ack_ms < 0 or fill_ms < 0:
            raise ValueError("latencies must be non-negative")
        self._submission_ms = submission_ms
        self._ack_ms = ack_ms
        self._fill_ms = fill_ms

    def submission_delay_ms(self, mechanism_name: str = "clob") -> int:
        _ = mechanism_name
        return self._submission_ms

    def ack_delay_ms(self, mechanism_name: str = "clob") -> int:
        _ = mechanism_name
        return self._ack_ms

    def fill_delay_ms(self, mechanism_name: str = "clob") -> int:
        _ = mechanism_name
        return self._fill_ms


class ConfigurableLatencyModel(LatencyModel):
    """
    Mechanism-aware latency model with deterministic jitter by seed.
    """

    def __init__(
        self,
        *,
        default: LatencyProfile | None = None,
        per_mechanism: dict[str, LatencyProfile] | None = None,
        seed: int = 0,
    ) -> None:
        self._default = default or LatencyProfile()
        self._per_mechanism = per_mechanism or {}
        self._rng = Random(seed)

    def submission_delay_ms(self, mechanism_name: str = "clob") -> int:
        profile = self._profile_for(mechanism_name)
        return self._draw(profile.submission_ms, profile.jitter_ms)

    def ack_delay_ms(self, mechanism_name: str = "clob") -> int:
        profile = self._profile_for(mechanism_name)
        return self._draw(profile.ack_ms, profile.jitter_ms)

    def fill_delay_ms(self, mechanism_name: str = "clob") -> int:
        profile = self._profile_for(mechanism_name)
        return self._draw(profile.fill_ms, profile.jitter_ms)

    def _profile_for(self, mechanism_name: str) -> LatencyProfile:
        return self._per_mechanism.get(mechanism_name, self._default)

    def _draw(self, base_ms: int, jitters_ms: int) -> int:
        if jitters_ms == 0:
            return base_ms
        return base_ms + self._rng.randint(0, jitters_ms)


SUPPORTED_MECHANISMS: tuple[str, ...] = ("clob", "fba", "rfq")


def build_default_latency_model() -> ConfigurableLatencyModel:
    """
    Default parity mode: same latency primitive values for all mechanisms
    """
    base = LatencyProfile(submission_ms=1, ack_ms=1, jitter_ms=0)
    per_mechanism = {name: base for name in SUPPORTED_MECHANISMS}
    return ConfigurableLatencyModel(default=base, per_mechanism=per_mechanism, seed=7)
