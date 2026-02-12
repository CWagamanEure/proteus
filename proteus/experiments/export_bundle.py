"""CLI to generate one canonical run artifact bundle."""

from __future__ import annotations

import argparse
from pathlib import Path

from proteus.core.events import Event, EventType, Fill
from proteus.experiments.scenarios import clob_smoke_scenario
from proteus.metrics.recorder import Recorder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate one run artifact bundle.")
    parser.add_argument("--out-dir", required=True, help="Output directory for artifacts")
    parser.add_argument("--run-id", default="smoke-run", help="Artifact file prefix")
    parser.add_argument("--seed", type=int, default=7, help="Scenario seed")
    parser.add_argument("--mark-price", type=float, default=0.5, help="Mark price for PnL metrics")
    parser.add_argument(
        "--write-parquet",
        action="store_true",
        help="Also write event/fill parquet files (requires pandas + parquet engine)",
    )
    args = parser.parse_args(argv)

    scenario = clob_smoke_scenario(seed=args.seed)
    recorder = Recorder()

    recorder.record(
        Event(event_id="news-1", ts_ms=0, event_type=EventType.NEWS, payload={"p_t": 0.45})
    )

    recorder.record(
        Event(
            event_id="ord-1",
            ts_ms=1,
            event_type=EventType.ORDER,
            payload={"agent_id": "noise-1"},
        )
    )
    recorder.record(
        Event(
            event_id="quote-1",
            ts_ms=1,
            event_type=EventType.QUOTE,
            payload={"bid": 0.44, "ask": 0.46, "bid_size": 10.0, "ask_size": 12.0},
        )
    )

    fill = Fill(
        fill_id="fill-1",
        ts_ms=2,
        buy_agent_id="noise-1",
        sell_agent_id="mm-1",
        price=0.46,
        size=5.0,
    )

    recorder.record_fill(fill)
    recorder.record(
        Event(
            event_id="fill-1-evt",
            ts_ms=2,
            event_type=EventType.FILL,
            payload={"fill_id": "fill-1"},
        )
    )

    bundle = recorder.build_bundle(
        scenario_id=scenario.scenario_id,
        seed=scenario.seed,
        mechanism=scenario.mechanism.name,
        mark_price=args.mark_price,
    )

    outputs = recorder.write_bundle(
        bundle,
        output_dir=Path(args.out_dir),
        run_id=args.run_id,
        write_parquet=args.write_parquet,
    )

    print(outputs["bundle_json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
