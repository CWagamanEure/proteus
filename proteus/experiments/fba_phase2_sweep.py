"""PT-014 Phase 2 CLOB vs FBA delta sweep + analysis."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from math import isfinite, sqrt
from pathlib import Path
from random import Random
from statistics import mean, stdev

from proteus.agents.informed import InformedTraderAgent
from proteus.agents.market_maker import MarketMakerAgent
from proteus.agents.noise import NoiseTraderAgent
from proteus.core.accounting import AccountingEngine
from proteus.core.config import MechanismConfig, ScenarioConfig
from proteus.core.events import Event, EventType, Fill, OrderIntent, Side
from proteus.core.rng import RNGManager, derive_repetition_seed
from proteus.execution.latency import ConfigurableLatencyModel, LatencyProfile
from proteus.experiments.calibration import (
    CalibrationSearchConfig,
    CandidateRegime,
    SurvivalCriteria,
    run_clob_calibration,
)
from proteus.experiments.runner import build_mechanism
from proteus.info.latent_process import BoundedLogOddsLatentProcess
from proteus.info.signal_model import AgentSignalConfig, HeterogeneousSignalModel
from proteus.metrics.recorder import Recorder


@dataclass(frozen=True)
class Phase2SweepConfig:
    base_seed: int = 7
    repetitions: int = 8
    duration_ms: int = 20_000
    step_ms: int = 100
    batch_intervals_ms: tuple[int, ...] = (50, 100, 250, 500, 1000)
    informed_activity_prob: float = 0.06
    submission_latency_ms: int = 1
    fba_price_tie_policy: str = "min_imbalance"
    fba_allocation_policy: str = "time_priority"
    calibration: CalibrationSearchConfig = field(default_factory=CalibrationSearchConfig)


@dataclass(frozen=True)
class Phase2SweepResult:
    run_dir: str
    report_path: str
    summary_csv_path: str
    calibration_report_path: str | None


@dataclass(frozen=True)
class Phase2RunMetrics:
    mm_pnl: float
    mm_max_drawdown: float
    mm_adverse_selection_loss: float
    mm_abs_inventory: float
    market_spread_mean: float
    stable: bool
    trader_time_to_execution_ms: float
    market_price_rmse: float


def run_fba_phase2_sweep(
    config: Phase2SweepConfig,
    *,
    out_dir: str | Path,
    version_tag: str = "v1",
) -> Phase2SweepResult:
    _validate_config(config)

    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / f"pt014_phase2_delta_sweep_{version_tag}"
    run_dir.mkdir(parents=True, exist_ok=True)

    seeds = tuple(derive_repetition_seed(config.base_seed, i) for i in range(config.repetitions))

    cal_cfg = CalibrationSearchConfig(
        seeds=seeds,
        duration_ms=config.duration_ms,
        step_ms=config.step_ms,
        mm_h0_grid=config.calibration.mm_h0_grid,
        mm_kappa_grid=config.calibration.mm_kappa_grid,
        mm_min_half_spread_grid=config.calibration.mm_min_half_spread_grid,
        baseline_informed_activity_prob=config.calibration.baseline_informed_activity_prob,
        baseline_submission_latency_ms=config.calibration.baseline_submission_latency_ms,
        informed_activity_grid=config.calibration.informed_activity_grid,
        latency_submission_grid_ms=config.calibration.latency_submission_grid_ms,
        criteria=config.calibration.criteria,
    )
    calibration = run_clob_calibration(
        cal_cfg,
        out_dir=run_dir,
        report_name="clob_calibration_report.json",
    )
    regime = calibration.selected_regime

    clob_runs = _run_mechanism_cell(
        seeds=seeds,
        duration_ms=config.duration_ms,
        step_ms=config.step_ms,
        regime=regime,
        informed_activity_prob=config.informed_activity_prob,
        submission_latency_ms=config.submission_latency_ms,
        mechanism_name="clob",
        mechanism_params={},
    )

    rows: list[dict[str, float | str]] = []
    for delta_ms in config.batch_intervals_ms:
        fba_runs = _run_mechanism_cell(
            seeds=seeds,
            duration_ms=config.duration_ms,
            step_ms=config.step_ms,
            regime=regime,
            informed_activity_prob=config.informed_activity_prob,
            submission_latency_ms=config.submission_latency_ms,
            mechanism_name="fba",
            mechanism_params={
                "batch_interval_ms": delta_ms,
                "price_tie_policy": config.fba_price_tie_policy,
                "allocation_policy": config.fba_allocation_policy,
            },
        )
        rows.append(
            _summarize_comparison_row(delta_ms=delta_ms, clob_runs=clob_runs, fba_runs=fba_runs)
        )

    config_payload = asdict(config)
    config_payload["effective_repetition_seeds"] = list(seeds)
    config_payload["calibration"]["seeds"] = list(seeds)
    config_payload["calibration"]["duration_ms"] = config.duration_ms
    config_payload["calibration"]["step_ms"] = config.step_ms

    report_payload = {
        "config": config_payload,
        "selected_regime": asdict(regime),
        "calibration_baseline_summary": calibration.baseline_summary,
        "rows": rows,
    }

    report_path = run_dir / "phase2_delta_sweep_report.json"
    report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")

    summary_csv_path = run_dir / "phase2_delta_sweep_summary.csv"
    _write_summary_csv(summary_csv_path, rows)

    return Phase2SweepResult(
        run_dir=str(run_dir),
        report_path=str(report_path),
        summary_csv_path=str(summary_csv_path),
        calibration_report_path=calibration.report_path,
    )


def _validate_config(config: Phase2SweepConfig) -> None:
    if config.repetitions <= 0:
        raise ValueError("repetitions must be > 0")
    if config.duration_ms <= 0:
        raise ValueError("duration_ms must be > 0")
    if config.step_ms <= 0:
        raise ValueError("step_ms must be > 0")
    if not config.batch_intervals_ms:
        raise ValueError("batch_intervals_ms must be non-empty")
    if any(delta <= 0 for delta in config.batch_intervals_ms):
        raise ValueError("batch_intervals_ms values must be > 0")


def _run_mechanism_cell(
    *,
    seeds: tuple[int, ...],
    duration_ms: int,
    step_ms: int,
    regime: CandidateRegime,
    informed_activity_prob: float,
    submission_latency_ms: int,
    mechanism_name: str,
    mechanism_params: dict[str, object],
) -> list[Phase2RunMetrics]:
    return [
        _simulate_one_mechanism(
            seed=seed,
            duration_ms=duration_ms,
            step_ms=step_ms,
            regime=regime,
            informed_activity_prob=informed_activity_prob,
            submission_latency_ms=submission_latency_ms,
            mechanism_name=mechanism_name,
            mechanism_params=mechanism_params,
            criteria=SurvivalCriteria(),
        )
        for seed in seeds
    ]


def _simulate_one_mechanism(
    *,
    seed: int,
    duration_ms: int,
    step_ms: int,
    regime: CandidateRegime,
    informed_activity_prob: float,
    submission_latency_ms: int,
    mechanism_name: str,
    mechanism_params: dict[str, object],
    criteria: SurvivalCriteria,
) -> Phase2RunMetrics:
    rng = RNGManager(seed)

    clob_reference = ScenarioConfig(
        scenario_id="pt014-clob-reference",
        seed=seed,
        duration_ms=duration_ms,
        mechanism=MechanismConfig(name="clob", params={}),
        params={
            "step_ms": step_ms,
            "informed_activity_prob": informed_activity_prob,
            "submission_latency_ms": submission_latency_ms,
            "regime": asdict(regime),
        },
    )
    scenario = ScenarioConfig(
        scenario_id=f"pt014-{mechanism_name}",
        seed=seed,
        duration_ms=duration_ms,
        mechanism=MechanismConfig(name=mechanism_name, params=dict(mechanism_params)),
        params={
            "step_ms": step_ms,
            "informed_activity_prob": informed_activity_prob,
            "submission_latency_ms": submission_latency_ms,
            "regime": asdict(regime),
        },
    )
    mechanism = build_mechanism(
        scenario,
        parity_reference=clob_reference if mechanism_name != "clob" else None,
    )
    mech_name = scenario.mechanism.name

    latency_profile = LatencyProfile(
        submission_ms=submission_latency_ms,
        ack_ms=1,
        fill_ms=1,
        jitter_ms=0,
    )
    latency = ConfigurableLatencyModel(
        default=latency_profile,
        per_mechanism={"clob": latency_profile, "fba": latency_profile},
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
    next_decision_ts = 0

    while True:
        candidate_ts: list[int] = []
        if next_decision_ts <= duration_ms:
            candidate_ts.append(next_decision_ts)
        if pending_orders:
            candidate_ts.append(min(pending_orders))
        if pending_fills:
            candidate_ts.append(min(pending_fills))
        if not candidate_ts:
            break

        ts = min(candidate_ts)

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
            pending_fills[ts + latency.fill_delay_ms(mech_name)].append(fill)

        if ts == next_decision_ts and ts <= duration_ms:
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

            submit_delay = latency.submission_delay_ms(mech_name) + latency.ack_delay_ms(mech_name)
            for intent in intents:
                pending_orders[ts + submit_delay].append(intent)

            next_decision_ts += step_ms

    bundle = recorder.build_bundle(
        scenario_id=f"pt014-{mech_name}",
        seed=seed,
        mechanism=mech_name,
        mark_price=last_truth,
    )
    metrics = bundle.metrics

    engine = AccountingEngine()
    engine.process_fills(recorder.fills)
    account = engine.snapshot().accounts.get("mm-1")
    mm_abs_inventory = abs(account.inventory) if account is not None else 0.0

    stable = (
        float(metrics["mm_pnl"]) >= criteria.min_mm_pnl
        and mm_abs_inventory <= criteria.max_abs_inventory
        and float(metrics["mm_max_drawdown"]) <= criteria.max_drawdown
    )

    return Phase2RunMetrics(
        mm_pnl=float(metrics["mm_pnl"]),
        mm_max_drawdown=float(metrics["mm_max_drawdown"]),
        mm_adverse_selection_loss=float(metrics["mm_adverse_selection_loss"]),
        mm_abs_inventory=float(mm_abs_inventory),
        market_spread_mean=float(metrics["market_spread_mean"]),
        stable=stable,
        trader_time_to_execution_ms=float(metrics["trader_time_to_execution_ms"]),
        market_price_rmse=float(metrics["market_price_rmse"]),
    )


def _summarize_comparison_row(
    *,
    delta_ms: int,
    clob_runs: list[Phase2RunMetrics],
    fba_runs: list[Phase2RunMetrics],
) -> dict[str, float | str]:
    endpoints = {
        "mm_as_loss": (
            [r.mm_adverse_selection_loss for r in clob_runs],
            [r.mm_adverse_selection_loss for r in fba_runs],
        ),
        "market_spread_mean": (
            [r.market_spread_mean for r in clob_runs],
            [r.market_spread_mean for r in fba_runs],
        ),
        "trader_time_to_execution_ms": (
            [r.trader_time_to_execution_ms for r in clob_runs],
            [r.trader_time_to_execution_ms for r in fba_runs],
        ),
        "market_price_rmse": (
            [r.market_price_rmse for r in clob_runs],
            [r.market_price_rmse for r in fba_runs],
        ),
    }

    row: dict[str, float | str] = {
        "delta_ms": float(delta_ms),
        "n_runs": float(len(fba_runs)),
    }
    notes: list[str] = []

    for label, (clob_vals, fba_vals) in endpoints.items():
        fba_mu, fba_lo, fba_hi = _mean_ci95(fba_vals)
        diffs = [fba_vals[i] - clob_vals[i] for i in range(min(len(clob_vals), len(fba_vals)))]
        diff_mu, diff_lo, diff_hi = _mean_ci95(diffs)

        row[f"{label}_fba_mean"] = fba_mu
        row[f"{label}_fba_ci95_low"] = fba_lo
        row[f"{label}_fba_ci95_high"] = fba_hi
        row[f"{label}_delta_vs_clob_mean"] = diff_mu
        row[f"{label}_delta_vs_clob_ci95_low"] = diff_lo
        row[f"{label}_delta_vs_clob_ci95_high"] = diff_hi
        notes.append(_significance_note(label, diff_lo, diff_hi))

    row["significance_notes"] = " | ".join(notes)
    return row


def _mean_ci95(values: list[float]) -> tuple[float, float, float]:
    clean = [value for value in values if isfinite(value)]
    if not clean:
        return (0.0, 0.0, 0.0)
    mu = mean(clean)
    if len(clean) < 2:
        return (mu, mu, mu)
    half_width = 1.96 * (stdev(clean) / sqrt(len(clean)))
    return (mu, mu - half_width, mu + half_width)


def _significance_note(metric: str, diff_lo: float, diff_hi: float) -> str:
    if diff_lo > 0.0:
        return f"{metric}: FBA > CLOB (CI excludes 0)"
    if diff_hi < 0.0:
        return f"{metric}: FBA < CLOB (CI excludes 0)"
    return f"{metric}: no clear difference"


def _write_summary_csv(path: Path, rows: list[dict[str, float | str]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
