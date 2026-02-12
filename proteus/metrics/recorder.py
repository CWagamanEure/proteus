"""Metric recorder and event sink."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from math import isfinite, nan, sqrt
from pathlib import Path
from statistics import mean, pstdev, pvariance
from typing import Any

from proteus.core.accounting import AccountingEngine
from proteus.core.events import Event, EventType, Fill

SCHEMA_VERSION = "1.0.0"

NON_NEGOTIABLE_METRICS: tuple[str, ...] = (
    "mm_pnl",
    "mm_sharpe",
    "mm_max_drawdown",
    "mm_inventory_variance",
    "mm_adverse_selection_loss",
    "trader_execution_error_rmse",
    "trader_slippage_bps",
    "trader_fill_probability",
    "trader_time_to_execution_ms",
    "market_price_rmse",
    "market_spread_mean",
    "market_depth_mean",
    "market_realized_volatility",
    "market_shock_resilience_half_life_ms",
)


@dataclass(frozen=True)
class RunArtifactBundle:
    """
    per-run artifact payload
    """

    schema_version: str
    scenario_id: str
    seed: int
    mechanism: str
    created_at_utc: str
    event_log: list[dict[str, Any]]
    fills: list[dict[str, Any]]
    metrics: dict[str, float]
    summary_table: list[dict[str, float]]


@dataclass
class Recorder:
    """Mechanism-agnostic event recorder."""

    events: list[Event] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)

    def record(self, event: Event) -> None:
        self.events.append(event)

    def record_fill(self, fill: Fill) -> None:
        self.fills.append(fill)

    def clear(self) -> None:
        self.events.clear()
        self.fills.clear()

    def build_bundle(
        self,
        *,
        scenario_id: str,
        seed: int,
        mechanism: str,
        mark_price: float = 0.5,
        adverse_selection_delta_ms: int = 1,
    ) -> RunArtifactBundle:
        event_log = [self._serialize_event(event) for event in self.events]
        fill_log = [self._serialize_fill(fill) for fill in self.fills]
        metrics = self._compute_metrics(
            mark_price=mark_price,
            adverse_selection_delta_ms=adverse_selection_delta_ms,
        )
        summary = [{"metric": key, "value": metrics[key]} for key in sorted(metrics)]

        return RunArtifactBundle(
            schema_version=SCHEMA_VERSION,
            scenario_id=scenario_id,
            seed=seed,
            mechanism=mechanism,
            created_at_utc=datetime.now(tz=UTC).isoformat(),
            event_log=event_log,
            fills=fill_log,
            metrics=metrics,
            summary_table=summary,
        )

    def write_bundle(
        self,
        bundle: RunArtifactBundle,
        *,
        output_dir: str | Path,
        run_id: str | None = None,
        write_parquet: bool = False,
    ) -> dict[str, Path]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        resolved_run_id = run_id or f"{bundle.scenario_id}_seed{bundle.seed}_{bundle.mechanism}"
        bundle_path = out_dir / f"{resolved_run_id}_bundle.json"
        metrics_path = out_dir / f"{resolved_run_id}_metrics.json"
        summary_path = out_dir / f"{resolved_run_id}_summary.csv"
        events_path = out_dir / f"{resolved_run_id}_events.jsonl"
        fills_path = out_dir / f"{resolved_run_id}_fills.jsonl"

        bundle_path.write_text(
            json.dumps(asdict(bundle), indent=2, sort_keys=True), encoding="utf-8"
        )
        metrics_path.write_text(
            json.dumps(bundle.metrics, indent=2, sort_keys=True), encoding="utf-8"
        )
        self._write_summary_csv(summary_path, bundle.summary_table)
        self._write_jsonl(events_path, bundle.event_log)
        self._write_jsonl(fills_path, bundle.fills)

        output_map: dict[str, Path] = {
            "bundle_json": bundle_path,
            "metrics_json": metrics_path,
            "summary_csv": summary_path,
            "events_jsonl": events_path,
            "fills_jsonl": fills_path,
        }

        if write_parquet:
            output_map.update(self._write_parquet(out_dir, resolved_run_id, bundle))

        return output_map

    def _compute_metrics(
        self,
        *,
        mark_price: float,
        adverse_selection_delta_ms: int,
    ) -> dict[str, float]:

        metrics = {name: nan for name in NON_NEGOTIABLE_METRICS}
        if not isfinite(mark_price):
            raise ValueError("mark_price must be finite")

        fills_sorted = sorted(self.fills, key=lambda fill: fill.ts_ms)
        events_sorted = sorted(
            self.events, key=lambda event: (event.ts_ms, event.seq_no, event.event_id)
        )

        prices = [fill.price for fill in fills_sorted]
        if prices:
            diffs_to_mark = [price - mark_price for price in prices]
            metrics["trader_execution_error_rmse"] = sqrt(
                mean(delta * delta for delta in diffs_to_mark)
            )
            metrics["trader_slippage_bps"] = mean(abs(delta) for delta in diffs_to_mark) * 10_000.0

        order_events = [event for event in events_sorted if event.event_type is EventType.ORDER]
        if order_events:
            metrics["trader_fill_probability"] = min(1.0, len(fills_sorted) / len(order_events))

        metrics["trader_time_to_execution_ms"] = self._mean_time_to_execution_ms(
            order_events, fills_sorted
        )

        quote_events = [event for event in events_sorted if event.event_type is EventType.QUOTE]
        metrics["market_spread_mean"] = self._mean_spread(quote_events)
        metrics["market_depth_mean"] = self._mean_depth(quote_events)
        metrics["market_realized_volatility"] = self._realized_volatility(prices)
        metrics["market_price_rmse"] = self._market_rmse(events_sorted, fills_sorted, mark_price)
        metrics["market_shock_resilience_half_life_ms"] = nan
        mm_metrics = self._compute_mm_metrics(
            fills_sorted=fills_sorted,
            mark_price=mark_price,
            adverse_selection_delta_ms=adverse_selection_delta_ms,
        )
        metrics.update(mm_metrics)

        return metrics

    def _compute_mm_metrics(
        self,
        *,
        fills_sorted: list[Fill],
        mark_price: float,
        adverse_selection_delta_ms: int,
    ) -> dict[str, float]:
        out = {
            "mm_pnl": nan,
            "mm_sharpe": nan,
            "mm_max_drawdown": nan,
            "mm_inventory_variance": nan,
            "mm_adverse_selection_loss": nan,
        }

        if not fills_sorted:
            return out

        engine = AccountingEngine()
        for fill in fills_sorted:
            engine.process_fill(fill)

        snapshot = engine.snapshot()
        mm_ids = sorted(agent_id for agent_id in snapshot.accounts if _is_mm_agent(agent_id))
        if not mm_ids:
            return out

        settled = engine.settlement_pnl(outcome=mark_price)
        mm_pnls = [settled[agent_id] for agent_id in mm_ids]
        out["mm_pnl"] = mean(mm_pnls)

        inventories = [snapshot.accounts[agent_id].inventory for agent_id in mm_ids]
        out["mm_inventory_variance"] = pvariance(inventories) if len(inventories) > 1 else 0.0

        equity_curve = self._mm_equity_curve(
            fills_sorted=fills_sorted, mm_ids=mm_ids, mark_price=mark_price
        )

        if len(equity_curve) >= 2:
            returns = [
                equity_curve[idx] - equity_curve[idx - 1] for idx in range(1, len(equity_curve))
            ]

            sigma = pstdev(returns) if len(returns) > 1 else 0.0
            out["mm_sharpe"] = (mean(returns) / sigma) if sigma > 0.0 else 0.0
            out["mm_max_drawdown"] = _max_drawdown(equity_curve)
        else:
            out["mm_sharpe"] = 0.0
            out["mm_max_drawdown"] = 0.0

        out["mm_adverse_selection_loss"] = self._adverse_selection_loss(
            fills_sorted=fills_sorted,
            adverse_selection_delta_ms=adverse_selection_delta_ms,
        )
        return out

    def _adverse_selection_loss(
        self,
        *,
        fills_sorted: list[Fill],
        adverse_selection_delta_ms: int,
    ) -> float:
        if not fills_sorted:
            return nan

        as_loss = 0.0
        ts_prices = [(fill.ts_ms, fill.price) for fill in fills_sorted]

        for fill in fills_sorted:
            q = 0.0
            if _is_mm_agent(fill.buy_agent_id):
                q += fill.size
            if _is_mm_agent(fill.sell_agent_id):
                q -= fill.size
            if q == 0.0:
                continue

            future_ts = fill.ts_ms + adverse_selection_delta_ms
            p_future = _latest_price_at_or_after(ts_prices, future_ts, fallback=fill.price)
            as_loss += q * (p_future - fill.price)

        return as_loss

    def _mm_equity_curve(
        self,
        *,
        fills_sorted: list[Fill],
        mm_ids: list[str],
        mark_price: float,
    ) -> list[float]:
        engine = AccountingEngine()
        curve: list[float] = []
        for fill in fills_sorted:
            engine.process_fill(fill)
            mtm = engine.mark_to_market(mark_price)
            curve.append(sum(mtm.get(agent_id, 0.0) for agent_id in mm_ids))
        return curve

    def _mean_time_to_execution_ms(
        self,
        order_events: list[Event],
        fills_sorted: list[Fill],
    ) -> float:
        first_order_ts: dict[str, int] = {}
        for event in order_events:
            agent_id = _extract_agent_id(event)
            if agent_id is not None and agent_id not in first_order_ts:
                first_order_ts[agent_id] = event.ts_ms

        first_fill_ts: dict[str, int] = {}
        for fill in fills_sorted:
            for agent_id in (fill.buy_agent_id, fill.sell_agent_id):
                if not _is_mm_agent(agent_id) and agent_id not in first_fill_ts:
                    first_fill_ts[agent_id] = fill.ts_ms

        delays = [
            first_fill_ts[agent_id] - first_order_ts[agent_id]
            for agent_id in first_fill_ts
            if agent_id in first_order_ts and first_fill_ts[agent_id] >= first_order_ts[agent_id]
        ]
        if not delays:
            return nan
        return mean(delays)

    def _market_rmse(
        self,
        events_sorted: list[Event],
        fills_sorted: list[Fill],
        mark_price: float,
    ) -> float:
        if not fills_sorted:
            return nan

        truth_series: list[tuple[int, float]] = []
        for event in events_sorted:
            if event.event_type is EventType.NEWS:
                raw = event.payload.get("p_t")
                if isinstance(raw, (int, float)):
                    truth_series.append((event.ts_ms, float(raw)))

        errors: list[float] = []
        for fill in fills_sorted:
            truth = _latest_truth_at_or_before(truth_series, fill.ts_ms, fallback=mark_price)
            errors.append((fill.price - truth) ** 2)

        return sqrt(mean(errors)) if errors else nan

    def _mean_spread(self, quote_events: list[Event]) -> float:
        spreads: list[float] = []
        for event in quote_events:
            bid = event.payload.get("bid")
            ask = event.payload.get("ask")
            if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and ask >= bid:
                spreads.append(float(ask) - float(bid))

        if not spreads:
            return nan
        return mean(spreads)

    def _mean_depth(self, quote_events: list[Event]) -> float:
        depths: list[float] = []
        for event in quote_events:
            bid_size = event.payload.get("bid_size")
            ask_size = event.payload.get("ask_size")
            if isinstance(bid_size, (int, float)) and isinstance(ask_size, (int, float)):
                depths.append(float(bid_size) + float(ask_size))
        if not depths:
            return nan
        return mean(depths)

    def _realized_volatility(self, prices: list[float]) -> float:
        if len(prices) < 2:
            return nan
        returns = [prices[idx] - prices[idx - 1] for idx in range(1, len(prices))]
        if len(returns) == 1:
            return abs(returns[0])
        return pstdev(returns)

    def _serialize_event(self, event: Event) -> dict[str, Any]:
        return {
            "event_id": event.event_id,
            "ts_ms": event.ts_ms,
            "event_type": event.event_type.value,
            "seq_no": event.seq_no,
            "payload": event.payload,
        }

    def _serialize_fill(self, fill: Fill) -> dict[str, Any]:
        return {
            "fill_id": fill.fill_id,
            "ts_ms": fill.ts_ms,
            "buy_agent_id": fill.buy_agent_id,
            "sell_agent_id": fill.sell_agent_id,
            "price": fill.price,
            "size": fill.size,
        }

    def _write_summary_csv(self, path: Path, rows: list[dict[str, float]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
            writer.writeheader()
            writer.writerows(rows)

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True))
                handle.write("\n")

    def _write_parquet(
        self,
        out_dir: Path,
        run_id: str,
        bundle: RunArtifactBundle,
    ) -> dict[str, Path]:
        try:
            import pandas as pd
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("Parquet export requires pandas + pyarrow or fastparquet") from exc

        events_path = out_dir / f"{run_id}_events.parquet"
        fills_path = out_dir / f"{run_id}_fills.parquet"
        pd.DataFrame(bundle.event_log).to_parquet(events_path, index=False)
        pd.DataFrame(bundle.fills).to_parquet(fills_path, index=False)

        return {"events_parquet": events_path, "fills_parquet": fills_path}


def _is_mm_agent(agent_id: str) -> bool:
    return agent_id.startswith("mm")


def _extract_agent_id(event: Event) -> str | None:
    direct = event.payload.get("agent_id")
    if isinstance(direct, str):
        return direct

    intent = event.payload.get("intent")
    if isinstance(intent, dict):
        nested = intent.get("agent_id")
        if isinstance(nested, str):
            return nested

    return None


def _latest_truth_at_or_before(
    truth_series: list[tuple[int, float]],
    ts_ms: int,
    fallback: float,
) -> float:
    if not truth_series:
        return fallback

    candidate = truth_series[0][1]
    for truth_ts, truth_val in truth_series:
        if truth_ts > ts_ms:
            break
        candidate = truth_val
    return candidate


def _latest_price_at_or_after(
    ts_prices: list[tuple[int, float]],
    ts_ms: int,
    fallback: float,
) -> float:
    for price_ts, price in ts_prices:
        if price_ts >= ts_ms:
            return price
    return fallback


def _max_drawdown(curve: list[float]) -> float:
    if not curve:
        return nan
    peak = curve[0]
    max_dd = 0.0
    for value in curve:
        if value > peak:
            peak = value
        dd = peak - value
        if dd > max_dd:
            max_dd = dd
    return max_dd
