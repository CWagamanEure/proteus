from __future__ import annotations

from proteus.core.events import CancelIntent, OrderIntent, Side
from proteus.mechanisms.fba import FBAMechanism


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


def test_fba_waits_for_batch_boundary_then_clears() -> None:
    fba = FBAMechanism(batch_interval_ms=100)
    fba.submit(_order("b1", "mm-1", Side.BUY, 0.60, 2.0, 10))
    fba.submit(_order("s1", "inf-1", Side.SELL, 0.55, 2.0, 20))

    assert fba.clear(ts_ms=99) == []

    fills = fba.clear(ts_ms=100)
    assert len(fills) == 1
    assert fills[0].ts_ms == 100
    assert fills[0].size == 2.0


def test_uniform_clearing_price_tie_policy_lower_vs_upper() -> None:
    lower = FBAMechanism(batch_interval_ms=100, price_tie_policy="lower")
    upper = FBAMechanism(batch_interval_ms=100, price_tie_policy="upper")

    for mechanism in (lower, upper):
        mechanism.submit(_order("b1", "mm-1", Side.BUY, 0.70, 5.0, 1))
        mechanism.submit(_order("b2", "mm-2", Side.BUY, 0.60, 5.0, 2))
        mechanism.submit(_order("s1", "inf-1", Side.SELL, 0.40, 4.0, 3))
        mechanism.submit(_order("s2", "inf-2", Side.SELL, 0.55, 6.0, 4))

    lower_fills = lower.clear(ts_ms=100)
    upper_fills = upper.clear(ts_ms=100)

    assert lower_fills
    assert upper_fills
    assert all(fill.price == 0.55 for fill in lower_fills)
    assert all(fill.price == 0.60 for fill in upper_fills)
    assert sum(fill.size for fill in lower_fills) == 10.0
    assert sum(fill.size for fill in upper_fills) == 10.0


def test_time_priority_allocation_rations_by_arrival() -> None:
    fba = FBAMechanism(batch_interval_ms=100, allocation_policy="time_priority")
    fba.submit(_order("b1", "mm-1", Side.BUY, 0.60, 5.0, 1))
    fba.submit(_order("b2", "mm-2", Side.BUY, 0.60, 5.0, 2))
    fba.submit(_order("s1", "noise-1", Side.SELL, 0.50, 5.0, 3))

    fills = fba.clear(ts_ms=100)
    assert len(fills) == 1
    assert fills[0].buy_agent_id == "mm-1"
    assert fills[0].size == 5.0


def test_pro_rata_allocation_splits_scarce_side() -> None:
    fba = FBAMechanism(batch_interval_ms=100, allocation_policy="pro_rata")
    fba.submit(_order("b1", "mm-1", Side.BUY, 0.60, 5.0, 1))
    fba.submit(_order("b2", "mm-2", Side.BUY, 0.60, 5.0, 2))
    fba.submit(_order("s1", "noise-1", Side.SELL, 0.50, 5.0, 3))

    fills = fba.clear(ts_ms=100)
    assert len(fills) == 2
    assert {fills[0].buy_agent_id, fills[1].buy_agent_id} == {"mm-1", "mm-2"}
    assert sum(fill.size for fill in fills) == 5.0

    by_buyer = {fill.buy_agent_id: fill.size for fill in fills}
    assert by_buyer["mm-1"] == 2.5
    assert by_buyer["mm-2"] == 2.5


def test_cancel_prevents_participation_in_batch() -> None:
    fba = FBAMechanism(batch_interval_ms=100)
    fba.submit(_order("b1", "mm-1", Side.BUY, 0.60, 2.0, 1))
    fba.submit(_order("s1", "inf-1", Side.SELL, 0.50, 2.0, 2))
    fba.cancel(
        CancelIntent(
            intent_id="c1",
            agent_id="mm-1",
            ts_ms=50,
            order_id="b1",
        )
    )

    fills = fba.clear(ts_ms=100)
    assert fills == []


def test_invalid_order_values_raise() -> None:
    fba = FBAMechanism()

    try:
        fba.submit(_order("bad", "mm-1", Side.BUY, 1.1, 1.0, 0))
        assert False, "expected ValueError"
    except ValueError:
        pass

    try:
        fba.submit(_order("bad2", "mm-1", Side.BUY, 0.5, 0.0, 0))
        assert False, "expected ValueError"
    except ValueError:
        pass
