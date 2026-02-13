"""Central limit order book mechanism stub."""

from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass
from math import isfinite

from proteus.core.events import CancelIntent, Fill, OrderIntent, Side
from proteus.mechanisms.base import Mechanism


@dataclass
class _BookOrder:
    order_id: str
    agent_id: str
    side: Side
    price: float
    remaining_size: float
    ts_ms: int
    seq_no: int


class CLOBMechanism(Mechanism):
    """
    Deterministic price-time CLOB with cancels and partial fills.
    """

    name = "clob"

    def __init__(self) -> None:
        self._bids: dict[float, deque[_BookOrder]] = {}  # price level queues
        self._asks: dict[float, deque[_BookOrder]] = {}  # price level queues
        self._bid_heap: list[float] = []  # max-heap using negative prices
        self._ask_heap: list[float] = []  # min-heap
        self._orders_by_id: dict[str, _BookOrder] = {}
        self._next_order_seq = 1
        self._next_fill_seq = 1

    def submit(self, intent: OrderIntent) -> None:
        self._validate_order_intent(intent)
        if intent.intent_id in self._orders_by_id:
            raise ValueError(f"duplicate order id: {intent.intent_id}")

        order = _BookOrder(
            order_id=intent.intent_id,
            agent_id=intent.agent_id,
            side=intent.side,
            price=intent.price,
            remaining_size=intent.size,
            ts_ms=intent.ts_ms,
            seq_no=self._next_order_seq,
        )

        self._next_order_seq += 1
        self._orders_by_id[order.order_id] = order

        if order.side is Side.BUY:
            level = self._bids.setdefault(order.price, deque())
            if len(level) == 0:
                heapq.heappush(self._bid_heap, -order.price)
            level.append(order)
            return

        level = self._asks.setdefault(order.price, deque())
        if len(level) == 0:
            heapq.heappush(self._ask_heap, order.price)
        level.append(order)

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
        while True:
            best_bid = self._best_bid()
            best_ask = self._best_ask()
            if best_bid is None or best_ask is None:
                break
            if best_bid.price < best_ask.price:
                break

            size = min(best_bid.remaining_size, best_ask.remaining_size)
            if size <= 0.0:
                self._consume_depleted(best_bid)
                self._consume_depleted(best_ask)
                continue

            fill = Fill(
                fill_id=f"fill-{self._next_fill_seq}",
                ts_ms=ts_ms,
                buy_agent_id=best_bid.agent_id,
                sell_agent_id=best_ask.agent_id,
                price=self._execution_price(best_bid, best_ask),
                size=size,
            )

            self._next_fill_seq += 1
            fills.append(fill)

            best_bid.remaining_size -= size
            best_ask.remaining_size -= size

            self._consume_depleted(best_bid)
            self._consume_depleted(best_ask)

        return fills

    def _best_bid(self) -> _BookOrder | None:
        return self._best_order(heap=self._bid_heap, levels=self._bids, is_bid=True)

    def _best_ask(self) -> _BookOrder | None:
        return self._best_order(heap=self._ask_heap, levels=self._asks, is_bid=False)

    def _best_order(
        self,
        *,
        heap: list[float],
        levels: dict[float, deque[_BookOrder]],
        is_bid: bool,
    ) -> _BookOrder | None:
        while heap:
            price_key = -heap[0] if is_bid else heap[0]
            level = levels.get(price_key)
            if level is None or len(level) == 0:
                heapq.heappop(heap)
                if price_key in levels:
                    del levels[price_key]
                continue

            while level and level[0].remaining_size <= 0.0:
                head = level.popleft()
                self._orders_by_id.pop(head.order_id, None)

            if not level:
                heapq.heappop(heap)
                del levels[price_key]
                continue

            return level[0]
        return None

    def _consume_depleted(self, order: _BookOrder) -> None:
        if order.remaining_size > 0.0:
            return
        self._orders_by_id.pop(order.order_id, None)

    @staticmethod
    def _execution_price(bid: _BookOrder, ask: _BookOrder) -> float:
        # for now we treat the older order as the maker
        return bid.price if bid.seq_no < ask.seq_no else ask.price

    @staticmethod
    def _validate_order_intent(intent: OrderIntent) -> None:
        if intent.ts_ms < 0:
            raise ValueError("ts_ms must be non-negative")
        if not isfinite(intent.price) or intent.price < 0.0 or intent.price > 1.0:
            raise ValueError("price must be finite and in [0,1]")
        if not isfinite(intent.size) or intent.size <= 0.0:
            raise ValueError("size must be finite and > 0")
