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
