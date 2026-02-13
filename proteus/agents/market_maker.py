"""Market maker agent v1 implementation."""

from __future__ import annotations

from proteus.agents.base import Agent
from proteus.core.events import Event, EventType, OrderIntent, Side


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


class MarketMakerAgent(Agent):
    """
    Simple inventory-aware market maker with configurable spread model.
    """

    def __init__(
        self,
        agent_id: str,
        *,
        belief_init: float = 0.5,
        h0: float = 0.01,
        kappa_inventory: float = 0.01,
        a_inventory_spread: float = 0.002,
        b_vol_spread: float = 0.5,
        c_as_spread: float = 0.5,
        min_half_spread: float = 0.0025,
        base_size: float = 1.0,
        min_size: float = 0.1,
        max_inventory: float = 20.0,
        belief_alpha: float = 0.35,
        vol_alpha: float = 0.25,
        as_alpha: float = 0.2,
    ) -> None:
        self.agent_id = agent_id
        self._belief = _clip01(belief_init)
        self._inventory = 0.0

        self._h0 = h0
        self._kappa_inventory = kappa_inventory
        self._a_inventory_spread = a_inventory_spread
        self._b_vol_spread = b_vol_spread
        self._c_as_spread = c_as_spread
        self._min_half_spread = min_half_spread
        self._base_size = base_size
        self._min_size = min_size
        self._max_inventory = max_inventory

        self._belief_alpha = belief_alpha
        self._vol_alpha = vol_alpha
        self._as_alpha = as_alpha

        self._sigma_hat = 0.0
        self._as_hat = 0.0
        self._last_mid: float | None = None
        self._intent_seq = 0

    def on_event(self, event: Event) -> None:
        if event.event_type is EventType.NEWS:
            signal = _extract_float(event.payload, "signal", "belief", "p_t")
            if signal is not None:
                self._belief = _clip01(
                    ((1.0 - self._belief_alpha) * self._belief) + (self._belief_alpha * signal)
                )
            return

        if event.event_type is EventType.FILL:
            size = float(event.payload.get("size", 0.0) or 0.0)
            fill_price = _extract_float(event.payload, "price")

            if event.payload.get("buy_agent_id") == self.agent_id:
                self._inventory += size
            elif event.payload.get("sell_agent_id") == self.agent_id:
                self._inventory -= size

            if fill_price is not None and (
                event.payload.get("buy_agent_id") == self.agent_id
                or event.payload.get("sell_agent_id") == self.agent_id
            ):
                as_sample = abs(self._belief - fill_price)
                self._as_hat = ((1.0 - self._as_alpha) * self._as_hat) + (
                    self._as_alpha * as_sample
                )
                self._update_vol_from_mid(fill_price)
            return

        mid = _extract_mid(event.payload)
        if mid is not None:
            self._update_vol_from_mid(mid)

    def generate_intents(self, ts_ms: int) -> list[OrderIntent]:
        if ts_ms < 0:
            raise ValueError("ts_ms must be non-negative")

        reservation = _clip01(self._belief - (self._kappa_inventory * self._inventory))
        half_spread = max(
            self._min_half_spread,
            self._h0
            + (self._a_inventory_spread * abs(self._inventory))
            + (self._b_vol_spread * self._sigma_hat)
            + (self._c_as_spread * self._as_hat),
        )

        size_scale = max(0.2, 1.0 - (abs(self._inventory) / max(self._max_inventory, 1e-9)))
        order_size = max(self._min_size, self._base_size * size_scale)

        intents: list[OrderIntent] = []

        # At risk limit, quote only the inventory-reducing side
        if self._inventory >= self._max_inventory:
            ask = _clip01(reservation + half_spread)
            intents.append(
                self._make_intent(ts_ms=ts_ms, side=Side.SELL, price=ask, size=order_size)
            )
            return intents
        if self._inventory <= -self._max_inventory:
            bid = _clip01(reservation - half_spread)
            intents.append(
                self._make_intent(ts_ms=ts_ms, side=Side.BUY, price=bid, size=order_size)
            )
            return intents

        bid = _clip01(reservation - half_spread)
        ask = _clip01(reservation + half_spread)
        if bid >= ask:
            epsilon = min(self._min_half_spread, 0.001)
            bid = _clip01(reservation - epsilon)
            ask = _clip01(reservation + epsilon)

        intents.append(self._make_intent(ts_ms=ts_ms, side=Side.BUY, price=bid, size=order_size))
        intents.append(self._make_intent(ts_ms=ts_ms, side=Side.SELL, price=ask, size=order_size))
        return intents

    def _make_intent(self, *, ts_ms: int, side: Side, price: float, size: float) -> OrderIntent:
        self._intent_seq += 1
        return OrderIntent(
            intent_id=f"{self.agent_id}-{ts_ms}-{self._intent_seq}",
            agent_id=self.agent_id,
            ts_ms=ts_ms,
            side=side,
            price=price,
            size=size,
        )

    def _update_vol_from_mid(self, mid: float) -> None:
        mid = _clip01(mid)
        if self._last_mid is None:
            self._last_mid = mid
            return
        delta = abs(mid - self._last_mid)
        self._sigma_hat = ((1.0 - self._vol_alpha) * self._sigma_hat) + (self._vol_alpha * delta)
        self._last_mid = mid


def _extract_float(payload: dict, *keys: str) -> float | None:
    for key in keys:
        if key in payload and payload[key] is not None:
            return float(payload[key])
    return None


def _extract_mid(payload: dict) -> float | None:
    if "mid_price" in payload and payload["mid_price"] is not None:
        return _clip01(float(payload["mid_price"]))

    bid = payload.get("best_bid")
    ask = payload.get("best_ask")
    if bid is not None and ask is not None:
        return _clip01((float(bid) + float(ask)) / 2.0)
    return None
