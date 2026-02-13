# Proteus Build Log

## How to use
- Keep one ticket `in_progress` at a time.
- For each work session, add one entry.
- Keep entries short and concrete.

## Session Template
- Date:
- Ticket:
- Definition of done:
  - 
  - 
  - 
- Test(s) to run:
  - 
- What changed:
  - 
- What broke / risks:
  - 
- Next ticket:

---

## Entries

### 2026-02-10
- Ticket: PT-001
- Definition of done:
  - Create package layout aligned with roadmap modules.
  - Define typed base interfaces for agents, mechanisms, metrics, and core event schemas.
  - Add a smoke entrypoint that initializes core modules.
- Test(s) to run:
  - `python3 -m proteus`
- What changed:
  - Added full `proteus/` package tree with subpackages: `core`, `info`, `agents`, `mechanisms`, `execution`, `metrics`, `experiments`.
  - Added base contracts in `proteus/agents/base.py`, `proteus/mechanisms/base.py`, `proteus/metrics/*.py`, and event types in `proteus/core/events.py`.
  - Added smoke wiring in `proteus/core/smoke.py` and runnable entrypoint in `proteus/__main__.py`.
- What broke / risks:
  - Implementations are stubs; no mechanism logic or strategy behavior exists yet.
  - No test suite yet beyond smoke execution.
- Next ticket: PT-002

### 2026-02-10
- Ticket: PT-002
- Definition of done:
  - Implement deterministic stream manager with named child streams.
  - Add tests for reproducibility, stream isolation, reset behavior, and repetition-seed derivation.
  - Document seed protocol for experiment parity and reproducibility.
- Test(s) to run:
  - `poetry run pytest -q`
  - `poetry run ruff check .`
- What changed:
  - Extended `proteus/core/rng.py` with persistent named streams, child-seed derivation, reset support, and `derive_repetition_seed`.
  - Added RNG validation tests in `tests/test_rng_manager.py`.
  - Added seed protocol documentation in `docs/PROTEUS_SEED_PROTOCOL.md`.
- What broke / risks:
  - End-to-end event-log/metric reproducibility checks remain to be added when runner emits richer artifacts.
- Next ticket: PT-003

### 2026-02-12
- Ticket: PT-006
- Definition of done:
  - Verify recorder emits event/fill logs and derived metrics with stable schema version.
  - Verify non-negotiable metrics are present in the artifact bundle.
  - Verify one command can generate run artifact bundle output.
- Test(s) to run:
  - `poetry run pytest -q tests/test_metrics_recorder.py`
  - `python -m proteus.experiments.export_bundle --out-dir /tmp/proteus-pt006-check --run-id pt006-check`
- What changed:
  - Validated PT-006 acceptance criteria against existing implementation and tests.
  - Marked PT-006 complete in ticket backlog and daily checklist.
- What broke / risks:
  - Parquet output remains optional and depends on local `pandas` + parquet engine availability.
- Next ticket: PT-007

### 2026-02-13
- Ticket: PT-007
- Definition of done:
  - Implement deterministic CLOB matching with price-time priority.
  - Add tests for queue-position effects, partial fills, crossed books, and cancel race behavior.
  - Keep mechanism wiring intact so CLOB can still be selected by runner/smoke paths.
- Test(s) to run:
  - `poetry run pytest -q tests/test_clob_mechanism.py`
  - `poetry run pytest -q`
  - `poetry run ruff check .`
- What changed:
  - Replaced CLOB stub with a concrete order-book matcher in `proteus/mechanisms/clob.py`.
  - Added PT-007 regression tests in `tests/test_clob_mechanism.py`.
- What broke / risks:
  - Matching/price policy is deterministic and minimal; advanced microstructure details (amend/replace, IOC/FOK, hidden orders) are still out of scope.
- Next ticket: PT-008

### 2026-02-13
- Ticket: PT-008
- Definition of done:
  - Implement v1 market maker with configurable reservation price and spread controls.
  - Implement v1 informed trader thresholding with edge-scaled sizing.
  - Implement v1 noise trader Poisson arrivals with random side/size and deterministic seeding.
- Test(s) to run:
  - `poetry run pytest -q tests/test_agents_v1.py`
  - `poetry run pytest -q`
  - `poetry run ruff check .`
- What changed:
  - Replaced agent stubs in `proteus/agents/market_maker.py`, `proteus/agents/informed.py`, and `proteus/agents/noise.py` with PT-008 behavior implementations.
  - Added/validated PT-008 tests in `tests/test_agents_v1.py`.
  - Fixed informed-trader threshold gating and corrected market-maker news-belief update condition.
- What broke / risks:
  - Agent policies are intentionally simple and event-payload-driven; richer state estimation and execution-awareness are deferred to later tickets.
  - Current run loop integration still needs to exercise these agents in full scenario sweeps.
- Next ticket: PT-009
