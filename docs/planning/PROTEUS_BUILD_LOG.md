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

### 2026-02-13
- Ticket: PT-009
- Definition of done:
  - Implement configurable submission/ack/fill latency primitives with reproducible seeded behavior.
  - Implement explicit mechanism leakage policy with public/private field visibility mapping.
  - Add parity tests ensuring shared default latency/leakage primitives across CLOB/FBA/RFQ.
- Test(s) to run:
  - `poetry run pytest -q tests/test_execution_models.py`
  - `poetry run pytest -q`
  - `poetry run ruff check .`
- What changed:
  - Extended `proteus/execution/latency.py` with latency profiles, ack-delay support, configurable seeded model, and default parity builder.
  - Extended `proteus/execution/leakage.py` with mechanism-aware visibility/payload filtering and default/private policy builders.
  - Added PT-009 regression coverage in `tests/test_execution_models.py`.
- What broke / risks:
  - Leakage policy is field-based and event-payload driven; richer channel semantics (for example venue-specific metadata redaction) remain future work.
  - Latency is modeled as bounded additive jitter; heavier-tailed queue/network delay models are not yet implemented.
- Next ticket: PT-010

### 2026-02-19
- Ticket: PT-010
- Definition of done:
  - Implement CLOB calibration harness that searches MM parameter regimes under low informed intensity.
  - Generate calibration report with selected regime and explicit rationale.
  - Include sensitivity diagnostics across informed activity and latency grids.
- Test(s) to run:
  - `poetry run pytest -q tests/test_clob_calibration.py`
  - `poetry run pytest -q`
  - `poetry run ruff check .`
  - `python -m proteus.experiments.calibrate_clob --out-dir /tmp/proteus-pt010-check --duration-ms 2000 --step-ms 100`
- What changed:
  - Added calibration harness in `proteus/experiments/calibration.py` with candidate search, stability checks, and sensitivity sweeps.
  - Added CLI entrypoint in `proteus/experiments/calibrate_clob.py`.
  - Added regression tests in `tests/test_clob_calibration.py`.
- What broke / risks:
  - Calibration uses a lightweight event loop and heuristic objective for regime selection; methodology can be refined when PT-011 experiment pack formalizes endpoints.
  - Runtime scales with grid size and seed count; wider sweeps may require batching controls.
- Next ticket: PT-011

### 2026-02-19
- Ticket: PT-011
- Definition of done:
  - Implement CLOB baseline experiment pack runner that consumes the calibrated regime and executes Monte Carlo grid sweeps.
  - Emit confidence intervals and effect-size summaries for baseline contrasts.
  - Provide reproducible CLI command and artifact outputs (JSON + CSV).
- Test(s) to run:
  - `poetry run pytest -q tests/test_baseline_pack.py tests/test_clob_calibration.py`
  - `poetry run pytest -q`
  - `poetry run ruff check .`
  - `python -m proteus.experiments.run_clob_baseline_pack --out-dir /tmp/proteus-pt011-final-check --repetitions 6 --duration-ms 2000 --step-ms 100`
- What changed:
  - Added baseline pack runner in `proteus/experiments/baseline_pack.py` with calibration handoff, seeded repetitions, CI/effect-size summaries, and CSV/JSON artifact writing.
  - Added CLI entrypoint `proteus/experiments/run_clob_baseline_pack.py`.
  - Expanded regression coverage in `tests/test_baseline_pack.py` and `tests/test_clob_calibration.py` for seed metadata fidelity, report path serialization, latency sensitivity behavior, and output invariants.
- What broke / risks:
  - Latency sensitivity for very small delays can be muted when delays are below the decision step resolution; default latency grids now include multi-step values to preserve diagnostic signal.
  - Metric summaries remain tied to current simplified agent/mechanism dynamics and should be interpreted as baseline diagnostics before cross-mechanism parity work.
- Next ticket: PT-012

### 2026-02-26
- Ticket: PT-012
- Definition of done:
  - Implement FBA batch collection and fixed-interval clears.
  - Implement uniform clearing price selection with configurable tie policy.
  - Implement selectable allocation policies and deterministic fixtures/tests.
- Test(s) to run:
  - `poetry run pytest -q tests/test_fba_mechanism.py`
  - `poetry run pytest -q`
  - `poetry run ruff check .`
- What changed:
  - Added `FBAMechanism` in `proteus/mechanisms/fba.py` with batch interval clearing, uniform-price selection, tie policies, and allocation policies.
  - Added PT-012 regression coverage in `tests/test_fba_mechanism.py`.
  - Wired FBA mechanism construction in `proteus/experiments/runner.py`.
- What broke / risks:
  - FBA implementation is baseline-only (no advanced auction priority/rounding variants beyond current selectable policies).
  - Batch clearing emits fills only; richer batch-level auction events/diagnostics can be added later if analysis requires them.
- Next ticket: PT-013

### 2026-02-26
- Ticket: PT-013
- Definition of done:
  - Add parity preflight checks for cross-mechanism scenario comparisons.
  - Fail with exact differing config keys when parity contract is violated.
  - Integrate preflight into mechanism runner path and cover with tests.
- Test(s) to run:
  - `poetry run pytest -q tests/test_mechanism_parity.py`
  - `poetry run pytest -q`
  - `poetry run ruff check .`
- What changed:
  - Added parity diff/assert helpers in `proteus/experiments/parity.py`.
  - Integrated optional parity preflight into `proteus/experiments/runner.py` via `build_mechanism(..., parity_reference=...)`.
  - Added PT-013 regression coverage in `tests/test_mechanism_parity.py`.
