from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from proteus.core.events import Fill


@dataclass
class AgentAccount:
    """
    Per-agent cash and inventory state
    """

    cash: float = 0.0
    inventory: float = 0.0

    def equity(self, mark_price: float) -> float:
        """
        Mark-to-market equity at the provided contract price
        """
        return self.cash + (self.inventory * mark_price)


@dataclass
class InvariantViolation:
    """
    A single invariant breach tied to the source event/fill id
    """

    event_id: str
    code: str
    message: str


@dataclass
class AccountingSnapshot:
    """
    Immutable-ish view of the current ledger state
    """

    accounts: dict[str, AgentAccount]
    total_cash: float
    total_inventory: float
    violations: list[InvariantViolation]
    processed_fills: int


class AccountingEngine:
    """
    Replay fills into agent accounts and enforce accounting invariants
    """

    def __init__(self, *, tolerance: float = 1e-9) -> None:
        self._accounts: dict[str, AgentAccount] = {}
        self._violations: list[InvariantViolation] = []
        self._processed_fills = 0
        self._last_fill_id: str | None = None
        self._tol = tolerance

    def reset(self) -> None:
        """
        Clear all state
        """
        self._accounts.clear()
        self._violations.clear()
        self._processed_fills = 0
        self._last_fill_id = None

    def process_fill(self, fill: Fill) -> None:
        """
        Apply one fill and evaluate per-fill invariants.
        """

        self._last_fill_id = fill.fill_id
        if not self._validate_fill(fill):
            return

        buyer = self._accounts.setdefault(fill.buy_agent_id, AgentAccount())
        seller = self._accounts.setdefault(fill.sell_agent_id, AgentAccount())

        prior_total_cash = self._total_cash()
        prior_total_inventory = self._total_inventory()

        notional = fill.price * fill.size
        buyer_cash_delta = -notional
        seller_cash_delta = notional
        buyer_inventory_delta = fill.size
        seller_inventory_delta = -fill.size

        buyer.cash += buyer_cash_delta
        seller.cash += seller_cash_delta
        buyer.inventory += buyer_inventory_delta
        seller.inventory += seller_inventory_delta
        self._processed_fills += 1

        self._check_zero_sum_transfer(fill.fill_id, buyer_cash_delta, seller_cash_delta, "cash")
        self._check_zero_sum_transfer(
            fill.fill_id, buyer_inventory_delta, seller_inventory_delta, "inventory"
        )
        self._check_conservation(fill.fill_id, prior_total_cash, self._total_cash(), "cash")
        self._check_conservation(
            fill.fill_id, prior_total_inventory, self._total_inventory(), "inventory"
        )

    def process_fills(self, fills: list[Fill]) -> AccountingSnapshot:
        """
        Apply many fills in-order
        """
        for fill in fills:
            self.process_fill(fill)
        return self.snapshot()

    def mark_to_market(self, mark_price: float) -> dict[str, float]:
        """
        Returns equity per agent
        """
        if not isfinite(mark_price):
            raise ValueError("mark_price must be finite")
        return {
            agent_id: account.equity(mark_price) for agent_id, account in self._accounts.items()
        }

    def settlement_pnl(self, outcome: float) -> dict[str, float]:
        """
        Compute settlement_pnl for a binary payoff outcome [0, 1].
        """

        if not isfinite(outcome) or outcome < 0.0 or outcome > 1.0:
            raise ValueError("outcome must be finite and in [0,1]")
        pnl = self.mark_to_market(outcome)
        total = sum(pnl.values())
        if abs(total) > self._tol:
            self._violations.append(
                InvariantViolation(
                    event_id=self._last_fill_id or "no-fills",
                    code="pnl_non_zero_sum",
                    message=f"settlement pnl sum drifted by {total}",
                )
            )
        return pnl

    def snapshot(self) -> AccountingSnapshot:
        """
        Return a structured snapshot of ledger state and violations
        """

        accounts_copy = {
            agent_id: AgentAccount(cash=account.cash, inventory=account.inventory)
            for agent_id, account in self._accounts.items()
        }

        violations_copy = list(self._violations)
        return AccountingSnapshot(
            accounts=accounts_copy,
            total_cash=self._total_cash(),
            total_inventory=self._total_inventory(),
            violations=violations_copy,
            processed_fills=self._processed_fills,
        )

    def _validate_fill(self, fill: Fill) -> bool:
        if not isfinite(fill.price) or fill.price < 0.0 or fill.price > 1.0:
            self._violations.append(
                InvariantViolation(
                    event_id=fill.fill_id,
                    code="invalid_fill_price",
                    message=f"fill price must be within [0,1], got {fill.price}",
                )
            )
            return False

        if not isfinite(fill.size) or fill.size <= 0.0:
            self._violations.append(
                InvariantViolation(
                    event_id=fill.fill_id,
                    code="invalid_fill_size",
                    message=f"fill size must be > 0, got {fill.size}",
                )
            )
            return False

        return True

    def _check_zero_sum_transfer(
        self,
        event_id: str,
        first_leg: float,
        second_leg: float,
        quantity_name: str,
    ) -> None:
        drift = first_leg + second_leg
        if abs(drift) > self._tol:
            self._violations.append(
                InvariantViolation(
                    event_id=event_id,
                    code=f"{quantity_name}_transfer_not_zero_sum",
                    message=f"{quantity_name} transfer drifted by {drift}",
                )
            )

    def _check_conservation(
        self, event_id: str, before: float, after: float, quantity_name: str
    ) -> None:
        drift = after - before
        if abs(drift) > self._tol:
            self._violations.append(
                InvariantViolation(
                    event_id=event_id,
                    code=f"{quantity_name}_conservation_violation",
                    message=f"total {quantity_name} drifted by {drift}",
                )
            )

    def _total_cash(self) -> float:
        return sum(account.cash for account in self._accounts.values())

    def _total_inventory(self) -> float:
        return sum(account.inventory for account in self._accounts.values())
