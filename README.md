# Proteus

Proteus is a mechanism-pluggable market microstructure simulation framework.

The goal is to run controlled, reproducible experiments where mechanism design is the treatment variable:
- CLOB vs frequent batch auctions vs RFQ (and later hybrids)
- shared seeds and information paths across runs
- comparable accounting, execution, and metrics outputs

Today, Proteus is in CLOB-baseline experiment mode (through PT-011): core primitives, CLOB matching, v1 agents, calibration, and baseline sweep tooling are implemented.

## Why Proteus

Proteus is built for interesting economics questions like:
- How much adverse selection changes when you switch matching mechanisms?
- When does a market maker survive or fail under informed flow + latency?
- Which market design gives better spread/fill/price-discovery tradeoffs?
- How do incentive policy changes shift behavior (post-MVP roadmap)?

## Current Status

Implemented now (PT-001 to PT-011):
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
- Agent diagnostic schema + research-metric stubs for instrumentation
- Smoke runner wiring for core module initialization

Still scaffold/placeholder:
- FBA and RFQ internals are still stubs
- Cross-mechanism parity/sweep stack is in progress (`PT-012+`)
- Longitudinal identity + lending-market extensions are planned (see M5 / research notes)

## Quickstart

Install:

```bash
poetry install
```

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
- `proteus/mechanisms`: mechanism interface, implemented CLOB baseline, and FBA/RFQ stubs
- `proteus/execution`: latency and leakage policies
- `proteus/metrics`: recorder, metric calculations, artifact schema
- `proteus/experiments`: scenarios, runner hooks, calibration, baseline pack, analysis hooks

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

With current implementation, you can run CLOB-only research sweeps on:
- MM viability under informed-flow and latency regimes
- adverse selection, spread, and execution-quality sensitivity
- reproducible Monte Carlo comparisons with confidence intervals/effect sizes

Next major step:
- `PT-012`: implement FBA internals, then parity/sweep tickets (`PT-013`, `PT-014`) for cross-mechanism studies.
