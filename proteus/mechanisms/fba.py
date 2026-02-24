"""Frequent batch auction mechanism implementation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from proteus.core.events import CancelIntent, Fill, OrderIntent, Side
from proteus.mechanisms.base import Mechanism

_EPS = 1e-12
_PRICE_TIE_POLICIES = {"min_imbalance", "lower", "upper", "midpoint"}
_ALLOCATION_POLICIES = {"time_priority", "pro_rata"}


@dataclass
class _BatchOrder:
    order_id: str
    agent_id: str
    side: Side
    price: float
    remaining_size: float
    ts_ms: int
    seq_no: int


@dataclass(frozen=True)
class _PriceCandidate:
    price: float
    matched_size: float
    imbalance: float


class FBAMechanism(Mechanism):
    """
    Frequent batch auction with uniform-price clears.

    v1 behavior:
    - collects orders continuously
    - clears on fixed interval boundaries
    - computes a uniform clearing price that maximizes matched volume
    - resolves price ties via configurable policy
    - allocates scarce-side fills via configurable policy
    """

    name = "fba"

    def __init__(
        self,
        *,
        batch_interval_ms: int = 100,
        price_tie_policy: str = "min_imbalance",
        allocation_policy: str = "time_priority",
    ) -> None:
        if batch_interval_ms <= 0:
            raise ValueError("batch_interval_ms must be > 0")
        if price_tie_policy not in _PRICE_TIE_POLICIES:
            raise ValueError(
                f"unsupported price_tie_policy: {price_tie_policy} "
                f"(expected one of {sorted(_PRICE_TIE_POLICIES)})"
            )
        if allocation_policy not in _ALLOCATION_POLICIES:
            raise ValueError(
                f"unsupported allocation_policy: {allocation_policy} "
                f"(expected one of {sorted(_ALLOCATION_POLICIES)})"
            )

        self.batch_interval_ms = batch_interval_ms
        self.price_tie_policy = price_tie_policy
        self.allocation_policy = allocation_policy

        self._orders_by_id: dict[str, _BatchOrder] = {}
        self._next_order_seq = 1
        self._next_fill_seq = 1
        self._next_batch_ts_ms = batch_interval_ms

    def submit(self, intent: OrderIntent) -> None:
        self._validate_order_intent(intent)
        if intent.intent_id in self._orders_by_id:
            raise ValueError(f"duplicate order id: {intent.intent_id}")

        self._orders_by_id[intent.intent_id] = _BatchOrder(
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

        price_and_size = self._select_clearing_price(eligible)
        if price_and_size is None:
            return []

        clearing_price, matched_size = price_and_size
        if matched_size <= _EPS:
            return []

        buy_side = self._sorted_orders(
            [
                order
                for order in eligible
                if order.side is Side.BUY and order.price + _EPS >= clearing_price
            ]
        )
        sell_side = self._sorted_orders(
            [
                order
                for order in eligible
                if order.side is Side.SELL and order.price <= clearing_price + _EPS
            ]
        )

        buy_alloc = self._allocate_side(buy_side, matched_size)
        sell_alloc = self._allocate_side(sell_side, matched_size)

        return self._pair_allocations(
            buy_alloc=buy_alloc,
            sell_alloc=sell_alloc,
            price=clearing_price,
            ts_ms=batch_ts_ms,
        )

    def _select_clearing_price(
        self,
        orders: list[_BatchOrder],
    ) -> tuple[float, float] | None:
        candidate_prices = sorted({order.price for order in orders})
        if not candidate_prices:
            return None

        candidates: list[_PriceCandidate] = []
        for price in candidate_prices:
            buy_qty = sum(
                order.remaining_size
                for order in orders
                if order.side is Side.BUY and order.price + _EPS >= price
            )
            sell_qty = sum(
                order.remaining_size
                for order in orders
                if order.side is Side.SELL and order.price <= price + _EPS
            )
            matched = min(buy_qty, sell_qty)
            if matched <= _EPS:
                continue
            candidates.append(
                _PriceCandidate(
                    price=price,
                    matched_size=matched,
                    imbalance=abs(buy_qty - sell_qty),
                )
            )

        if not candidates:
            return None

        max_matched = max(candidate.matched_size for candidate in candidates)
        best = [
            candidate
            for candidate in candidates
            if abs(candidate.matched_size - max_matched) <= _EPS
        ]

        if self.price_tie_policy == "lower":
            chosen = min(best, key=lambda candidate: candidate.price)
            return (chosen.price, chosen.matched_size)

        if self.price_tie_policy == "upper":
            chosen = max(best, key=lambda candidate: candidate.price)
            return (chosen.price, chosen.matched_size)

        if self.price_tie_policy == "midpoint":
            lower = min(candidate.price for candidate in best)
            upper = max(candidate.price for candidate in best)
            return ((lower + upper) / 2.0, max_matched)

        min_imbalance = min(candidate.imbalance for candidate in best)
        best = [
            candidate
            for candidate in best
            if abs(candidate.imbalance - min_imbalance) <= _EPS
        ]
        lower = min(candidate.price for candidate in best)
        upper = max(candidate.price for candidate in best)
        return ((lower + upper) / 2.0, max_matched)

    def _allocate_side(
        self,
        side_orders: list[_BatchOrder],
        matched_size: float,
    ) -> list[tuple[_BatchOrder, float]]:
        if matched_size <= _EPS or not side_orders:
            return []

        total_available = sum(order.remaining_size for order in side_orders)
        if total_available <= _EPS:
            return []

        target = min(matched_size, total_available)
        if target <= _EPS:
            return []

        if self.allocation_policy == "time_priority":
            allocations: list[tuple[_BatchOrder, float]] = []
            remaining = target
            for order in side_orders:
                if remaining <= _EPS:
                    break
                qty = min(order.remaining_size, remaining)
                if qty > _EPS:
                    allocations.append((order, qty))
                    remaining -= qty
            return allocations

        raw_allocations = [
            min(order.remaining_size, target * (order.remaining_size / total_available))
            for order in side_orders
        ]
        allocated = sum(raw_allocations)
        residual = max(0.0, target - allocated)

        if residual > _EPS:
            for idx, order in enumerate(side_orders):
                spare = max(0.0, order.remaining_size - raw_allocations[idx])
                extra = min(spare, residual)
                raw_allocations[idx] += extra
                residual -= extra
                if residual <= _EPS:
                    break

        return [
            (order, qty)
            for order, qty in zip(side_orders, raw_allocations, strict=False)
            if qty > _EPS
        ]

    def _pair_allocations(
        self,
        *,
        buy_alloc: list[tuple[_BatchOrder, float]],
        sell_alloc: list[tuple[_BatchOrder, float]],
        price: float,
        ts_ms: int,
    ) -> list[Fill]:
        fills: list[Fill] = []
        if not buy_alloc or not sell_alloc:
            return fills

        buys = [[order, qty] for order, qty in buy_alloc]
        sells = [[order, qty] for order, qty in sell_alloc]

        buy_idx = 0
        sell_idx = 0
        while buy_idx < len(buys) and sell_idx < len(sells):
            buy_order, buy_qty = buys[buy_idx]
            sell_order, sell_qty = sells[sell_idx]

            size = min(buy_qty, sell_qty)
            if size <= _EPS:
                if buy_qty <= _EPS:
                    buy_idx += 1
                if sell_qty <= _EPS:
                    sell_idx += 1
                continue

            fills.append(
                Fill(
                    fill_id=f"fill-{self._next_fill_seq}",
                    ts_ms=ts_ms,
                    buy_agent_id=buy_order.agent_id,
                    sell_agent_id=sell_order.agent_id,
                    price=price,
                    size=size,
                )
            )
            self._next_fill_seq += 1

            buy_order.remaining_size = max(0.0, buy_order.remaining_size - size)
            sell_order.remaining_size = max(0.0, sell_order.remaining_size - size)

            buys[buy_idx][1] -= size
            sells[sell_idx][1] -= size

            if buys[buy_idx][1] <= _EPS:
                buys[buy_idx][1] = 0.0
                buy_idx += 1
            if sells[sell_idx][1] <= _EPS:
                sells[sell_idx][1] = 0.0
                sell_idx += 1

        return fills

    def _purge_depleted(self) -> None:
        depleted = [
            order_id
            for order_id, order in self._orders_by_id.items()
            if order.remaining_size <= _EPS
        ]
        for order_id in depleted:
            self._orders_by_id.pop(order_id, None)

    @staticmethod
    def _sorted_orders(orders: list[_BatchOrder]) -> list[_BatchOrder]:
        return sorted(orders, key=lambda order: (order.ts_ms, order.seq_no, order.order_id))

    @staticmethod
    def _validate_order_intent(intent: OrderIntent) -> None:
        if intent.ts_ms < 0:
            raise ValueError("ts_ms must be non-negative")
        if not isfinite(intent.price) or intent.price < 0.0 or intent.price > 1.0:
            raise ValueError("price must be finite and in [0,1]")
        if not isfinite(intent.size) or intent.size <= 0.0:
            raise ValueError("size must be finite and > 0")
