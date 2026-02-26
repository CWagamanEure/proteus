"""Request-for-quote mechanism implementation."""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import isfinite

from proteus.core.events import CancelIntent, Fill, OrderIntent, Side
from proteus.mechanisms.base import Mechanism

_EPS = 1e-12


@dataclass(frozen=True)
class RFQRequestIntent:
    request_id: str
    requester_id: str
    ts_ms: int
    side: Side
    size: float
    ttl_ms: int
    symbol: str = "binary"
    limit_price: float | None = None


@dataclass(frozen=True)
class RFQQuoteIntent:
    quote_id: str
    request_id: str
    dealer_id: str
    ts_ms: int
    side: Side
    price: float
    size: float
    ttl_ms: int | None = None


@dataclass(frozen=True)
class RFQAcceptIntent:
    accept_id: str
    request_id: str
    requester_id: str
    quote_id: str
    ts_ms: int


@dataclass
class _OpenRequest:
    request_id: str
    requester_id: str
    side: Side
    size: float
    remaining_size: float
    ts_ms: int
    expires_ts_ms: int
    symbol: str
    limit_price: float | None
    closed: bool = False


@dataclass
class _DealerQuote:
    quote_id: str
    request_id: str
    dealer_id: str
    side: Side
    price: float
    size: float
    ts_ms: int
    expires_ts_ms: int


