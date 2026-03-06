"""Dual-flow batch mechanism with maker/taker segregation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from proteus.core.events import CancelIntent, Fill, OrderIntent, Side
from proteus.mechanisms.base import Mechanism

_EPS = 1e-12


@dataclass
class _DualFlowOrder:
    order_id: str
    agent_id: str
    side: Side
    price: float
    remaining_size: float
    ts_ms: int
    seq_no: int


class DualFlowBatchMechanism(Mechanism):
    """
    Optional phase-4 mechanism with segregated buy/sell clears.

    v1 behavior:
    - maker/taker segregation via maker id prefixes
    - separate buy-flow and sell-flow batch clears
    - no maker-maker matching by construction
    """

    name = "dual_flow_batch"

    def __init__(
        self,
        *,
        batch_interval_ms: int = 100,
        maker_id_prefixes: tuple[str, ...] = ("mm-",),
    ) -> None:
        if batch_interval_ms <= 0:
            raise ValueError("batch_interval_ms must be > 0")
        if not maker_id_prefixes:
            raise ValueError("maker_id_prefixes must be non-empty")

        self.batch_interval_ms = batch_interval_ms
        self.maker_id_prefixes = tuple(str(prefix) for prefix in maker_id_prefixes)

        self._orders_by_id: dict[str, _DualFlowOrder] = {}
        self._next_order_seq = 1
        self._next_fill_seq = 1
        self._next_batch_ts_ms = batch_interval_ms

    def submit(self, intent: OrderIntent) -> None:
        self._validate_order_intent(intent)
        if intent.intent_id in self._orders_by_id:
            raise ValueError(f"duplicate order id: {intent.intent_id}")

        self._orders_by_id[intent.intent_id] = _DualFlowOrder(
            order_id=intent.intent_id,
            agent_id=intent.agent_id,
            side=intent.side,
            price=intent.price,
            remaining_size=intent.size,
            ts_ms=intent.ts_ms,
            seq_no=self._next_order_seq,
        )
        self._next_order_seq += 1

    def cancel(self, intent: CancelIntent) -> None:
        order = self._orders_by_id.get(intent.order_id)
        if order is None:
            return
        if order.agent_id != intent.agent_id:
            return
        order.remaining_size = 0.0

    def clear(self, ts_ms: int) -> list[Fill]:
        if ts_ms < 0:
            raise ValueError("ts_ms must be non-negative")

        fills: list[Fill] = []
        while self._next_batch_ts_ms <= ts_ms:
            fills.extend(self._clear_one_batch(self._next_batch_ts_ms))
            self._next_batch_ts_ms += self.batch_interval_ms

        self._purge_depleted()
        return fills

    def _clear_one_batch(self, batch_ts_ms: int) -> list[Fill]:
        eligible = [
            order
            for order in self._orders_by_id.values()
            if order.remaining_size > _EPS and order.ts_ms <= batch_ts_ms
        ]
        if not eligible:
            return []

        maker_sell = self._sorted_orders(
            [
                order
                for order in eligible
                if self._is_maker(order.agent_id) and order.side is Side.SELL
            ],
            key_fn=lambda order: (order.price, order.ts_ms, order.seq_no, order.order_id),
        )
        maker_buy = self._sorted_orders(
            [
                order
                for order in eligible
                if self._is_maker(order.agent_id) and order.side is Side.BUY
            ],
            key_fn=lambda order: (-order.price, order.ts_ms, order.seq_no, order.order_id),
        )

        taker_buy = self._sorted_orders(
            [
                order
                for order in eligible
                if (not self._is_maker(order.agent_id)) and order.side is Side.BUY
            ]
        )
        taker_sell = self._sorted_orders(
            [
                order
                for order in eligible
                if (not self._is_maker(order.agent_id)) and order.side is Side.SELL
            ]
        )

        fills: list[Fill] = []
        fills.extend(
            self._match_buy_flow(
                taker_buy=taker_buy,
                maker_sell=maker_sell,
                ts_ms=batch_ts_ms,
            )
        )
        fills.extend(
            self._match_sell_flow(
                taker_sell=taker_sell,
                maker_buy=maker_buy,
                ts_ms=batch_ts_ms,
            )
        )
        return fills

    def _match_buy_flow(
        self,
        *,
        taker_buy: list[_DualFlowOrder],
        maker_sell: list[_DualFlowOrder],
        ts_ms: int,
    ) -> list[Fill]:
        fills: list[Fill] = []
        maker_idx = 0
        for taker in taker_buy:
            while taker.remaining_size > _EPS and maker_idx < len(maker_sell):
                maker = maker_sell[maker_idx]
                if maker.remaining_size <= _EPS:
                    maker_idx += 1
                    continue
                if maker.price - _EPS > taker.price:
                    break

                size = min(taker.remaining_size, maker.remaining_size)
                if size <= _EPS:
                    maker_idx += 1
                    continue

                fills.append(
                    Fill(
                        fill_id=f"df-fill-{self._next_fill_seq}",
                        ts_ms=ts_ms,
                        buy_agent_id=taker.agent_id,
                        sell_agent_id=maker.agent_id,
                        price=maker.price,
                        size=size,
                    )
                )
                self._next_fill_seq += 1

                taker.remaining_size = max(0.0, taker.remaining_size - size)
                maker.remaining_size = max(0.0, maker.remaining_size - size)
                if maker.remaining_size <= _EPS:
                    maker_idx += 1

        return fills

    def _match_sell_flow(
        self,
        *,
        taker_sell: list[_DualFlowOrder],
        maker_buy: list[_DualFlowOrder],
        ts_ms: int,
    ) -> list[Fill]:
        fills: list[Fill] = []
        maker_idx = 0
        for taker in taker_sell:
            while taker.remaining_size > _EPS and maker_idx < len(maker_buy):
                maker = maker_buy[maker_idx]
                if maker.remaining_size <= _EPS:
                    maker_idx += 1
                    continue
                if maker.price + _EPS < taker.price:
                    break

                size = min(taker.remaining_size, maker.remaining_size)
                if size <= _EPS:
                    maker_idx += 1
                    continue

                fills.append(
                    Fill(
                        fill_id=f"df-fill-{self._next_fill_seq}",
                        ts_ms=ts_ms,
                        buy_agent_id=maker.agent_id,
                        sell_agent_id=taker.agent_id,
                        price=maker.price,
                        size=size,
                    )
                )
                self._next_fill_seq += 1

                taker.remaining_size = max(0.0, taker.remaining_size - size)
                maker.remaining_size = max(0.0, maker.remaining_size - size)
                if maker.remaining_size <= _EPS:
                    maker_idx += 1

        return fills

    def _is_maker(self, agent_id: str) -> bool:
        return any(agent_id.startswith(prefix) for prefix in self.maker_id_prefixes)

    def _purge_depleted(self) -> None:
        depleted = [
            order_id
            for order_id, order in self._orders_by_id.items()
            if order.remaining_size <= _EPS
        ]
        for order_id in depleted:
            self._orders_by_id.pop(order_id, None)

    @staticmethod
    def _sorted_orders(
        orders: list[_DualFlowOrder],
        *,
        key_fn=None,
    ) -> list[_DualFlowOrder]:
        if key_fn is None:
            return sorted(orders, key=lambda order: (order.ts_ms, order.seq_no, order.order_id))
        return sorted(orders, key=key_fn)

    @staticmethod
    def _validate_order_intent(intent: OrderIntent) -> None:
        if intent.ts_ms < 0:
            raise ValueError("ts_ms must be non-negative")
        if not isfinite(intent.price) or not (0.0 <= intent.price <= 1.0):
            raise ValueError("price must be finite and in [0,1]")
        if not isfinite(intent.size) or intent.size <= 0.0:
            raise ValueError("size must be finite and > 0")
