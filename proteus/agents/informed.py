"""Informed trader agent v1 implementation."""

from __future__ import annotations

from proteus.agents.base import Agent
from proteus.core.events import Event, EventType, OrderIntent, Side


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


class InformedTraderAgent(Agent):
    """
    Thresholded informed trader with edge-scaled sizing.
    """

    def __init__(
        self,
        agent_id: str,
        *,
        theta: float = 0.01,
        fee_bps: float = 0.0,
        latency_penalty: float = 0.0,
        min_size: float = 1.0,
        max_size: float = 5.0,
        size_slope: float = 20.0,
    ) -> None:
        self.agent_id = agent_id
        self._theta = theta
        self._fee_bps = fee_bps
        self._latency_penalty = latency_penalty
        self._min_size = min_size
        self._max_size = max_size
        self._size_slope = size_slope

        self._signal: float | None = None
        self._best_bid: float | None = None
        self._best_ask: float | None = None
        self._intent_seq = 0

    def on_event(self, event: Event) -> None:
        if event.event_type is EventType.NEWS:
            signal = _extract_float(event.payload, "signal", "belief", "p_t")
            if signal is not None:
                self._signal = _clip01(signal)
            return

        bid = _extract_float(event.payload, "best_bid", "bid")
        ask = _extract_float(event.payload, "best_ask", "ask")
        if bid is not None:
            self._best_bid = _clip01(bid)
        if ask is not None:
            self._best_ask = _clip01(ask)

    def generate_intents(self, ts_ms: int):
        if ts_ms < 0:
            raise ValueError("ts_ms must be non-negative")
        if self._signal is None or self._best_bid is None or self._best_ask is None:
            return ()

        threshold = self._theta + (self._fee_bps / 10_000.0) + self._latency_penalty

        buy_edge = self._signal - self._best_ask
        sell_edge = self._best_bid - self._signal

        if buy_edge <= threshold and sell_edge <= threshold:
            return ()

        if buy_edge >= sell_edge:
            size = self._size_for_edge(buy_edge - threshold)
            return (self._make_intent(ts_ms=ts_ms, side=Side.BUY, price=self._best_ask, size=size),)

        size = self._size_for_edge(sell_edge - threshold)
        return (self._make_intent(ts_ms=ts_ms, side=Side.SELL, price=self._best_bid, size=size),)

    def _size_for_edge(self, net_edge: float) -> float:
        raw = self._min_size + (self._size_slope * max(0.0, net_edge))
        return min(self._max_size, max(self._min_size, raw))

    def _make_intent(self, *, ts_ms: int, side: Side, price: float, size: float) -> OrderIntent:
        self._intent_seq += 1
        return OrderIntent(
            intent_id=f"{self.agent_id}-{ts_ms}-{self._intent_seq}",
            agent_id=self.agent_id,
            ts_ms=ts_ms,
            side=side,
            price=_clip01(price),
            size=size,
        )


def _extract_float(payload: dict, *keys: str) -> float | None:
    for key in keys:
        if key in payload and payload[key] is not None:
            return float(payload[key])
    return None
