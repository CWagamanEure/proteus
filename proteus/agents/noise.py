"""Noise trader agent v1 implementation."""

from __future__ import annotations

from math import exp
from random import Random

from proteus.agents.base import Agent
from proteus.core.events import Event, OrderIntent, Side


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _default_seed(agent_id: str) -> int:
    acc = 17
    for ch in agent_id:
        acc = (acc * 131 + ord(ch)) & 0xFFFFFFFFFFFFFFFF
    return acc


class NoiseTraderAgent(Agent):
    """
    Poisson-arrival random trader with bounded price/size draws.
    """

    def __init__(
        self,
        agent_id: str,
        *,
        arrival_rate_per_second: float = 2.0,
        min_size: float = 0.25,
        max_size: float = 2.0,
        price_low: float = 0.01,
        price_high: float = 0.99,
        price_jitter: float = 0.05,
        seed: int | None = None,
    ) -> None:
        if arrival_rate_per_second < 0.0:
            raise ValueError("arrival_rate_per_second must be non-negative")
        if min_size <= 0.0 or max_size < min_size:
            raise ValueError("size bounds must satisfy 0 < min_size <= max_size")
        if not 0.0 <= price_low <= price_high <= 1.0:
            raise ValueError("price bounds must satisfy 0 <= low <= high <= 1")

        self.agent_id = agent_id
        self._arrival_rate = arrival_rate_per_second
        self._min_size = min_size
        self._max_size = max_size
        self._price_low = price_low
        self._price_high = price_high
        self._price_jitter = max(0.0, price_jitter)

        self._rng = Random(seed if seed is not None else _default_seed(agent_id))
        self._last_ts_ms: int | None = None
        self._intent_seq = 0

        self._best_bid: float | None = None
        self._best_ask: float | None = None

    def on_event(self, event: Event) -> None:
        bid = event.payload.get("best_bid")
        ask = event.payload.get("best_ask")
        if bid is not None:
            self._best_bid = _clip01(float(bid))
        if ask is not None:
            self._best_ask = _clip01(float(ask))

    def generate_intents(self, ts_ms: int):
        if ts_ms < 0:
            raise ValueError("ts_ms must be non-negative")

        dt_ms = self._dt_ms(ts_ms)
        lam = self._arrival_rate * (dt_ms / 1000.0)
        n_arrivals = self._poisson(lam)

        intents: list[OrderIntent] = []
        for _ in range(n_arrivals):
            side = Side.BUY if self._rng.random() < 0.5 else Side.SELL
            size = self._rng.uniform(self._min_size, self._max_size)
            price = self._draw_price()

            self._intent_seq += 1
            intents.append(
                OrderIntent(
                    intent_id=f"{self.agent_id}-{ts_ms}-{self._intent_seq}",
                    agent_id=self.agent_id,
                    ts_ms=ts_ms,
                    side=side,
                    price=price,
                    size=size,
                )
            )
        return intents

    def _dt_ms(self, ts_ms: int) -> int:
        if self._last_ts_ms is None:
            self._last_ts_ms = ts_ms
            return 100  # default first step to avoid zero-intensity bootstrap
        dt = max(0, ts_ms - self._last_ts_ms)
        self._last_ts_ms = ts_ms
        return max(1, dt)

    def _draw_price(self) -> float:
        if self._best_bid is not None and self._best_ask is not None:
            mid = (self._best_bid + self._best_ask) / 2.0
            return _clip01(mid + self._rng.uniform(-self._price_jitter, self._price_jitter))
        return self._rng.uniform(self._price_low, self._price_high)

    def _poisson(self, lam: float) -> int:
        if lam <= 0.0:
            return 0
        threshold = exp(-lam)
        k = 0
        p = 1.0
        while p > threshold:
            k += 1
            p *= self._rng.random()
        return k - 1
