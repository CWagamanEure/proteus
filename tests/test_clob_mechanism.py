from __future__ import annotations

from proteus.core.events import CancelIntent, OrderIntent, Side
from proteus.mechanisms.clob import CLOBMechanism


def _order(
    order_id: str,
    agent_id: str,
    side: Side,
    price: float,
    size: float,
    ts_ms: int,
) -> OrderIntent:
    return OrderIntent(
        intent_id=order_id,
        agent_id=agent_id,
        ts_ms=ts_ms,
        side=side,
        price=price,
        size=size,
    )


def test_price_time_priority_and_queue_position() -> None:
    clob = CLOBMechanism()
    clob.submit(_order("b1", "mm-1", Side.BUY, 0.50, 5.0, 1))
    clob.submit(_order("b2", "mm-2", Side.BUY, 0.50, 5.0, 2))
    clob.submit(_order("s1", "noise-1", Side.SELL, 0.50, 6.0, 3))

    fills = clob.clear(ts_ms=3)
    assert len(fills) == 2
    assert fills[0].buy_agent_id == "mm-1"
    assert fills[0].size == 5
    assert fills[1].buy_agent_id == "mm-2"
    assert fills[1].size == 1.0
    assert fills[0].price == 0.50
    assert fills[1].price == 0.50


def test_price_priority_overrides_arrival_time() -> None:
    clob = CLOBMechanism()
    clob.submit(_order("b1", "mm-1", Side.BUY, 0.49, 2.0, 1))
    clob.submit(_order("b2", "mm-2", Side.BUY, 0.50, 2.0, 2))
    clob.submit(_order("s1", "noise-1", Side.SELL, 0.49, 1.0, 3))

    fills = clob.clear(ts_ms=3)
    assert len(fills) == 1
    assert fills[0].buy_agent_id == "mm-2"
    assert fills[0].size == 1.0


def test_partial_fills_leave_resting_residual() -> None:
    clob = CLOBMechanism()
    clob.submit(_order("b1", "mm-1", Side.BUY, 0.55, 10.0, 1))
    clob.submit(_order("s1", "noise-1", Side.SELL, 0.55, 4.0, 2))

    first = clob.clear(ts_ms=2)
    assert len(first) == 1
    assert first[0].size == 4.0

    clob.submit(_order("s2", "noise-2", Side.SELL, 0.54, 3.0, 3))
    second = clob.clear(ts_ms=3)
    assert len(second) == 1
    assert second[0].buy_agent_id == "mm-1"
    assert second[0].size == 3.0


def test_cancel_race_prevents_fill_for_canceled_order() -> None:
    clob = CLOBMechanism()
    clob.submit(_order("b1", "mm-1", Side.BUY, 0.50, 2.0, 1))
    clob.submit(_order("b2", "mm-2", Side.BUY, 0.50, 2.0, 2))
    clob.cancel(
        CancelIntent(
            intent_id="c1",
            agent_id="mm-1",
            ts_ms=3,
            order_id="b1",
        )
    )
    clob.submit(_order("s1", "noise-1", Side.SELL, 0.49, 1.0, 4))

    fills = clob.clear(ts_ms=4)
    assert len(fills) == 1
    assert fills[0].buy_agent_id == "mm-2"
    assert fills[0].size == 1.0


def test_crossed_book_clears_until_uncrossed() -> None:
    clob = CLOBMechanism()
    clob.submit(_order("s1", "inf-1", Side.SELL, 0.40, 2.0, 1))
    clob.submit(_order("b1", "mm-1", Side.BUY, 0.60, 5.0, 2))
    clob.submit(_order("s2", "inf-2", Side.SELL, 0.55, 4.0, 3))

    fills = clob.clear(ts_ms=3)
    assert len(fills) == 2
    assert fills[0].size == 2.0
    assert fills[0].price == 0.40
    assert fills[1].size == 3.0
    assert fills[1].price == 0.60


def test_invalid_order_values_raise() -> None:
    clob = CLOBMechanism()
    try:
        clob.submit(_order("bad", "mm-1", Side.BUY, 1.5, 1.0, 0))
        assert False, "expected ValueError"
    except ValueError:
        pass

    try:
        clob.submit(_order("bad2", "mm-1", Side.BUY, 0.5, 0.0, 0))
        assert False, "expected ValueError"
    except ValueError:
        pass
