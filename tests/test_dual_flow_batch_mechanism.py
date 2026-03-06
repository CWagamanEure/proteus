from __future__ import annotations

from proteus.core.events import CancelIntent, OrderIntent, Side
from proteus.mechanisms.dual_flow_batch import DualFlowBatchMechanism


def _order(
    intent_id: str,
    agent_id: str,
    side: Side,
    price: float,
    size: float,
    ts_ms: int,
) -> OrderIntent:
    return OrderIntent(
        intent_id=intent_id,
        agent_id=agent_id,
        ts_ms=ts_ms,
        side=side,
        price=price,
        size=size,
    )


def test_dual_flow_separate_buy_and_sell_clears() -> None:
    mech = DualFlowBatchMechanism(batch_interval_ms=10)

    mech.submit(_order("ms1", "mm-1", Side.SELL, 0.55, 2.0, 0))
    mech.submit(_order("mb1", "mm-2", Side.BUY, 0.45, 2.0, 0))
    mech.submit(_order("tb1", "noise-1", Side.BUY, 0.60, 1.0, 1))
    mech.submit(_order("ts1", "inf-1", Side.SELL, 0.40, 1.0, 1))

    fills = mech.clear(10)
    assert len(fills) == 2

    buy_flow = [f for f in fills if f.buy_agent_id == "noise-1"]
    sell_flow = [f for f in fills if f.sell_agent_id == "inf-1"]

    assert len(buy_flow) == 1
    assert buy_flow[0].sell_agent_id == "mm-1"
    assert buy_flow[0].price == 0.55

    assert len(sell_flow) == 1
    assert sell_flow[0].buy_agent_id == "mm-2"
    assert sell_flow[0].price == 0.45


def test_dual_flow_does_not_allow_maker_maker_matching() -> None:
    mech = DualFlowBatchMechanism(batch_interval_ms=10)

    mech.submit(_order("mb1", "mm-1", Side.BUY, 0.60, 1.0, 0))
    mech.submit(_order("ms1", "mm-2", Side.SELL, 0.40, 1.0, 0))

    fills = mech.clear(10)
    assert fills == []


def test_dual_flow_cancel_prevents_fill() -> None:
    mech = DualFlowBatchMechanism(batch_interval_ms=10)

    mech.submit(_order("ms1", "mm-1", Side.SELL, 0.55, 1.0, 0))
    mech.submit(_order("tb1", "noise-1", Side.BUY, 0.60, 1.0, 1))
    mech.cancel(
        CancelIntent(
            intent_id="c1",
            agent_id="mm-1",
            ts_ms=2,
            order_id="ms1",
        )
    )

    fills = mech.clear(10)
    assert fills == []
