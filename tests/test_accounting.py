from __future__ import annotations

from proteus.core.accounting import AccountingEngine
from proteus.core.events import Fill


def test_accounting_reconciles_cash_inventory_and_pnl() -> None:
    engine = AccountingEngine()
    fills = [
        Fill(
            fill_id="f-1",
            ts_ms=1,
            buy_agent_id="a",
            sell_agent_id="b",
            price=0.4,
            size=10.0,
        ),
        Fill(
            fill_id="f-2",
            ts_ms=2,
            buy_agent_id="b",
            sell_agent_id="c",
            price=0.6,
            size=5.0,
        ),
    ]
    snapshot = engine.process_fills(fills)

    assert snapshot.accounts["a"].cash == -4.0
    assert snapshot.accounts["a"].inventory == 10.0
    assert snapshot.accounts["b"].cash == 1.0
    assert snapshot.accounts["b"].inventory == -5.0
    assert snapshot.accounts["c"].cash == 3.0
    assert snapshot.accounts["c"].inventory == -5.0

    assert snapshot.total_cash == 0.0
    assert snapshot.total_inventory == 0.0
    assert snapshot.processed_fills == 2
    assert snapshot.violations == []

    mtm = engine.mark_to_market(mark_price=0.5)
    assert mtm["a"] == 1.0
    assert mtm["b"] == -1.5
    assert mtm["c"] == 0.5
    assert sum(mtm.values()) == 0.0

    settled = engine.settlement_pnl(outcome=1.0)
    assert settled["a"] == 6.0
    assert settled["b"] == -4.0
    assert settled["c"] == -2.0
    assert sum(settled.values()) == 0.0
    assert engine.snapshot().violations == []


def test_accounting_reports_fill_id_for_invalid_size() -> None:
    engine = AccountingEngine()
    engine.process_fill(
        Fill(
            fill_id="bad-size",
            ts_ms=1,
            buy_agent_id="a",
            sell_agent_id="b",
            price=0.5,
            size=0.0,
        )
    )

    snapshot = engine.snapshot()
    assert len(snapshot.violations) == 1
    violation = snapshot.violations[0]
    assert violation.event_id == "bad-size"
    assert violation.code == "invalid_fill_size"
