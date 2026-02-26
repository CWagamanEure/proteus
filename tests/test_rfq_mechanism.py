from __future__ import annotations

from proteus.core.events import CancelIntent, OrderIntent, Side
from proteus.mechanisms.rfq import (
    RFQAcceptIntent,
    RFQMechanism,
    RFQQuoteIntent,
    RFQRequestIntent,
)


def test_rfq_enforces_response_latency_and_accepts_after_threshold() -> None:
    rfq = RFQMechanism(min_response_latency_ms=10)

    rfq.request_quote(
        RFQRequestIntent(
            request_id="r1",
            requester_id="taker-1",
            ts_ms=100,
            side=Side.BUY,
            size=2.0,
            ttl_ms=50,
        )
    )
    rfq.submit_quote(
        RFQQuoteIntent(
            quote_id="q-early",
            request_id="r1",
            dealer_id="dealer-a",
            ts_ms=105,
            side=Side.SELL,
            price=0.53,
            size=2.0,
        )
    )
    rfq.submit_quote(
        RFQQuoteIntent(
            quote_id="q-ok",
            request_id="r1",
            dealer_id="dealer-a",
            ts_ms=111,
            side=Side.SELL,
            price=0.52,
            size=2.0,
        )
    )
    rfq.accept_quote(
        RFQAcceptIntent(
            accept_id="a1",
            request_id="r1",
            requester_id="taker-1",
            quote_id="q-ok",
            ts_ms=120,
        )
    )

    fills = rfq.clear(200)
    assert len(fills) == 1
    fill = fills[0]
    assert fill.ts_ms == 120
    assert fill.buy_agent_id == "taker-1"
    assert fill.sell_agent_id == "dealer-a"
    assert fill.price == 0.52
    assert fill.size == 2.0


def test_rfq_request_ttl_expiry_prevents_accept() -> None:
    rfq = RFQMechanism()

    rfq.request_quote(
        RFQRequestIntent(
            request_id="r1",
            requester_id="taker-1",
            ts_ms=0,
            side=Side.BUY,
            size=1.0,
            ttl_ms=10,
        )
    )
    rfq.submit_quote(
        RFQQuoteIntent(
            quote_id="q1",
            request_id="r1",
            dealer_id="dealer-a",
            ts_ms=5,
            side=Side.SELL,
            price=0.55,
            size=1.0,
        )
    )
    rfq.accept_quote(
        RFQAcceptIntent(
            accept_id="a1",
            request_id="r1",
            requester_id="taker-1",
            quote_id="q1",
            ts_ms=20,
        )
    )

    assert rfq.clear(50) == []


def test_rfq_supports_multi_dealer_competition_and_explicit_accept_path() -> None:
    rfq = RFQMechanism(allowed_dealer_ids=("dealer-a", "dealer-b", "dealer-c"))

    rfq.request_quote(
        RFQRequestIntent(
            request_id="r1",
            requester_id="taker-1",
            ts_ms=0,
            side=Side.BUY,
            size=1.0,
            ttl_ms=100,
        )
    )
    rfq.submit_quote(
        RFQQuoteIntent(
            quote_id="q-a",
            request_id="r1",
            dealer_id="dealer-a",
            ts_ms=5,
            side=Side.SELL,
            price=0.56,
            size=1.0,
        )
    )
    rfq.submit_quote(
        RFQQuoteIntent(
            quote_id="q-b",
            request_id="r1",
            dealer_id="dealer-b",
            ts_ms=6,
            side=Side.SELL,
            price=0.54,
            size=1.0,
        )
    )
    rfq.accept_quote(
        RFQAcceptIntent(
            accept_id="a1",
            request_id="r1",
            requester_id="taker-1",
            quote_id="q-a",
            ts_ms=8,
        )
    )

    fills = rfq.clear(20)
    assert len(fills) == 1
    assert fills[0].sell_agent_id == "dealer-a"
    assert fills[0].price == 0.56


def test_rfq_cancel_request_drops_pending_quotes_and_prevents_fill() -> None:
    rfq = RFQMechanism()

    rfq.request_quote(
        RFQRequestIntent(
            request_id="r1",
            requester_id="taker-1",
            ts_ms=0,
            side=Side.SELL,
            size=1.0,
            ttl_ms=100,
        )
    )
    rfq.submit_quote(
        RFQQuoteIntent(
            quote_id="q1",
            request_id="r1",
            dealer_id="dealer-a",
            ts_ms=5,
            side=Side.BUY,
            price=0.49,
            size=1.0,
        )
    )
    rfq.cancel(
        CancelIntent(
            intent_id="c1",
            agent_id="taker-1",
            ts_ms=6,
            order_id="r1",
        )
    )
    rfq.accept_quote(
        RFQAcceptIntent(
            accept_id="a1",
            request_id="r1",
            requester_id="taker-1",
            quote_id="q1",
            ts_ms=8,
        )
    )

    assert rfq.clear(20) == []


def test_rfq_rejects_generic_order_submit_api() -> None:
    rfq = RFQMechanism()

    try:
        rfq.submit(
            OrderIntent(
                intent_id="o1",
                agent_id="x",
                ts_ms=0,
                side=Side.BUY,
                price=0.5,
                size=1.0,
            )
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
