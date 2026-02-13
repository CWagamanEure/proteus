from __future__ import annotations

from proteus.agents.informed import InformedTraderAgent
from proteus.agents.market_maker import MarketMakerAgent
from proteus.agents.noise import NoiseTraderAgent
from proteus.core.events import Event, EventType, Side


def test_market_maker_quotes_and_inventory_skew() -> None:
    mm = MarketMakerAgent("mm-1", belief_init=0.5, max_inventory=10.0, base_size=2.0)
    mm.on_event(
        Event(
            event_id="n1",
            ts_ms=1,
            event_type=EventType.NEWS,
            payload={"signal": 0.6},
        )
    )

    intents_before = list(mm.generate_intents(ts_ms=2))
    assert len(intents_before) == 2

    bid_before = next(i for i in intents_before if i.side is Side.BUY)
    ask_before = next(i for i in intents_before if i.side is Side.SELL)
    assert 0.0 <= bid_before.price < ask_before.price <= 1.0

    mm.on_event(
        Event(
            event_id="f1",
            ts_ms=3,
            event_type=EventType.FILL,
            payload={
                "buy_agent_id": "mm-1",
                "sell_agent_id": "other",
                "size": 2.0,
                "price": ask_before.price,
            },
        )
    )

    intents_after = list(mm.generate_intents(ts_ms=4))
    bid_after = next(i for i in intents_after if i.side is Side.BUY)
    assert bid_after.price < bid_before.price


def test_informed_trader_threshold_and_size_scaling() -> None:
    inf = InformedTraderAgent(
        "inf-1",
        theta=0.02,
        fee_bps=0.0,
        latency_penalty=0.0,
        min_size=5.0,
        size_slope=20.0,
    )

    inf.on_event(
        Event(
            event_id="q1",
            ts_ms=1,
            event_type=EventType.QUOTE,
            payload={"best_bid": 0.45, "best_ask": 0.50},
        )
    )

    inf.on_event(
        Event(
            event_id="n1",
            ts_ms=2,
            event_type=EventType.NEWS,
            payload={"signal": 0.60},
        )
    )

    buy_intents = list(inf.generate_intents(ts_ms=3))
    assert len(buy_intents) == 1
    assert buy_intents[0].side is Side.BUY
    assert buy_intents[0].price == 0.50
    assert buy_intents[0].size >= 5.0

    inf.on_event(
        Event(
            event_id="n2",
            ts_ms=4,
            event_type=EventType.NEWS,
            payload={"signal": 0.505},
        )
    )
    assert list(inf.generate_intents(ts_ms=5)) == []


def test_noise_trader_poisson_arrivals_are_seed_deterministic() -> None:
    a = NoiseTraderAgent("noise-1", arrival_rate_per_second=8.0, seed=123)
    b = NoiseTraderAgent("noise-1", arrival_rate_per_second=8.0, seed=123)

    observed_a: list[tuple[str, float, float]] = []
    observed_b: list[tuple[str, float, float]] = []

    for ts in (100, 200, 500, 900):
        for intent in a.generate_intents(ts_ms=ts):
            observed_a.append((intent.side.value, round(intent.price, 4), round(intent.size, 4)))
        for intent in b.generate_intents(ts_ms=ts):
            observed_b.append((intent.side.value, round(intent.price, 4), round(intent.size, 4)))

    assert observed_a == observed_b

    for _, price, size in observed_a:
        assert 0.0 <= price <= 1.0
        assert 0.25 <= size <= 2.0
