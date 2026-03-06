"""PT-016 RFQ scenario sweeps + analysis."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from math import isfinite, sqrt
from pathlib import Path
from random import Random
from statistics import mean, stdev

from proteus.core.config import MechanismConfig, ScenarioConfig
from proteus.core.events import Event, EventType, Fill, Side
from proteus.core.rng import RNGManager, derive_repetition_seed
from proteus.execution.latency import ConfigurableLatencyModel, LatencyProfile
from proteus.experiments.calibration import (
    CalibrationSearchConfig,
    CandidateRegime,
    SurvivalCriteria,
    run_clob_calibration,
)
from proteus.experiments.fba_phase2_sweep import _simulate_one_mechanism
from proteus.experiments.runner import build_mechanism
from proteus.info.latent_process import BoundedLogOddsLatentProcess
from proteus.mechanisms.rfq import RFQAcceptIntent, RFQQuoteIntent, RFQRequestIntent
from proteus.metrics.recorder import Recorder


@dataclass(frozen=True)
class RFQPhase3SweepConfig:
    base_seed: int = 7
    repetitions: int = 8
    duration_ms: int = 20_000
    step_ms: int = 100
    request_ttl_grid_ms: tuple[int, ...] = (50, 100, 250, 500)
    response_latency_grid_ms: tuple[int, ...] = (0, 5, 10, 25)
    dealer_count_grid: tuple[int, ...] = (1, 2, 3)
    informed_activity_prob: float = 0.06
    submission_latency_ms: int = 1
    rfq_request_prob_per_step: float = 0.5
    rfq_request_size_range: tuple[float, float] = (0.5, 2.0)
    rfq_half_spread: float = 0.01
    dealer_competition_step: float = 0.0015
    calibration: CalibrationSearchConfig = field(default_factory=CalibrationSearchConfig)


@dataclass(frozen=True)
class RFQPhase3SweepResult:
    run_dir: str
    report_path: str
    summary_csv_path: str
    calibration_report_path: str | None


@dataclass(frozen=True)
class RFQRunMetrics:
    mm_pnl: float
    mm_max_drawdown: float
    mm_adverse_selection_loss: float
    market_spread_mean: float
    trader_time_to_execution_ms: float
    market_price_rmse: float
    stable: bool


def run_rfq_phase3_sweep(
    config: RFQPhase3SweepConfig,
    *,
    out_dir: str | Path,
    version_tag: str = "v1",
    show_progress: bool = False,
) -> RFQPhase3SweepResult:
    _validate_config(config)

    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / f"pt016_rfq_phase3_sweep_{version_tag}"
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
    if show_progress:
        print("[proteus] phase3: running CLOB calibration")
    calibration = run_clob_calibration(
        cal_cfg,
        out_dir=run_dir,
        report_name="clob_calibration_report.json",
        show_progress=show_progress,
    )
    if show_progress:
        print("[proteus] phase3: calibration complete")
    regime = calibration.selected_regime

    if show_progress:
        print("[proteus] phase3: running CLOB baseline contrast cell")
    clob_runs = _run_clob_baseline_cell(
        seeds=seeds,
        duration_ms=config.duration_ms,
        step_ms=config.step_ms,
        regime=regime,
        informed_activity_prob=config.informed_activity_prob,
        submission_latency_ms=config.submission_latency_ms,
    )
    if show_progress:
        print("[proteus] phase3: running RFQ sweep cells")

    cells = [
        (request_ttl_ms, response_latency_ms, dealer_count)
        for request_ttl_ms in config.request_ttl_grid_ms
        for response_latency_ms in config.response_latency_grid_ms
        for dealer_count in config.dealer_count_grid
    ]

    rows: list[dict[str, float | str]] = []
    for request_ttl_ms, response_latency_ms, dealer_count in _with_progress(
        cells,
        label="PT-016 sweep cells",
        enabled=show_progress,
    ):
        rfq_runs = _run_rfq_cell(
            seeds=seeds,
            duration_ms=config.duration_ms,
            step_ms=config.step_ms,
            regime=regime,
            request_ttl_ms=request_ttl_ms,
            response_latency_ms=response_latency_ms,
            dealer_count=dealer_count,
            criteria=config.calibration.criteria,
            request_prob_per_step=config.rfq_request_prob_per_step,
            request_size_range=config.rfq_request_size_range,
            half_spread=config.rfq_half_spread,
            dealer_competition_step=config.dealer_competition_step,
        )
        rows.append(
            _summarize_comparison_row(
                request_ttl_ms=request_ttl_ms,
                response_latency_ms=response_latency_ms,
                dealer_count=dealer_count,
                clob_runs=clob_runs,
                rfq_runs=rfq_runs,
            )
        )

    frontier_protection_vs_discovery = _compute_frontier(
        rows,
        x_key="mm_as_loss_delta_vs_clob_mean",
        y_key="market_price_rmse_delta_vs_clob_mean",
    )
    frontier_protection_vs_speed = _compute_frontier(
        rows,
        x_key="mm_as_loss_delta_vs_clob_mean",
        y_key="trader_time_to_execution_ms_delta_vs_clob_mean",
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
        "frontiers": {
            "protection_vs_price_discovery": frontier_protection_vs_discovery,
            "protection_vs_execution_speed": frontier_protection_vs_speed,
        },
    }

    report_path = run_dir / "rfq_phase3_sweep_report.json"
    report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")

    summary_csv_path = run_dir / "rfq_phase3_sweep_summary.csv"
    _write_summary_csv(summary_csv_path, rows)

    return RFQPhase3SweepResult(
        run_dir=str(run_dir),
        report_path=str(report_path),
        summary_csv_path=str(summary_csv_path),
        calibration_report_path=calibration.report_path,
    )


def _validate_config(config: RFQPhase3SweepConfig) -> None:
    if config.repetitions <= 0:
        raise ValueError("repetitions must be > 0")
    if config.duration_ms <= 0:
        raise ValueError("duration_ms must be > 0")
    if config.step_ms <= 0:
        raise ValueError("step_ms must be > 0")
    if not config.request_ttl_grid_ms:
        raise ValueError("request_ttl_grid_ms must be non-empty")
    if any(ttl <= 0 for ttl in config.request_ttl_grid_ms):
        raise ValueError("request_ttl_grid_ms values must be > 0")
    if not config.response_latency_grid_ms:
        raise ValueError("response_latency_grid_ms must be non-empty")
    if any(latency < 0 for latency in config.response_latency_grid_ms):
        raise ValueError("response_latency_grid_ms values must be >= 0")
    if not config.dealer_count_grid:
        raise ValueError("dealer_count_grid must be non-empty")
    if any(count <= 0 for count in config.dealer_count_grid):
        raise ValueError("dealer_count_grid values must be > 0")
    min_size, max_size = config.rfq_request_size_range
    if min_size <= 0.0 or max_size <= 0.0 or min_size > max_size:
        raise ValueError("rfq_request_size_range must satisfy 0 < min_size <= max_size")
    if not (0.0 <= config.rfq_request_prob_per_step <= 1.0):
        raise ValueError("rfq_request_prob_per_step must be in [0, 1]")
    if config.rfq_half_spread <= 0.0:
        raise ValueError("rfq_half_spread must be > 0")
    if config.dealer_competition_step < 0.0:
        raise ValueError("dealer_competition_step must be >= 0")


def _run_clob_baseline_cell(
    *,
    seeds: tuple[int, ...],
    duration_ms: int,
    step_ms: int,
    regime: CandidateRegime,
    informed_activity_prob: float,
    submission_latency_ms: int,
) -> list[RFQRunMetrics]:
    return [
        _rfq_metrics_from_extended_run(
            _simulate_one_mechanism(
                seed=seed,
                duration_ms=duration_ms,
                step_ms=step_ms,
                regime=regime,
                informed_activity_prob=informed_activity_prob,
                submission_latency_ms=submission_latency_ms,
                mechanism_name="clob",
                mechanism_params={},
                criteria=SurvivalCriteria(),
            )
        )
        for seed in seeds
    ]


def _rfq_metrics_from_extended_run(run) -> RFQRunMetrics:
    return RFQRunMetrics(
        mm_pnl=run.mm_pnl,
        mm_max_drawdown=run.mm_max_drawdown,
        mm_adverse_selection_loss=run.mm_adverse_selection_loss,
        market_spread_mean=run.market_spread_mean,
        trader_time_to_execution_ms=run.trader_time_to_execution_ms,
        market_price_rmse=run.market_price_rmse,
        stable=run.stable,
    )


def _run_rfq_cell(
    *,
    seeds: tuple[int, ...],
    duration_ms: int,
    step_ms: int,
    regime: CandidateRegime,
    request_ttl_ms: int,
    response_latency_ms: int,
    dealer_count: int,
    criteria: SurvivalCriteria,
    request_prob_per_step: float,
    request_size_range: tuple[float, float],
    half_spread: float,
    dealer_competition_step: float,
) -> list[RFQRunMetrics]:
    return [
        _simulate_rfq_one(
            seed=seed,
            duration_ms=duration_ms,
            step_ms=step_ms,
            regime=regime,
            request_ttl_ms=request_ttl_ms,
            response_latency_ms=response_latency_ms,
            dealer_count=dealer_count,
            criteria=criteria,
            request_prob_per_step=request_prob_per_step,
            request_size_range=request_size_range,
            half_spread=half_spread,
            dealer_competition_step=dealer_competition_step,
        )
        for seed in seeds
    ]


def _simulate_rfq_one(
    *,
    seed: int,
    duration_ms: int,
    step_ms: int,
    regime: CandidateRegime,
    request_ttl_ms: int,
    response_latency_ms: int,
    dealer_count: int,
    criteria: SurvivalCriteria,
    request_prob_per_step: float,
    request_size_range: tuple[float, float],
    half_spread: float,
    dealer_competition_step: float,
) -> RFQRunMetrics:
    rng = RNGManager(seed)
    sim_rng = Random(rng.child_seed("rfq-sim"))

    dealer_ids = tuple(f"mm-{idx + 1}" for idx in range(dealer_count))

    clob_reference = ScenarioConfig(
        scenario_id="pt016-clob-reference",
        seed=seed,
        duration_ms=duration_ms,
        mechanism=MechanismConfig(name="clob", params={}),
        params={
            "step_ms": step_ms,
            "request_ttl_ms": request_ttl_ms,
            "response_latency_ms": response_latency_ms,
            "dealer_count": dealer_count,
            "regime": asdict(regime),
        },
    )
    scenario = ScenarioConfig(
        scenario_id="pt016-rfq",
        seed=seed,
        duration_ms=duration_ms,
        mechanism=MechanismConfig(
            name="rfq",
            params={
                "min_response_latency_ms": response_latency_ms,
                "default_request_ttl_ms": request_ttl_ms,
                "allowed_dealer_ids": dealer_ids,
                "max_quotes_per_request": dealer_count,
            },
        ),
        params={
            "step_ms": step_ms,
            "request_ttl_ms": request_ttl_ms,
            "response_latency_ms": response_latency_ms,
            "dealer_count": dealer_count,
            "regime": asdict(regime),
        },
    )

    mechanism = build_mechanism(scenario, parity_reference=clob_reference)

    latency_profile = LatencyProfile(
        submission_ms=0,
        ack_ms=0,
        fill_ms=1,
        jitter_ms=0,
    )
    latency = ConfigurableLatencyModel(
        default=latency_profile,
        per_mechanism={"rfq": latency_profile},
        seed=rng.child_seed("latency"),
    )

    latent = BoundedLogOddsLatentProcess(p0=0.5, phi=0.995, sigma_eta=0.2)
    latent.reset(rng.child_seed("latent"))

    recorder = Recorder()
    pending_clears: set[int] = set()
    pending_fills: dict[int, list[Fill]] = defaultdict(list)

    event_seq = 0
    request_seq = 0
    quote_seq = 0
    accept_seq = 0
    next_decision_ts = 0
    last_truth = 0.5

    while True:
        candidate_ts: list[int] = []
        if next_decision_ts <= duration_ms:
            candidate_ts.append(next_decision_ts)
        if pending_clears:
            candidate_ts.append(min(pending_clears))
        if pending_fills:
            candidate_ts.append(min(pending_fills))
        if not candidate_ts:
            break

        ts = min(candidate_ts)

        fills_due = pending_fills.pop(ts, [])
        for fill in fills_due:
            recorder.record_fill(fill)
            event_seq += 1
            recorder.record(
                Event(
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
            )

        if ts in pending_clears:
            pending_clears.discard(ts)

        for fill in mechanism.clear(ts):
            fill_due_ts = ts + latency.fill_delay_ms("rfq")
            pending_fills[fill_due_ts].append(fill)

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

            if sim_rng.random() < request_prob_per_step:
                request_seq += 1
                request_id = f"req-{request_seq}"
                requester_id = "inf-1" if sim_rng.random() < 0.5 else "noise-1"
                side = Side.BUY if sim_rng.random() < 0.5 else Side.SELL
                size = sim_rng.uniform(request_size_range[0], request_size_range[1])

                mechanism.request_quote(
                    RFQRequestIntent(
                        request_id=request_id,
                        requester_id=requester_id,
                        ts_ms=ts,
                        side=side,
                        size=size,
                        ttl_ms=request_ttl_ms,
                    )
                )
                pending_clears.add(ts)

                event_seq += 1
                recorder.record(
                    Event(
                        event_id=f"order-{event_seq}",
                        ts_ms=ts,
                        event_type=EventType.ORDER,
                        payload={
                            "agent_id": requester_id,
                            "side": side.value,
                            "size": size,
                            "rfq_request_id": request_id,
                        },
                    )
                )

                quote_side = Side.SELL if side is Side.BUY else Side.BUY
                quote_ts = ts + response_latency_ms
                accept_ts = quote_ts + 1

                quote_prices: list[float] = []
                quote_ids: list[str] = []
                for dealer_idx, dealer_id in enumerate(dealer_ids):
                    quote_seq += 1
                    quote_id = f"quote-{quote_seq}"
                    dealer_shade = dealer_competition_step * dealer_idx
                    micro_noise = sim_rng.uniform(0.0, dealer_competition_step)

                    if side is Side.BUY:
                        price = _clamp_price(last_truth + half_spread - dealer_shade + micro_noise)
                    else:
                        price = _clamp_price(last_truth - half_spread + dealer_shade - micro_noise)

                    quote_prices.append(price)
                    quote_ids.append(quote_id)

                    mechanism.submit_quote(
                        RFQQuoteIntent(
                            quote_id=quote_id,
                            request_id=request_id,
                            dealer_id=dealer_id,
                            ts_ms=quote_ts,
                            side=quote_side,
                            price=price,
                            size=size,
                            ttl_ms=max(1, request_ttl_ms - (quote_ts - ts)),
                        )
                    )
                    pending_clears.add(quote_ts)

                if quote_prices:
                    best_quote_idx = (
                        quote_prices.index(min(quote_prices))
                        if side is Side.BUY
                        else quote_prices.index(max(quote_prices))
                    )
                    selected_quote_id = quote_ids[best_quote_idx]

                    accept_seq += 1
                    mechanism.accept_quote(
                        RFQAcceptIntent(
                            accept_id=f"accept-{accept_seq}",
                            request_id=request_id,
                            requester_id=requester_id,
                            quote_id=selected_quote_id,
                            ts_ms=accept_ts,
                        )
                    )
                    pending_clears.add(accept_ts)

                    synthetic_bid = _clamp_price(last_truth - half_spread)
                    synthetic_ask = _clamp_price(last_truth + half_spread)
                    if side is Side.BUY:
                        synthetic_ask = min(synthetic_ask, min(quote_prices))
                    else:
                        synthetic_bid = max(synthetic_bid, max(quote_prices))
                    if synthetic_ask < synthetic_bid:
                        synthetic_ask = synthetic_bid

                    event_seq += 1
                    recorder.record(
                        Event(
                            event_id=f"quote-{event_seq}",
                            ts_ms=quote_ts,
                            event_type=EventType.QUOTE,
                            payload={
                                "bid": synthetic_bid,
                                "ask": synthetic_ask,
                                "best_bid": synthetic_bid,
                                "best_ask": synthetic_ask,
                                "bid_size": size,
                                "ask_size": size,
                            },
                        )
                    )

            next_decision_ts += step_ms

    bundle = recorder.build_bundle(
        scenario_id="pt016-rfq",
        seed=seed,
        mechanism="rfq",
        mark_price=last_truth,
    )
    metrics = bundle.metrics

    mm_pnl = float(metrics["mm_pnl"])
    mm_max_drawdown = float(metrics["mm_max_drawdown"])
    mm_as_loss = float(metrics["mm_adverse_selection_loss"])
    spread_mean = float(metrics["market_spread_mean"])
    tte = float(metrics["trader_time_to_execution_ms"])
    rmse = float(metrics["market_price_rmse"])

    stable = (
        mm_pnl >= criteria.min_mm_pnl
        and mm_max_drawdown <= criteria.max_drawdown
        and abs(mm_as_loss) <= max(criteria.max_abs_inventory, 1.0) * 10.0
    )

    return RFQRunMetrics(
        mm_pnl=mm_pnl,
        mm_max_drawdown=mm_max_drawdown,
        mm_adverse_selection_loss=mm_as_loss,
        market_spread_mean=spread_mean,
        trader_time_to_execution_ms=tte,
        market_price_rmse=rmse,
        stable=stable,
    )


def _summarize_comparison_row(
    *,
    request_ttl_ms: int,
    response_latency_ms: int,
    dealer_count: int,
    clob_runs: list[RFQRunMetrics],
    rfq_runs: list[RFQRunMetrics],
) -> dict[str, float | str]:
    endpoints = {
        "mm_as_loss": (
            [r.mm_adverse_selection_loss for r in clob_runs],
            [r.mm_adverse_selection_loss for r in rfq_runs],
        ),
        "market_spread_mean": (
            [r.market_spread_mean for r in clob_runs],
            [r.market_spread_mean for r in rfq_runs],
        ),
        "trader_time_to_execution_ms": (
            [r.trader_time_to_execution_ms for r in clob_runs],
            [r.trader_time_to_execution_ms for r in rfq_runs],
        ),
        "market_price_rmse": (
            [r.market_price_rmse for r in clob_runs],
            [r.market_price_rmse for r in rfq_runs],
        ),
    }

    row: dict[str, float | str] = {
        "request_ttl_ms": float(request_ttl_ms),
        "response_latency_ms": float(response_latency_ms),
        "dealer_count": float(dealer_count),
        "n_runs": float(len(rfq_runs)),
    }
    notes: list[str] = []

    for label, (clob_vals, rfq_vals) in endpoints.items():
        rfq_mu, rfq_lo, rfq_hi = _mean_ci95(rfq_vals)
        diffs = [rfq_vals[i] - clob_vals[i] for i in range(min(len(clob_vals), len(rfq_vals)))]
        diff_mu, diff_lo, diff_hi = _mean_ci95(diffs)

        row[f"{label}_rfq_mean"] = rfq_mu
        row[f"{label}_rfq_ci95_low"] = rfq_lo
        row[f"{label}_rfq_ci95_high"] = rfq_hi
        row[f"{label}_delta_vs_clob_mean"] = diff_mu
        row[f"{label}_delta_vs_clob_ci95_low"] = diff_lo
        row[f"{label}_delta_vs_clob_ci95_high"] = diff_hi
        notes.append(_significance_note(label, diff_lo, diff_hi))

    row["significance_notes"] = " | ".join(notes)
    return row


def _compute_frontier(
    rows: list[dict[str, float | str]],
    *,
    x_key: str,
    y_key: str,
) -> list[dict[str, float]]:
    points: list[dict[str, float]] = []
    for row in rows:
        raw_x = row.get(x_key)
        raw_y = row.get(y_key)
        if not isinstance(raw_x, int | float) or not isinstance(raw_y, int | float):
            continue
        x = float(raw_x)
        y = float(raw_y)
        if not isfinite(x) or not isfinite(y):
            continue
        points.append(
            {
                "request_ttl_ms": float(row["request_ttl_ms"]),
                "response_latency_ms": float(row["response_latency_ms"]),
                "dealer_count": float(row["dealer_count"]),
                x_key: x,
                y_key: y,
            }
        )

    frontier: list[dict[str, float]] = []
    for idx, point in enumerate(points):
        dominated = False
        for jdx, other in enumerate(points):
            if idx == jdx:
                continue
            if (
                other[x_key] <= point[x_key]
                and other[y_key] <= point[y_key]
                and (other[x_key] < point[x_key] or other[y_key] < point[y_key])
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(point)

    frontier.sort(key=lambda item: (item[x_key], item[y_key]))
    return frontier


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
        return f"{metric}: RFQ > CLOB (CI excludes 0)"
    if diff_hi < 0.0:
        return f"{metric}: RFQ < CLOB (CI excludes 0)"
    return f"{metric}: no clear difference"


def _write_summary_csv(path: Path, rows: list[dict[str, float | str]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _clamp_price(value: float) -> float:
    return min(0.999, max(0.001, value))


def _with_progress(
    items: Iterable[tuple[int, int, int]],
    *,
    label: str,
    enabled: bool,
) -> Iterator[tuple[int, int, int]]:
    materialized = list(items)
    if not enabled:
        yield from materialized
        return

    try:
        from tqdm.auto import tqdm  # type: ignore[import-not-found]

        yield from tqdm(materialized, desc=label, unit="cell")
        return
    except Exception:
        pass

    total = len(materialized)
    print(f"{label}: starting {total} cell(s)")
    for idx, row in enumerate(materialized, start=1):
        if idx == 1 or idx == total or idx % 5 == 0:
            print(f"{label}: {idx}/{total}")
        yield row
