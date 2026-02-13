# Proteus

Proteus is a mechanism-pluggable market microstructure simulation framework.

The goal is to run controlled, reproducible experiments where mechanism design is the treatment variable:
- CLOB vs frequent batch auctions vs RFQ (and later hybrids)
- shared seeds and information paths across runs
- comparable accounting, execution, and metrics outputs

Today, Proteus is in foundation mode: core simulation contracts are in place, and early validation pieces are implemented.

## Why Proteus

Proteus is built for interesting economics questions like:
- How much adverse selection changes when you switch matching mechanisms?
- When does a market maker survive or fail under informed flow + latency?
- Which market design gives better spread/fill/price-discovery tradeoffs?
- How do incentive policy changes shift behavior (post-MVP roadmap)?

## Current Status

Implemented now:
- Deterministic RNG stream manager with subsystem isolation
- Event clock + typed event model + deterministic replay helpers
- Fill accounting engine with reconciliation/invariant checks
- Bounded latent process and heterogeneous signal model
- Canonical run artifact bundle export (`json`, `jsonl`, `csv`, optional parquet)
- Smoke runner wiring for core module initialization

Still scaffold/placeholder:
- Mechanism internals (`clob`, `fba`, `rfq`) are mostly stubs
- Agent strategy logic is minimal
- Full experiment analysis stack is in progress

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
- `proteus/agents`: agent interfaces and baseline agent stubs
- `proteus/mechanisms`: mechanism interface and mechanism stubs
- `proteus/execution`: latency and leakage policies
- `proteus/metrics`: recorder, metric calculations, artifact schema
- `proteus/experiments`: scenarios, runner, analysis hooks

Planning docs:
- `docs/planning/PROTEUS_ARCHITECTURE_ROADMAP.md`
- `docs/planning/PROTEUS_TICKETS.md`
- `docs/planning/PROTEUS_BUILD_LOG.md`

## Design Principles

- Mechanism-pluggable by construction: agents emit intents, mechanisms emit fills.
- Determinism first: common random numbers and replayable event ordering.
- Accounting integrity first: cash/inventory/PnL invariants before analysis claims.
- Treatment parity first: only mechanism changes unless explicitly swept.
