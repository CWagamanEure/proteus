# AGENTS.md

## Purpose
Proteus is a mechanism-pluggable market microstructure simulation framework.
Current state is foundation-plus-baseline: core simulation primitives are implemented, CLOB matching is live, and strategy layers are the main remaining gap.

## Read First
1. `README.md` for basic dev commands.
2. `docs/planning/PROTEUS_ARCHITECTURE_ROADMAP.md` for modeling assumptions and roadmap.
3. `docs/planning/PROTEUS_TICKETS.md` and `docs/planning/PROTEUS_BUILD_LOG.md` for active work tracking.

## Project Layout
- `proteus/core`: configs, clock, RNG, event schemas, smoke harness.
- `proteus/info`: latent process and signal models.
- `proteus/agents`: agent interfaces, placeholder agent classes, and decision-diagnostic schema hooks.
- `proteus/mechanisms`: mechanism interface, implemented CLOB baseline, plus FBA/RFQ stubs.
- `proteus/execution`: latency and information leakage policies.
- `proteus/metrics`: event recorder, metric calculators, and research-metric stubs.
- `proteus/experiments`: scenarios, mechanism factory, analysis hooks.
- `tests`: unit coverage for RNG, events/clock, accounting, info models, metrics recorder, CLOB matching, plus smoke.
- `docs/planning`: architecture, ticket plan, checklist, build log, and research notes.

## Environment
- Python: `>=3.11,<4.0`
- Package manager: Poetry
- Install: `poetry install`
- Run smoke entrypoint: `python -m proteus`
- Run tests: `poetry run pytest`
- Lint: `poetry run ruff check .`
- Format: `poetry run ruff format .`

## Current Architecture Notes
- Core contract separation:
  - agents generate intents
  - mechanisms consume intents and emit fills
  - metrics consume event/fill logs
- Mechanism selection currently lives in `proteus/experiments/runner.py` via `build_mechanism`.
- Smoke flow is wired in `proteus/core/smoke.py` and returns `"smoke-ok"` when initialization succeeds.

## Modeling Assumptions (v1)
Keep these stable unless explicitly changing experiment design:
1. Single binary contract with terminal payoff in `{0,1}`.
2. Latent probability process exists and is unobservable.
3. Agents receive heterogeneous/noisy/delayed signals.
4. Cross-mechanism comparisons should share seeds and information paths.
5. Execution mechanism is the treatment variable unless a sweep says otherwise.

## Contribution Guidance
1. Preserve typed interfaces in `core/events.py`, `agents/base.py`, and `mechanisms/base.py`.
2. Prefer adding behavior behind existing abstractions over ad hoc direct coupling.
3. Keep mechanism-specific behavior inside `proteus/mechanisms/*`, not in agent base classes.
4. Add/expand tests with each behavior change (unit first, then scenario-level where useful).
5. Update planning docs when completing meaningful ticketed work:
   - `docs/planning/PROTEUS_BUILD_LOG.md`
   - `docs/planning/PROTEUS_TICKETS.md`
6. Test quality standard: write tests to enforce correctness requirements and invariants, not to simply confirm the current implementation behavior.

## Known Gaps
- Agent strategies are still minimal/no-op style implementations (PT-008 is next).
- FBA and RFQ mechanism internals are still placeholders.
- Runner/analysis stack for large experiment sweeps is still early.
- Longitudinal identity and lending-market research paths are planned but not implemented (`PT-031+`).

## Good First Implementation Targets
1. Implement `PT-008`: MM/informed/noise agent v1 behavior specs.
2. Add mechanism parity preflight checks (`PT-013`).
3. Extend scenario presets beyond `clob_smoke_scenario`.
4. Add longitudinal identity scaffolding (`PT-031`) for panel-style research.

## Operational Rules for Agents
- Avoid breaking public interfaces without coordinated updates across modules.
- Keep changes small and composable; this repo is still in foundation phase.
- If behavior or assumptions change, update docs in the same change.