- What broke / risks:
  - Parity contract intentionally ignores `scenario_id` and `mechanism.*`; future experiments may need a stricter/parameterized parity policy.
  - Diff output is key-path based and does not currently summarize value deltas beyond path names.
- Next ticket: PT-014

### 2026-02-26
- Ticket: PT-014
- Definition of done:
  - Run CLOB vs FBA delta sweep over configured batch intervals with shared seeds.
  - Emit AS loss/spread/fill-delay/RMSE comparison outputs with CI summaries.
  - Persist versioned JSON + CSV artifacts for phase-2 analysis.
- Test(s) to run:
  - `poetry run pytest -q tests/test_fba_phase2_sweep.py`
  - `poetry run pytest -q`
  - `poetry run ruff check .`
- What changed:
  - Added phase-2 sweep module in `proteus/experiments/fba_phase2_sweep.py` with calibrated baseline handoff and delta-grid comparisons.
  - Added CLI entrypoint `proteus/experiments/run_fba_phase2_sweep.py`.
  - Added PT-014 regression tests in `tests/test_fba_phase2_sweep.py`.
- What broke / risks:
  - Report-level significance notes are heuristic summaries and should not be treated as formal hypothesis-test output.
  - Runtime grows with repetition count and delta grid size; wider sweeps may require PT-039 parallel execution.
- Next ticket: PT-015

### 2026-02-27
- Ticket: PT-015
- Definition of done:
  - Implement RFQ request -> quote -> accept pipeline.
  - Enforce request/quote TTL and response latency constraints.
  - Support multi-dealer quote competition and request/quote cancellation handling.
- Test(s) to run:
  - `poetry run pytest -q tests/test_rfq_mechanism.py`
  - `poetry run pytest -q`
  - `poetry run ruff check .`
- What changed:
  - Replaced RFQ stub with concrete implementation in `proteus/mechanisms/rfq.py`.
  - Added RFQ intent dataclasses and queued-action clearing flow for deterministic request/quote/accept processing.
  - Added PT-015 regression coverage in `tests/test_rfq_mechanism.py`.
  - Updated mechanism factory wiring in `proteus/experiments/runner.py` to pass RFQ params through scenario config.
- What broke / risks:
  - Current RFQ implementation is baseline and intentionally minimal (single-accept closure, no partial multi-accept lifecycle).
  - Leakage/privacy validation is currently indirect via existing leakage policy; deeper RFQ event-level privacy assertions remain follow-on work.
- Next ticket: PT-016

### 2026-03-06
- Ticket: PT-016
- Definition of done:
  - Implement RFQ sweep runner over request TTL, response latency, and dealer-count grids with shared seeds.
  - Compare RFQ outputs against calibrated CLOB baseline and emit CI/effect-style delta summaries.
  - Emit tradeoff frontier artifacts and reproducibility metadata for sweep reports.
- Test(s) to run:
  - `poetry run pytest -q tests/test_rfq_phase3_sweep.py`
  - `poetry run pytest -q`
  - `poetry run ruff check .`
- What changed:
  - Added PT-016 sweep/analysis module in `proteus/experiments/rfq_phase3_sweep.py` with calibrated baseline handoff, deterministic RFQ simulation, CI summaries, and Pareto-style frontiers.
  - Added CLI entrypoint `proteus/experiments/run_rfq_phase3_sweep.py`.
  - Added PT-016 regression coverage in `tests/test_rfq_phase3_sweep.py` including artifacts, reproducibility, frontier correctness, config validation, and CLI smoke checks.
- What broke / risks:
  - RFQ sweep simulation uses a stylized request/quote/accept flow intended for scenario-comparison baselines; richer requestor/dealer strategy models remain future work.
  - Frontier significance remains CI-based summary diagnostics rather than formal hypothesis-test inference.
- Next ticket: PT-017

### 2026-03-06
- Ticket: PT-017
- Definition of done:
  - Enforce PT-014/PT-016 gate checks before allowing dual-flow mechanism construction.
  - Implement dual-flow batch mechanism with separate buy/sell clears and no maker-maker matching.
  - Emit a comparative phase-4 report only after gate satisfaction.
- Test(s) to run:
  - `poetry run pytest -q tests/test_dual_flow_batch_mechanism.py tests/test_dual_flow_phase4_report.py tests/test_experiments_cli.py`
  - `poetry run pytest -q`
  - `poetry run ruff check .`
- What changed:
  - Added `DualFlowBatchMechanism` in `proteus/mechanisms/dual_flow_batch.py` with maker/taker segregation, separate flow clears, and deterministic matching.
  - Added dual-flow gate enforcement in `proteus/experiments/runner.py` for mechanism name `dual_flow_batch` requiring `scenario.params.dual_flow_gate` with `phase2_passed=True` and `phase3_passed=True`.
  - Added gated comparative report runner in `proteus/experiments/dual_flow_phase4_report.py` and CLI entrypoint `proteus/experiments/run_dual_flow_phase4_report.py`.
  - Extended unified CLI `proteus-exp` with `run phase4` and required gate-report arguments.
  - Added PT-017 regression coverage in `tests/test_dual_flow_batch_mechanism.py`, `tests/test_dual_flow_phase4_report.py`, and extended `tests/test_experiments_cli.py`.
- What broke / risks:
  - Dual-flow gating currently keys on presence of non-empty PT-014/PT-016 report rows; stricter statistical quality gates (for example CI/power thresholds) remain future policy work.
  - Dual-flow comparative fixture is a deterministic sanity fixture, not a full-scale economic study harness.
- Next ticket: PT-018
