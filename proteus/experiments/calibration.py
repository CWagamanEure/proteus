"""CLOB calibration harness."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from random import Random
from statistics import mean

from proteus.agents.informed import InformedTraderAgent
from proteus.agents.market_maker import MarketMakerAgent
from proteus.agents.noise import NoiseTraderAgent
from proteus.core.accounting import AccountingEngine
from proteus.core.events import Event, EventType, Fill, OrderIntent, Side
from proteus.core.rng import RNGManager
from proteus.execution.latency import ConfigurableLatencyModel, LatencyProfile
from proteus.info.latent_process import BoundedLogOddsLatentProcess
from proteus.info.signal_model import AgentSignalConfig, HeterogeneousSignalModel
from proteus.mechanisms.clob import CLOBMechanism
from proteus.metrics.recorder import Recorder


@dataclass(frozen=True)
class SurvivalCriteria:
    min_mm_pnl: float = 0.0
    max_abs_inventory: float = 10.0
    max_drawdown: float = 5.0


@dataclass(frozen=True)
class CalibrationSearchConfig:
    seeds: tuple[int, ...] = (7, 11, 17)
    duration_ms: int = 20_000
    step_ms: int = 100

    # Search knobs under low informed activity and low latency.
    mm_h0_grid: tuple[float, ...] = (0.008, 0.012, 0.016, 0.02)
    mm_kappa_grid: tuple[float, ...] = (0.004, 0.008, 0.012)
    mm_min_half_spread_grid: tuple[float, ...] = (0.002, 0.003, 0.004)

    baseline_informed_activity_prob: float = 0.06
    baseline_submission_latency_ms: int = 1

    # Sensitivity diagnostics required by PT-010.
    informed_activity_grid: tuple[float, ...] = (0.03, 0.06, 0.12, 0.2)
    latency_submission_grid_ms: tuple[int, ...] = (1, 3, 7, 15)

    criteria: SurvivalCriteria = field(default_factory=SurvivalCriteria)


@dataclass(frozen=True)
class CandidateRegime:
    h0: float
    kappa_inventory: float
    min_half_spread: float


@dataclass(frozen=True)
class RunMetrics:
    mm_pnl: float
    mm_max_drawdown: float
    mm_adverse_selection_loss: float
    mm_abs_inventory: float
    market_spread_mean: float
    stable: bool


@dataclass(frozen=True)
class CalibrationReport:
    selected_regime: CandidateRegime
    baseline_summary: dict[str, float]
    baseline_rationale: str
    sensitivity_rows: list[dict[str, float]]
    stable_candidates_found: int
    report_path: str | None = None


def run_clob_calibration(
    config: CalibrationSearchConfig,
    *,
    out_dir: str | Path | None = None,
    report_name: str = "clob_calibration_report.json",
) -> CalibrationReport:
    candidates = [
        CandidateRegime(h0=h0, kappa_inventory=kappa, min_half_spread=min_half_spread)
        for h0 in config.mm_h0_grid
        for kappa in config.mm_kappa_grid
        for min_half_spread in config.mm_min_half_spread_grid
    ]

    scored: list[tuple[float, CandidateRegime, list[RunMetrics]]] = []
    stable_count = 0

    for regime in candidates:
        runs = [
            _simulate_one(
                seed=seed,
                duration_ms=config.duration_ms,
                step_ms=config.step_ms,
                regime=regime,
                informed_activity_prob=config.baseline_informed_activity_prob,
                submission_latency_ms=config.baseline_submission_latency_ms,
                criteria=config.criteria,
            )
            for seed in config.seeds
        ]
        if all(row.stable for row in runs):
            stable_count += 1

        # Risk-adjusted baseline score used to select one candidate.
        score = (
            mean(row.mm_pnl for row in runs)
            - mean(row.mm_max_drawdown for row in runs)
            - (0.5 * mean(abs(row.mm_adverse_selection_loss) for row in runs))
        )
        scored.append((score, regime, runs))

    stable_scored = [item for item in scored if all(row.stable for row in item[2])]
    _, selected_regime, selected_runs = max(stable_scored or scored, key=lambda x: x[0])

    baseline_summary = {
        "mm_pnl_mean": mean(row.mm_pnl for row in selected_runs),
        "mm_drawdown_mean": mean(row.mm_max_drawdown for row in selected_runs),
        "mm_abs_inventory_mean": mean(row.mm_abs_inventory for row in selected_runs),
        "market_spread_mean": mean(row.market_spread_mean for row in selected_runs),
        "mm_as_loss_mean": mean(row.mm_adverse_selection_loss for row in selected_runs),
    }
    rationale = (
        "Selected regime maximizes baseline risk-adjusted MM performance "
        "(pnl - drawdown - 0.5*|adverse_selection_loss|) under low informed activity."
    )

    sensitivity_rows: list[dict[str, float]] = []
    for informed_prob in config.informed_activity_grid:
        for submission_latency_ms in config.latency_submission_grid_ms:
            runs = [
                _simulate_one(
                    seed=seed,
                    duration_ms=config.duration_ms,
                    step_ms=config.step_ms,
                    regime=selected_regime,
                    informed_activity_prob=informed_prob,
                    submission_latency_ms=submission_latency_ms,
                    criteria=config.criteria,
                )
                for seed in config.seeds
            ]
            sensitivity_rows.append(
                {
                    "informed_activity_prob": informed_prob,
                    "submission_latency_ms": float(submission_latency_ms),
                    "mm_pnl_mean": mean(row.mm_pnl for row in runs),
                    "mm_drawdown_mean": mean(row.mm_max_drawdown for row in runs),
                    "mm_as_loss_mean": mean(row.mm_adverse_selection_loss for row in runs),
                    "stable_rate": mean(1.0 if row.stable else 0.0 for row in runs),
                }
            )

    report = CalibrationReport(
        selected_regime=selected_regime,
        baseline_summary=baseline_summary,
        baseline_rationale=rationale,
        sensitivity_rows=sensitivity_rows,
        stable_candidates_found=stable_count,
    )

    if out_dir is None:
        return report

    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / report_name
    report_payload = asdict(report)
    report_payload["selected_regime"] = asdict(report.selected_regime)
    report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")

    return CalibrationReport(
        selected_regime=report.selected_regime,
        baseline_summary=report.baseline_summary,
        baseline_rationale=report.baseline_rationale,
        sensitivity_rows=report.sensitivity_rows,
        stable_candidates_found=report.stable_candidates_found,
        report_path=str(report_path),
    )


def _simulate_one(
    *,
    seed: int,
    duration_ms: int,
    step_ms: int,
    regime: CandidateRegime,
    informed_activity_prob: float,
    submission_latency_ms: int,
    criteria: SurvivalCriteria,
) -> RunMetrics:
    rng = RNGManager(seed)

    mechanism = CLOBMechanism()
    latency_profile = LatencyProfile(
        submission_ms=submission_latency_ms,
        ack_ms=1,
        fill_ms=1,
        jitter_ms=0,
    )
    latency = ConfigurableLatencyModel(
        default=latency_profile,
        per_mechanism={"clob": latency_profile},
        seed=rng.child_seed("latency"),
    )

    latent = BoundedLogOddsLatentProcess(p0=0.5, phi=0.995, sigma_eta=0.2)
    latent.reset(rng.child_seed("latent"))

    signal_model = HeterogeneousSignalModel(
        default=AgentSignalConfig(delay_ms=0, noise_stddev=0.01),
        per_agent={
            "mm-1": AgentSignalConfig(delay_ms=0, noise_stddev=0.01),
            "inf-1": AgentSignalConfig(delay_ms=10, noise_stddev=0.015),
            "noise-1": AgentSignalConfig(delay_ms=5, noise_stddev=0.02),
        },
    )
    signal_model.reset(rng.child_seed("signals"))

    mm = MarketMakerAgent(
        "mm-1",
        h0=regime.h0,
        kappa_inventory=regime.kappa_inventory,
        min_half_spread=regime.min_half_spread,
        base_size=1.0,
        max_inventory=20.0,
    )
    inf = InformedTraderAgent("inf-1", theta=0.01, min_size=0.5, max_size=2.0)
    noise = NoiseTraderAgent("noise-1", arrival_rate_per_second=1.8, seed=rng.child_seed("noise"))

    agents = [mm, inf, noise]
    decision_rng = Random(rng.child_seed("decision"))
    recorder = Recorder()

    pending_orders: dict[int, list[OrderIntent]] = defaultdict(list)
    pending_fills: dict[int, list[Fill]] = defaultdict(list)

    best_bid = 0.49
    best_ask = 0.51
    quote_size = 1.0
    last_truth = 0.5
    event_seq = 0

    ts = 0
    while ts <= duration_ms or pending_orders or pending_fills:
        for fill in pending_fills.pop(ts, []):
            recorder.record_fill(fill)
            event_seq += 1
            fill_event = Event(
                event_id=f"fill-{event_seq}",
                ts_ms=ts,
                event_type=EventType.FILL,
                payload={
                    "fill_id": fill.fill_id,
                    "buy_agent_id": fill.buy_agent_id,
                    "sell_agent_id": fill.sell_agent_id,
                    "price": fill.price,
                    "size": fill.size,
                },
            )
            recorder.record(fill_event)
            for agent in agents:
                agent.on_event(fill_event)

        for intent in pending_orders.pop(ts, []):
            mechanism.submit(intent)
            event_seq += 1
            recorder.record(
                Event(
                    event_id=f"order-{event_seq}",
                    ts_ms=ts,
                    event_type=EventType.ORDER,
                    payload={
                        "agent_id": intent.agent_id,
                        "side": intent.side.value,
                        "price": intent.price,
                        "size": intent.size,
                    },
                )
            )

        for fill in mechanism.clear(ts):
            fill_due = _align_to_step(ts + latency.fill_delay_ms("clob"), step_ms)
            pending_fills[fill_due].append(fill)

        if ts <= duration_ms:
            last_truth = latent.step(step_ms)
            event_seq += 1
            recorder.record(
                Event(
                    event_id=f"news-{event_seq}",
                    ts_ms=ts,
                    event_type=EventType.NEWS,
                    payload={"p_t": last_truth},
                )
            )

            for agent in agents:
                observed_signal = signal_model.observe(agent.agent_id, ts, last_truth)
                agent.on_event(
                    Event(
                        event_id=f"news-private-{agent.agent_id}-{event_seq}",
                        ts_ms=ts,
                        event_type=EventType.NEWS,
                        payload={"signal": observed_signal, "p_t": observed_signal},
                    )
                )

            event_seq += 1
            quote_event = Event(
                event_id=f"quote-{event_seq}",
                ts_ms=ts,
                event_type=EventType.QUOTE,
                payload={
                    "bid": best_bid,
                    "ask": best_ask,
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "bid_size": quote_size,
                    "ask_size": quote_size,
                },
            )
            recorder.record(quote_event)
            for agent in agents:
                agent.on_event(quote_event)

            mm_intents = list(mm.generate_intents(ts))
            bid_quotes = [intent for intent in mm_intents if intent.side is Side.BUY]
            ask_quotes = [intent for intent in mm_intents if intent.side is Side.SELL]
            if bid_quotes:
                best_bid = max(intent.price for intent in bid_quotes)
            if ask_quotes:
                best_ask = min(intent.price for intent in ask_quotes)
            if mm_intents:
                quote_size = mm_intents[0].size

            intents = list(mm_intents)
            if decision_rng.random() < informed_activity_prob:
                intents.extend(inf.generate_intents(ts))
            intents.extend(noise.generate_intents(ts))

            submit_delay = latency.submission_delay_ms("clob") + latency.ack_delay_ms("clob")
            for intent in intents:
                due_ts = _align_to_step(ts + max(step_ms, submit_delay), step_ms)
                pending_orders[due_ts].append(intent)

        ts += step_ms

    bundle = recorder.build_bundle(
        scenario_id="pt010-calibration",
        seed=seed,
        mechanism="clob",
        mark_price=last_truth,
    )
    metrics = bundle.metrics

    engine = AccountingEngine()
    engine.process_fills(recorder.fills)
    account = engine.snapshot().accounts.get("mm-1")
    mm_abs_inventory = abs(account.inventory) if account is not None else 0.0

    mm_pnl = float(metrics["mm_pnl"])
    mm_max_drawdown = float(metrics["mm_max_drawdown"])
    mm_as_loss = float(metrics["mm_adverse_selection_loss"])
    market_spread_mean = float(metrics["market_spread_mean"])

    stable = (
        mm_pnl >= criteria.min_mm_pnl
        and mm_abs_inventory <= criteria.max_abs_inventory
        and mm_max_drawdown <= criteria.max_drawdown
    )
    return RunMetrics(
        mm_pnl=mm_pnl,
        mm_max_drawdown=mm_max_drawdown,
        mm_adverse_selection_loss=mm_as_loss,
        mm_abs_inventory=mm_abs_inventory,
        market_spread_mean=market_spread_mean,
        stable=stable,
    )


def _align_to_step(ts_ms: int, step_ms: int) -> int:
    if step_ms <= 0:
        raise ValueError("step_ms must be > 0")
    if ts_ms <= 0:
        return 0
    return ((ts_ms + step_ms - 1) // step_ms) * step_ms