class RFQMechanism(Mechanism):
    """
    Baseline RFQ engine with explicit request -> quote -> accept.

    Notes:
    - This extends the generic Mechanism API with RFQ-specific methods:
      `request_quote`, `submit_quote`, `accept_quote`.
    - `submit(OrderIntent)` is intentionally unsupported for RFQ.
    """

    name = "rfq"

    def __init__(
        self,
        *,
        min_response_latency_ms: int = 0,
        default_request_ttl_ms: int = 250,
        allowed_dealer_ids: tuple[str, ...] | list[str] | None = None,
        max_quotes_per_request: int | None = None,
    ) -> None:
        if min_response_latency_ms < 0:
            raise ValueError("min_response_latency_ms must be >= 0")
        if default_request_ttl_ms <= 0:
            raise ValueError("default_request_ttl_ms must be > 0")
        if max_quotes_per_request is not None and max_quotes_per_request <= 0:
            raise ValueError("max_quotes_per_request must be > 0 when provided")

        self.min_response_latency_ms = min_response_latency_ms
        self.default_request_ttl_ms = default_request_ttl_ms
        self.allowed_dealer_ids = (
            None if allowed_dealer_ids is None else frozenset(str(x) for x in allowed_dealer_ids)
        )
        self.max_quotes_per_request = max_quotes_per_request

        self._requests_by_id: dict[str, _OpenRequest] = {}
        self._quotes_by_request: dict[str, dict[str, _DealerQuote]] = {}

        self._pending_actions: list[tuple[int, int, str, object]] = []
        self._next_action_seq = 1
        self._next_fill_seq = 1

    def submit(self, intent: OrderIntent) -> None:
        _ = intent
        raise ValueError(
            "RFQMechanism does not accept generic OrderIntent. "
            "Use request_quote(...), submit_quote(...), and accept_quote(...)."
        )

    def cancel(self, intent: CancelIntent) -> None:
        if intent.ts_ms < 0:
            raise ValueError("ts_ms must be non-negative")
        self._enqueue("cancel", intent.ts_ms, intent)

    def clear(self, ts_ms: int) -> list[Fill]:
        if ts_ms < 0:
            raise ValueError("ts_ms must be non-negative")

        fills: list[Fill] = []
        while self._pending_actions and self._pending_actions[0][0] <= ts_ms:
            action_ts, _, kind, payload = heappop(self._pending_actions)
            self._expire_up_to(action_ts)
            maybe_fill = self._apply_action(kind, payload, action_ts)
            if maybe_fill is not None:
                fills.append(maybe_fill)

        self._expire_up_to(ts_ms)
        return fills

    def request_quote(self, intent: RFQRequestIntent) -> None:
        self._validate_request_intent(intent)
        self._enqueue("request", intent.ts_ms, intent)

    def submit_quote(self, intent: RFQQuoteIntent) -> None:
        self._validate_quote_intent(intent)
        self._enqueue("quote", intent.ts_ms, intent)

    def accept_quote(self, intent: RFQAcceptIntent) -> None:
        self._validate_accept_intent(intent)
        self._enqueue("accept", intent.ts_ms, intent)

    def _enqueue(self, kind: str, ts_ms: int, payload: object) -> None:
        heappush(self._pending_actions, (ts_ms, self._next_action_seq, kind, payload))
        self._next_action_seq += 1

    def _apply_action(self, kind: str, payload: object, action_ts_ms: int) -> Fill | None:
        if kind == "request":
            self._apply_request(payload)  # type: ignore[arg-type]
            return None
        if kind == "quote":
            self._apply_quote(payload)  # type: ignore[arg-type]
            return None
        if kind == "accept":
            return self._apply_accept(payload, action_ts_ms)  # type: ignore[arg-type]
        if kind == "cancel":
            self._apply_cancel(payload)  # type: ignore[arg-type]
            return None
        raise ValueError(f"unknown RFQ action kind: {kind}")

    def _apply_request(self, intent: RFQRequestIntent) -> None:
        if intent.request_id in self._requests_by_id:
            raise ValueError(f"duplicate request id: {intent.request_id}")

        ttl_ms = intent.ttl_ms if intent.ttl_ms > 0 else self.default_request_ttl_ms
        req = _OpenRequest(
            request_id=intent.request_id,
            requester_id=intent.requester_id,
            side=intent.side,
            size=intent.size,
            remaining_size=intent.size,
            ts_ms=intent.ts_ms,
            expires_ts_ms=intent.ts_ms + ttl_ms,
            symbol=intent.symbol,
            limit_price=intent.limit_price,
        )
        self._requests_by_id[intent.request_id] = req
        self._quotes_by_request[intent.request_id] = {}

    def _apply_quote(self, intent: RFQQuoteIntent) -> None:
        req = self._requests_by_id.get(intent.request_id)
        if req is None or req.closed:
            return
        if intent.ts_ms > req.expires_ts_ms:
            return
        if intent.side is req.side:
            return
        if self.allowed_dealer_ids is not None and intent.dealer_id not in self.allowed_dealer_ids:
            return
        if intent.ts_ms < req.ts_ms + self.min_response_latency_ms:
            return
        if req.limit_price is not None:
            if req.side is Side.BUY and intent.price - _EPS > req.limit_price:
                return
            if req.side is Side.SELL and intent.price + _EPS < req.limit_price:
                return

        quote_expiry = req.expires_ts_ms
        if intent.ttl_ms is not None:
            if intent.ttl_ms <= 0:
                return
            quote_expiry = min(quote_expiry, intent.ts_ms + intent.ttl_ms)

        quotes = self._quotes_by_request.setdefault(intent.request_id, {})

        # v1 behavior: replace previous quote from same dealer on same request.
        for quote_id, existing in list(quotes.items()):
            if existing.dealer_id == intent.dealer_id:
                quotes.pop(quote_id, None)

        if self.max_quotes_per_request is not None and len(quotes) >= self.max_quotes_per_request:
            return

        quotes[intent.quote_id] = _DealerQuote(
            quote_id=intent.quote_id,
            request_id=intent.request_id,
            dealer_id=intent.dealer_id,
            side=intent.side,
            price=intent.price,
            size=intent.size,
            ts_ms=intent.ts_ms,
            expires_ts_ms=quote_expiry,
        )

    def _apply_accept(self, intent: RFQAcceptIntent, action_ts_ms: int) -> Fill | None:
        req = self._requests_by_id.get(intent.request_id)
        if req is None or req.closed:
            return None
        if req.requester_id != intent.requester_id:
            return None
        if action_ts_ms > req.expires_ts_ms:
            return None

        quotes = self._quotes_by_request.get(intent.request_id, {})
        quote = quotes.get(intent.quote_id)
        if quote is None:
            return None
        if action_ts_ms > quote.expires_ts_ms:
            return None

        fill_size = min(req.remaining_size, quote.size)
        if fill_size <= _EPS:
            return None

        req.remaining_size = max(0.0, req.remaining_size - fill_size)
        req.closed = True
        self._quotes_by_request.pop(intent.request_id, None)

        if req.side is Side.BUY:
            buy_agent_id = req.requester_id
            sell_agent_id = quote.dealer_id
        else:
            buy_agent_id = quote.dealer_id
            sell_agent_id = req.requester_id

        fill = Fill(
            fill_id=f"rfq-fill-{self._next_fill_seq}",
            ts_ms=action_ts_ms,
            buy_agent_id=buy_agent_id,
            sell_agent_id=sell_agent_id,
            price=quote.price,
            size=fill_size,
        )
        self._next_fill_seq += 1
        return fill

    def _apply_cancel(self, intent: CancelIntent) -> None:
        req = self._requests_by_id.get(intent.order_id)
        if req is not None:
            if req.requester_id == intent.agent_id:
                req.closed = True
                req.remaining_size = 0.0
                self._quotes_by_request.pop(intent.order_id, None)
            return

        for request_id, quotes in self._quotes_by_request.items():
            quote = quotes.get(intent.order_id)
            if quote is None:
                continue
            if quote.dealer_id == intent.agent_id:
                quotes.pop(intent.order_id, None)
            if not quotes:
                self._quotes_by_request[request_id] = {}
            return

    def _expire_up_to(self, ts_ms: int) -> None:
        expired_requests: list[str] = []
        for request_id, req in self._requests_by_id.items():
            if req.closed or ts_ms > req.expires_ts_ms:
                req.closed = True
                req.remaining_size = 0.0
                expired_requests.append(request_id)

        for request_id in expired_requests:
            self._quotes_by_request.pop(request_id, None)

        for request_id, quotes in list(self._quotes_by_request.items()):
            req = self._requests_by_id.get(request_id)
            if req is None or req.closed:
                self._quotes_by_request.pop(request_id, None)
                continue
            for quote_id, quote in list(quotes.items()):
                if ts_ms > quote.expires_ts_ms:
                    quotes.pop(quote_id, None)
            if not quotes:
                self._quotes_by_request[request_id] = {}

    @staticmethod
    def _validate_request_intent(intent: RFQRequestIntent) -> None:
        if intent.ts_ms < 0:
            raise ValueError("request ts_ms must be non-negative")
        if not isfinite(intent.size) or intent.size <= 0.0:
            raise ValueError("request size must be finite and > 0")
        if intent.ttl_ms <= 0:
            raise ValueError("request ttl_ms must be > 0")
        if intent.limit_price is not None and (
            not isfinite(intent.limit_price) or intent.limit_price < 0.0 or intent.limit_price > 1.0
        ):
            raise ValueError("request limit_price must be finite and in [0,1]")

    @staticmethod
    def _validate_quote_intent(intent: RFQQuoteIntent) -> None:
        if intent.ts_ms < 0:
            raise ValueError("quote ts_ms must be non-negative")
        if not isfinite(intent.price) or intent.price < 0.0 or intent.price > 1.0:
            raise ValueError("quote price must be finite and in [0,1]")
        if not isfinite(intent.size) or intent.size <= 0.0:
            raise ValueError("quote size must be finite and > 0")
        if intent.ttl_ms is not None and intent.ttl_ms <= 0:
            raise ValueError("quote ttl_ms must be > 0 when provided")

    @staticmethod
    def _validate_accept_intent(intent: RFQAcceptIntent) -> None:
        if intent.ts_ms < 0:
            raise ValueError("accept ts_ms must be non-negative")
