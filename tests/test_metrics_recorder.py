from __future__ import annotations

from pathlib import Path

from proteus.core.events import Event, EventType, Fill
from proteus.experiments.export_bundle import main as export_main
from proteus.metrics.recorder import NON_NEGOTIABLE_METRICS, SCHEMA_VERSION, Recorder


def _sample_recorder() -> Recorder:
    recorder = Recorder()
    recorder.record(
        Event(
            event_id="news-1",
            ts_ms=0,
            event_type=EventType.NEWS,
            payload={"p_t": 0.5},
        )
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
            payload={"bid": 0.49, "ask": 0.51, "bid_size": 8.0, "ask_size": 9.0},
        )
    )

    recorder.record_fill(
        Fill(
            fill_id="fill-1",
            ts_ms=2,
            buy_agent_id="noise-1",
            sell_agent_id="mm-1",
            price=0.51,
            size=2.0,
        )
    )
    recorder.record_fill(
        Fill(
            fill_id="fill-2",
            ts_ms=3,
            buy_agent_id="mm-1",
            sell_agent_id="inf-1",
            price=0.49,
            size=1.0,
        )
    )
    return recorder


def test_bundle_schema_and_metrics_are_stable() -> None:
    recorder = _sample_recorder()
    bundle = recorder.build_bundle(
        scenario_id="unit_scenario",
        seed=11,
        mechanism="clob",
        mark_price=0.5,
    )

    assert bundle.schema_version == SCHEMA_VERSION
    assert set(NON_NEGOTIABLE_METRICS).issubset(bundle.metrics.keys())
    assert len(bundle.summary_table) == len(bundle.metrics)
    assert bundle.event_log
    assert bundle.fills


def test_bundle_writer_outputs_artifacts(tmp_path: Path) -> None:
    recorder = _sample_recorder()
    bundle = recorder.build_bundle(
        scenario_id="unit_scenario",
        seed=11,
        mechanism="clob",
        mark_price=0.5,
    )

    outputs = recorder.write_bundle(bundle, output_dir=tmp_path, run_id="unit-run")

    assert outputs["bundle_json"].exists()
    assert outputs["metrics_json"].exists()
    assert outputs["summary_csv"].exists()
    assert outputs["events_jsonl"].exists()
    assert outputs["fills_jsonl"].exists()


def test_export_cli_generates_bundle(tmp_path: Path) -> None:
    rc = export_main(["--out-dir", str(tmp_path), "--run-id", "cli-run"])
    assert rc == 0
    assert (tmp_path / "cli-run_bundle.json").exists()
