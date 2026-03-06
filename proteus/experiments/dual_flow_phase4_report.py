"""PT-017 optional dual-flow comparative report (gated)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from proteus.core.config import MechanismConfig, ScenarioConfig
from proteus.core.events import OrderIntent, Side
from proteus.experiments.runner import build_mechanism


@dataclass(frozen=True)
class DualFlowPhase4Config:
    phase2_report_path: str | Path
    phase3_report_path: str | Path
    seed: int = 7
    duration_ms: int = 1_000
    batch_interval_ms: int = 100
    maker_id_prefixes: tuple[str, ...] = ("mm-",)


@dataclass(frozen=True)
class DualFlowPhase4Result:
    report_path: str


def run_dual_flow_phase4_report(
    config: DualFlowPhase4Config,
    *,
    out_dir: str | Path,
    version_tag: str = "v1",
) -> DualFlowPhase4Result:
    gate_status = _load_gate_status(config.phase2_report_path, config.phase3_report_path)

    scenario = ScenarioConfig(
        scenario_id="pt017-dual-flow",
        seed=config.seed,
        duration_ms=config.duration_ms,
        mechanism=MechanismConfig(
            name="dual_flow_batch",
            params={
                "batch_interval_ms": config.batch_interval_ms,
                "maker_id_prefixes": config.maker_id_prefixes,
            },
        ),
        params={
            "dual_flow_gate": {
                "phase2_passed": gate_status["phase2_passed"],
                "phase3_passed": gate_status["phase3_passed"],
            }
        },
    )

    # Hard gate enforcement occurs in build_mechanism.
    dual_flow = build_mechanism(scenario)

    clob = build_mechanism(
        ScenarioConfig(
            scenario_id="pt017-clob-baseline",
            seed=config.seed,
            duration_ms=config.duration_ms,
            mechanism=MechanismConfig(name="clob", params={}),
            params={},
        )
    )
    fba = build_mechanism(
        ScenarioConfig(
            scenario_id="pt017-fba-baseline",
            seed=config.seed,
            duration_ms=config.duration_ms,
            mechanism=MechanismConfig(
                name="fba",
                params={"batch_interval_ms": config.batch_interval_ms},
            ),
            params={},
        )
    )

    config_payload = asdict(config)
    config_payload["phase2_report_path"] = str(config.phase2_report_path)
    config_payload["phase3_report_path"] = str(config.phase3_report_path)

    comparison = {
        "dual_flow_batch": _run_fixture(dual_flow, clear_ts=config.batch_interval_ms),
        "clob": _run_fixture(clob, clear_ts=config.batch_interval_ms),
        "fba": _run_fixture(fba, clear_ts=config.batch_interval_ms),
    }

    payload = {
        "ticket": "PT-017",
        "version_tag": version_tag,
        "config": config_payload,
        "gate_status": gate_status,
        "comparison": comparison,
        "notes": [
            "Dual-flow gate satisfied from PT-014/PT-016 report evidence.",
            "Dual-flow fixture enforces maker/taker segregation with "
            "separate buy/sell batch clears.",
        ],
    }

    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / f"pt017_dual_flow_report_{version_tag}"
    run_dir.mkdir(parents=True, exist_ok=True)

    report_path = run_dir / "dual_flow_phase4_report.json"
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    return DualFlowPhase4Result(report_path=str(report_path))


def _load_gate_status(
    phase2_report_path: str | Path,
    phase3_report_path: str | Path,
) -> dict[str, bool]:
    return {
        "phase2_passed": _report_has_rows(phase2_report_path),
        "phase3_passed": _report_has_rows(phase3_report_path),
    }


def _report_has_rows(path: str | Path) -> bool:
    report_path = Path(path)
    if not report_path.exists():
        return False

    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    rows = payload.get("rows")
    return isinstance(rows, list) and len(rows) > 0


def _run_fixture(mechanism, *, clear_ts: int) -> dict[str, float]:
    orders = [
        # makers
        OrderIntent("m-sell-1", "mm-1", 0, Side.SELL, 0.55, 2.0),
        OrderIntent("m-buy-1", "mm-2", 0, Side.BUY, 0.45, 2.0),
        # takers
        OrderIntent("t-buy-1", "noise-1", 1, Side.BUY, 0.60, 1.0),
        OrderIntent("t-sell-1", "inf-1", 1, Side.SELL, 0.40, 1.0),
        # maker-maker cross candidate (should not cross in dual-flow)
        OrderIntent("m-buy-2", "mm-3", 2, Side.BUY, 0.60, 1.0),
        OrderIntent("m-sell-2", "mm-4", 2, Side.SELL, 0.40, 1.0),
    ]

    for order in orders:
        mechanism.submit(order)

    fills = list(mechanism.clear(clear_ts))
    total_size = sum(fill.size for fill in fills)
    mean_price = (
        sum(fill.price * fill.size for fill in fills) / total_size if total_size > 0 else 0.0
    )

    maker_maker_fills = sum(
        1
        for fill in fills
        if fill.buy_agent_id.startswith("mm-") and fill.sell_agent_id.startswith("mm-")
    )

    return {
        "fill_count": float(len(fills)),
        "total_size": float(total_size),
        "mean_price": float(mean_price),
        "maker_maker_fill_count": float(maker_maker_fills),
    }
