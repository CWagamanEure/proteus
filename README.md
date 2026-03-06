# Proteus

Proteus is a mechanism-pluggable market microstructure simulation framework.

The goal is to run controlled, reproducible experiments where mechanism design is the treatment variable:
- CLOB vs frequent batch auctions vs RFQ (and later hybrids)
- shared seeds and information paths across runs
- comparable accounting, execution, and metrics outputs

Today, Proteus is in cross-mechanism comparison mode (through PT-016): CLOB, FBA, and RFQ mechanism experiments are implemented with parity checks and sweep tooling.

## Why Proteus

Proteus is built for interesting economics questions like:
- How much adverse selection changes when you switch matching mechanisms?
- When does a market maker survive or fail under informed flow + latency?
- Which market design gives better spread/fill/price-discovery tradeoffs?
- How do incentive policy changes shift behavior (post-MVP roadmap)?

## Current Status

Implemented now (PT-001 to PT-016):
- Deterministic RNG stream manager with subsystem isolation
- Event clock + typed event model + deterministic replay helpers
- Fill accounting engine with reconciliation/invariant checks
- Bounded latent process and heterogeneous signal model
- Canonical run artifact bundle export (`json`, `jsonl`, `csv`, optional parquet)
- CLOB matching engine with deterministic price-time behavior (partials/cancels/crossed-book tests)
- Agent v1 implementations (market maker, informed trader, noise trader)
- Execution latency + leakage primitives with parity defaults
- CLOB calibration harness (`PT-010`) with selected-regime report and sensitivity diagnostics
- CLOB baseline experiment pack (`PT-011`) with Monte Carlo grid summaries, CI bands, and effect sizes
- FBA mechanism implementation (`PT-012`) with uniform-price clearing and configurable tie/allocation policies
- CLOB-vs-FBA parity preflight checks (`PT-013`) integrated into runner
- Phase-2 CLOB vs FBA sweep tooling (`PT-014`) with delta-grid artifacts and CI summaries
- RFQ mechanism implementation (`PT-015`) with request/quote/accept flow, TTL enforcement, and dealer competition controls
- Phase-3 RFQ sweep tooling (`PT-016`) over TTL/latency/dealer grids with frontier-style tradeoff outputs
- Optional dual-flow batch mechanism (`PT-017`) with runner gate checks and comparative phase-4 reporting
- Agent diagnostic schema + research-metric stubs for instrumentation
- Smoke runner wiring for core module initialization

Still scaffold/placeholder:
- Experiment workflow unification CLI/runbook remains open (`PT-020`)
- Longitudinal identity + lending-market extensions are planned (see M5 / research notes)

## Quickstart

Install:

```bash
poetry install
```

Run friendly preset workflows (recommended):

```bash
poetry run proteus-exp run baseline --out-dir ./artifacts/baseline --preset quick
poetry run proteus-exp run phase2 --out-dir ./artifacts/phase2 --preset quick
poetry run proteus-exp run phase3 --out-dir ./artifacts/phase3 --preset quick
```

Preset options:
- `quick`: short local run with small grids
- `ci`: minimal deterministic regression run
- `paper`: full default research grids

Run smoke check:

```bash
python -m proteus
```

Generate a sample artifact bundle:

```bash
python -m proteus.experiments.export_bundle --out-dir ./artifacts
```

Run CLOB calibration (PT-010):

```bash
python -m proteus.experiments.calibrate_clob --out-dir ./artifacts/calibration --duration-ms 2000 --step-ms 100
```

Run CLOB baseline experiment pack (PT-011):

```bash
python -m proteus.experiments.run_clob_baseline_pack --out-dir ./artifacts/baseline --repetitions 10 --duration-ms 4000 --step-ms 100
```

Run CLOB vs FBA phase-2 sweep (PT-014):

```bash
python -m proteus.experiments.run_fba_phase2_sweep --out-dir ./artifacts/phase2 --repetitions 8 --duration-ms 4000 --step-ms 100
```

Run RFQ phase-3 sweep (PT-016):

```bash
python -m proteus.experiments.run_rfq_phase3_sweep --out-dir ./artifacts/phase3 --repetitions 8 --duration-ms 4000 --step-ms 100
```

Run gated dual-flow phase-4 report (PT-017):

```bash
poetry run proteus-exp run phase4 --out-dir ./artifacts/phase4 --phase2-report ./artifacts/phase2/pt014_phase2_delta_sweep_v1/phase2_delta_sweep_report.json --phase3-report ./artifacts/phase3/pt016_rfq_phase3_sweep_v1/rfq_phase3_sweep_report.json --preset quick
```

Override example with unified CLI:

```bash
poetry run proteus-exp run phase3 --out-dir ./artifacts/phase3 --preset ci --dealer-count-grid 1,2,3 --version-tag ci-plus
```

Progress behavior:
- `phase3` shows progress by default for sweep cells
- disable with `--no-progress` when running in quiet logs/CI

Run tests:

```bash
poetry run pytest -q
```

Lint:

```bash
poetry run ruff check .
```

Format:

```bash
poetry run ruff format .
```

## Project Map

Core modules:
- `proteus/core`: config, clock, RNG, events, smoke
- `proteus/info`: latent process and signal models
- `proteus/agents`: agent interfaces and v1 MM/informed/noise implementations
- `proteus/mechanisms`: mechanism interface plus implemented CLOB/FBA/RFQ baselines
- `proteus/execution`: latency and leakage policies
- `proteus/metrics`: recorder, metric calculations, artifact schema
- `proteus/experiments`: scenarios, runner/parity hooks, calibration, baseline pack, phase-2 and phase-3 sweep analysis tooling

Planning docs:
- `docs/planning/PROTEUS_ARCHITECTURE_ROADMAP.md`
- `docs/planning/PROTEUS_TICKETS.md`
- `docs/planning/PROTEUS_BUILD_LOG.md`
- `docs/planning/PROTEUS_RESEARCH_NOTES.md`

## Design Principles

- Mechanism-pluggable by construction: agents emit intents, mechanisms emit fills.
- Determinism first: common random numbers and replayable event ordering.
- Accounting integrity first: cash/inventory/PnL invariants before analysis claims.
- Treatment parity first: only mechanism changes unless explicitly swept.

## What You Can Research Now

With current implementation, you can run CLOB-only baseline research sweeps on:
- MM viability under informed-flow and latency regimes
- adverse selection, spread, and execution-quality sensitivity
- reproducible Monte Carlo comparisons with confidence intervals/effect sizes

You can also run cross-mechanism comparisons on:
- CLOB vs FBA batch-interval sweeps with parity-checked configs and CI summaries
- RFQ TTL/latency/dealer competition sweeps with protection-vs-discovery and protection-vs-speed frontiers

Next major step:
- `PT-018`: statistical power and Monte Carlo budget policy.
