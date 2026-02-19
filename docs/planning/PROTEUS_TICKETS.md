# Proteus Ticket Backlog (derived from `PROTEUS_ARCHITECTURE_ROADMAP.md`)

## Milestone framing
- M0: Foundation + validation harness (must pass before mechanism comparisons)
- M1: CLOB baseline with stable MM and trustworthy metrics
- M2: Frequent batch auction comparisons (apples-to-apples)
- M3: RFQ comparisons and optional dual-flow extension

## Ticket Template Used
- Problem
- Scope (in/out)
- Acceptance criteria
- Dependencies
- Estimate

## M0: Foundation + Validation

### PT-001: Repository skeleton + module contracts
- Status: complete (2026-02-10)
- Problem: The roadmap defines modules, but no enforceable interfaces.
- Scope: Create package layout and abstract interfaces for `agents`, `mechanisms`, `metrics`, and event schemas.
- Acceptance criteria:
  - Directory structure matches roadmap modules.
  - Base interfaces compile and include type hints.
  - A simple smoke run initializes all core modules.
- Dependencies: none
- Estimate: M

### PT-002: Deterministic RNG stream manager
- Status: complete (2026-02-10)
- Problem: Common random numbers are required for fair treatment comparisons.
- Scope: Implement seeded stream manager with child streams per subsystem (`latent`, `agents`, `latency`, etc.).
- Acceptance criteria:
  - Same seed reproduces identical event log and metrics.
  - Changing one subsystem stream does not perturb others.
  - Documented seed protocol for experiments.
- Dependencies: PT-001
- Estimate: M

### PT-003: Time engine and event model
- Status: complete (2026-02-12)
- Problem: Simulation semantics (event-driven vs hybrid) are currently implicit.
- Scope: Implement clock + typed events (`news`, `order`, `fill`, `batch_clear`, `rfq_request`, `rfq_quote`, `rfq_accept`).
- Acceptance criteria:
  - Event ordering rules are codified and tested.
  - Timestamp precision and tie-break policy are explicit.
  - Replay from event log reconstructs state.
- Dependencies: PT-001, PT-002
- Estimate: M

### PT-004: Accounting and invariant checks
- Status: complete (2026-02-12)
- Problem: Incorrect PnL/inventory accounting can invalidate all conclusions.
- Scope: Build accounting engine and invariant test suite.
- Acceptance criteria:
  - Cash/inventory/PnL reconciliation tests pass.
  - Zero-sum transfer checks pass per trade.
  - Failure reports isolate violating event IDs.
- Dependencies: PT-003
- Estimate: M

### PT-005: Latent information process (`p_t`) + signal model
- Status: complete (2026-02-12)
- Problem: Core information model exists on paper but not in code.
- Scope: Implement bounded log-odds process with noise + jumps and per-agent delayed/noisy observations.
- Acceptance criteria:
  - `p_t in [0,1]` always.
  - Jump/noise/mean-reversion toggles configurable.
  - Signal delay/noise heterogeneity covered by tests.
- Dependencies: PT-002, PT-003
- Estimate: M

### PT-006: Metrics recorder and canonical output schema
- Status: complete (2026-02-12)
- Problem: Metrics are listed, but output format is undefined.
- Scope: Implement mechanism-agnostic recorder and standardized result schema (per-run JSON/Parquet + summary table).
- Acceptance criteria:
  - Event log and derived metrics serialize with stable schema version.
  - All non-negotiable metrics in roadmap are emitted.
  - One command generates run artifact bundle.
- Dependencies: PT-003, PT-004
- Estimate: M

## M1: CLOB Baseline

### PT-007: CLOB matching engine (price-time priority)
- Status: complete (2026-02-13)
- Problem: Baseline mechanism needed before treatment comparisons.
- Scope: Continuous matching, queue state, partial fills, cancels, and queue-position-aware fills.
- Acceptance criteria:
  - Price-time priority tests pass.
  - Queue position affects fill outcomes as expected.
  - Edge cases (crossed books, partials, cancel race) tested.
- Dependencies: PT-003
- Estimate: L

### PT-008: Agent v1 implementations (MM, informed, noise)
- Status: complete (2026-02-13)
- Problem: Comparative experiments need consistent strategy definitions.
- Scope: Implement v1 behavior specs from roadmap with shared policy interfaces.
- Acceptance criteria:
  - MM reservation/spread equations implemented and configurable.
  - Informed trader thresholding and size scaling implemented.
  - Noise trader Poisson arrivals + random side/size implemented.
- Dependencies: PT-005, PT-007
- Estimate: L

### PT-009: Execution latency + leakage primitives
- Status: complete (2026-02-13)
- Problem: Execution assumptions must be common across mechanisms.
- Scope: Implement configurable submission/ack/fill latency and explicit leakage model.
- Acceptance criteria:
  - Latency distributions parameterized and reproducible.
  - Leakage channels (public/private fields) explicitly mapped by mechanism.
  - Tests verify same primitive defaults applied to all mechanisms.
- Dependencies: PT-003
- Estimate: M

### PT-010: CLOB calibration harness
- Status: complete (2026-02-19)
- Problem: Need calibrated baseline where MM survives under low informed intensity.
- Scope: Build parameter search and diagnostics for survival region.
- Acceptance criteria:
  - Finds at least one stable parameter regime meeting survival criteria.
  - Produces calibration report with chosen parameters and rationale.
  - Report includes sensitivity to informed intensity + latency.
- Dependencies: PT-006, PT-008, PT-009
- Estimate: M

### PT-011: CLOB baseline experiment pack
- Problem: Phase 1 roadmap requires benchmark outputs.
- Scope: Scenario definitions, Monte Carlo runner, CI summaries for baseline contrasts.
- Acceptance criteria:
  - Runs batched simulations over defined grid.
  - Outputs confidence intervals and effect sizes.
  - Repro command documented.
- Dependencies: PT-010
- Estimate: M

## M2: Frequent Batch Auction

### PT-012: FBA mechanism implementation
- Problem: Phase 2 requires auction clearing with configurable interval/allocation.
- Scope: Batch collection, uniform clearing, tie/allocation policies.
- Acceptance criteria:
  - Clearing price logic validated on deterministic fixtures.
  - Supports `Delta` sweep in roadmap values.
  - Allocation policy variants selectable via config.
- Dependencies: PT-003
- Estimate: L

### PT-013: CLOB vs FBA parity test harness
- Problem: Comparisons are invalid without treatment parity checks.
- Scope: Automated assertions that all non-mechanism parameters are identical between runs.
- Acceptance criteria:
  - Fails run when parity contract is violated.
  - Logs exact differing config keys.
  - Integrated into experiment runner preflight.
- Dependencies: PT-011, PT-012
- Estimate: M

### PT-014: Phase 2 sweep + analysis
- Problem: Need treatment contrast across batch intervals.
- Scope: Execute `Delta in {50,100,250,500,1000}` sweep with common seeds.
- Acceptance criteria:
  - Produces AS loss/spread/fill delay/RMSE comparison tables.
  - Includes CIs and significance notes.
  - Artifacts saved in versioned experiment folder.
- Dependencies: PT-013
- Estimate: M

## M3: RFQ + Optional Dual-Flow

### PT-015: RFQ mechanism implementation
- Problem: Phase 3 requires private quote/accept pipeline.
- Scope: RFQ request, dealer response, TTL expiry, acceptance path.
- Acceptance criteria:
  - TTL and response latency are enforced by engine.
  - Private information path respected by leakage model.
  - Multi-dealer competition configuration supported.
- Dependencies: PT-003, PT-009
- Estimate: L

### PT-016: RFQ scenario sweeps + analysis
- Problem: Need protection vs price-discovery tradeoff measurement.
- Scope: Sweep TTL/latency/dealer competition parameters and compare against baseline.
- Acceptance criteria:
  - Outputs tradeoff frontiers for key metrics.
  - Includes confidence intervals and reproducibility metadata.
  - Contrasts use same seed sets as other mechanisms.
- Dependencies: PT-015
- Estimate: M

### PT-017: Dual-flow batch (optional, gated)
- Problem: Advanced mechanism should not begin before parity in earlier phases.
- Scope: Implement only if M1-M3 parity gates pass.
- Acceptance criteria:
  - Gate check enforced in runner.
  - Separate buy/sell clears and no maker-maker matching implemented.
  - Comparative report generated only after gate satisfied.
- Dependencies: PT-014, PT-016
- Estimate: L

## Cross-cutting quality tickets

### PT-018: Statistical power and Monte Carlo budget policy
- Problem: Roadmap calls for CIs but not required sample size/power targets.
- Scope: Define minimum run counts and stopping rules.
- Acceptance criteria:
  - Documented policy for CI width targets.
  - Runner can continue until precision criterion is met.
  - Reports include achieved precision diagnostics.
- Dependencies: PT-011
- Estimate: M

### PT-019: Regression suite for mechanism sanity cases
- Problem: Roadmap mentions sanity checks but no permanent regression set.
- Scope: Encode deterministic scenario fixtures for each mechanism.
- Acceptance criteria:
  - CI runs full sanity suite.
  - Golden outputs versioned and diffed.
  - Failure triage points to changed invariants.
- Dependencies: PT-007, PT-012, PT-015
- Estimate: M

### PT-020: Experiment CLI and runbook
- Problem: Reproducibility depends on standardized execution workflow.
- Scope: CLI for run/compare/report + concise runbook.
- Acceptance criteria:
  - One command to run each phase.
  - Run metadata captures git SHA, config hash, seed set.
  - Runbook includes troubleshooting and expected runtime.
- Dependencies: PT-011, PT-014, PT-016
- Estimate: S

## Issues found in the current roadmap (and fixes)

### 1) Missing explicit objective function
- Issue: The plan lists many metrics but no decision rule for choosing “better.”
- Risk: Conflicting conclusions across metrics.
- Fix ticket mapping: PT-011, PT-014, PT-016 should include a primary endpoint definition (for example, AS reduction at fixed fill-delay budget).

### 2) Ambiguous time semantics and unit mapping
- Issue: `Delta` is specified as ms-equivalent but no simulation clock/unit conversion standard is defined.
- Risk: Inconsistent latency vs batch-interval interpretation across mechanisms.
- Fix ticket mapping: PT-003 and PT-012 must define canonical time units and conversion rules.

### 3) Incomplete parity contract across mechanisms
- Issue: “Same latency and signal primitives” is stated but not enforceable.
- Risk: Hidden confounds in treatment comparisons.
- Fix ticket mapping: PT-013 enforces preflight parity checks with hard failures.

### 4) No statistical power criteria
- Issue: CIs are requested but minimum Monte Carlo counts are not specified.
- Risk: Underpowered claims and unstable rankings.
- Fix ticket mapping: PT-018.

### 5) Potential confound from mechanism-specific MM adaptation timing
- Issue: Roadmap warns about this but has no explicit gating policy.
- Risk: Strategy changes absorb mechanism effects.
- Fix ticket mapping: PT-008 should freeze common strategy defaults for all phase-comparison runs; mechanism-specific adaptations only after baseline reports.

### 6) Output schema/versioning not defined
- Issue: Metrics are listed without schema governance.
- Risk: Analysis breakage and irreproducible historical comparisons.
- Fix ticket mapping: PT-006 with schema versioning and compatibility checks.

### 7) Queue-position realism only noted in pitfalls
- Issue: CLOB fairness claims depend on queue modeling details.
- Risk: Biased CLOB baseline vs batch mechanisms.
- Fix ticket mapping: PT-007 includes queue-position-aware fill logic and tests.

## Suggested execution order (first 8 tickets)
1. PT-001
2. PT-002
3. PT-003
4. PT-004
5. PT-005
6. PT-006
7. PT-007
8. PT-008

## M4: Post-MVP DeFi + RL Extensions

### PT-021: Mechanism cost model abstraction
- Problem: Fee/gas/rebate assumptions are currently implicit and mechanism-specific.
- Scope: Add `MechanismCostModel` abstraction for fees, gas, rebates, and policy-adjustable execution costs.
- Acceptance criteria:
  - Cost model is mechanism-agnostic and injected via config.
  - Per-fill cost attribution is recorded in artifacts.
  - Regression tests verify deterministic cost accounting by seed.
- Dependencies: PT-006, PT-009
- Estimate: M

### PT-022: Settlement model abstraction (internal vs on-chain style)
- Problem: Current accounting assumes immediate final settlement.
- Scope: Add pluggable `SettlementModel` for delayed/final settlement semantics and settlement-state transitions.
- Acceptance criteria:
  - Supports immediate and delayed settlement modes.
  - Accounting reconciles correctly under delayed settlement.
  - Event log captures settlement lifecycle events.
- Dependencies: PT-004, PT-006, PT-021
- Estimate: M

### PT-023: Incentive policy engine
- Problem: Token incentives (emissions, staking rewards, penalties) are not represented.
- Scope: Add `IncentivePolicy` module supporting time-varying rewards/penalties and policy schedules.
- Acceptance criteria:
  - Policy schedules can be configured per scenario.
  - Incentive transfers are ledgered and auditable in artifacts.
  - Scenario sweeps can vary policy without changing mechanism code.
- Dependencies: PT-004, PT-006, PT-021
- Estimate: L

### PT-024: Agent policy interface split (strategy vs risk/capital constraints)
- Problem: Agent strategy and capital constraints are coupled, limiting reuse and fair comparisons.
- Scope: Separate agent decision policy from risk/capital constraint policy.
- Acceptance criteria:
  - Existing agent implementations migrate to split interfaces with no behavior regressions.
  - Same strategy can run under multiple risk/capital policies.
  - Unit tests cover constraint enforcement edge cases.
- Dependencies: PT-008
- Estimate: M

### PT-025: Environment state extensions for DeFi microstructure
- Problem: Oracle/mempool/block cadence state is missing from environment context.
- Scope: Add optional `EnvironmentState` channels (oracle state, mempool visibility, block timing, congestion).
- Acceptance criteria:
  - State channels are explicitly versioned in schema.
  - Agents can subscribe to selected channels without mechanism coupling.
  - Determinism tests confirm identical environment traces for equal seeds.
- Dependencies: PT-003, PT-005, PT-006
- Estimate: L

### PT-026: MM strategy lab (filters + quoting policy plugins)
- Problem: MM strategy variants are not modular enough for controlled comparisons.
- Scope: Add plugin-style MM filters (EWMA/Kalman) and quoting/risk policy modules.
- Acceptance criteria:
  - MM filters and quote policies are swappable via config.
  - Baseline strategy can be frozen while testing one policy dimension at a time.
  - Output artifacts include active strategy/policy metadata.
- Dependencies: PT-008, PT-024
- Estimate: M

### PT-027: RL environment API + offline dataset export
- Problem: No standardized interface exists for RL/self-play training.
- Scope: Add environment API (`observe`, `act`, `step`) and trajectory export for offline RL.
- Acceptance criteria:
  - Rule-based and RL agents can run through the same policy interface.
  - Trajectory datasets export with schema versioning and seed metadata.
  - Deterministic replay validates action/state trajectory parity.
- Dependencies: PT-006, PT-024, PT-025
- Estimate: L

### PT-028: Competition runner and leaderboard scoring
- Problem: There is no canonical framework to compare many agent policies across mechanisms.
- Scope: Build `CompetitionRunner` with season config, deterministic scenario packs, and scoring tables.
- Acceptance criteria:
  - Supports multi-agent matchups with fixed seed sets.
  - Produces leaderboard outputs by profitability, market quality, and robustness.
  - CI job runs a reduced competition smoke suite.
- Dependencies: PT-011, PT-019, PT-026, PT-027
- Estimate: M

### PT-029: Policy sweep runner for incentive/mechanism A/B
- Problem: Governance-style “change one rule and measure impact” workflows are manual.
- Scope: Add policy sweep tooling for mechanism and incentive parameter A/B experiments.
- Acceptance criteria:
  - One command runs an A/B sweep with common seeds.
  - Reports include winner/loser decomposition and risk diagnostics.
  - Sweep metadata includes config hashes and policy version IDs.
- Dependencies: PT-018, PT-023, PT-028
- Estimate: M

### PT-030: Stress and manipulation scenario suite
- Problem: Robustness against adversarial behavior is not encoded as regression tests.
- Scope: Add deterministic stress fixtures (oracle lag, latency spikes, spoof-like bursts, liquidity droughts).
- Acceptance criteria:
  - Stress suite runs in CI with golden-output diffing.
  - Failures identify violated invariants and scenario IDs.
  - Reports include robustness deltas per mechanism/policy.
- Dependencies: PT-019, PT-025, PT-028
- Estimate: M

## M5: Longitudinal Identity + Lending Market Research

### PT-031: Persistent agent identity and profile schema
- Problem: Current runs treat agents as stateless per-episode entities, limiting longitudinal analysis.
- Scope: Add stable `agent_uid` and versioned profile schema separate from per-run instance IDs.
- Acceptance criteria:
  - Agent identity fields persist across repeated runs in artifact metadata.
  - Profile schema includes strategy family, risk envelope, and capital baseline.
  - Identity/profile schema version is explicit and validated at load time.
- Dependencies: PT-006, PT-008
- Estimate: M

### PT-032: Cross-run state carryover engine
- Problem: There is no controlled way to retain agent state between runs.
- Scope: Implement carryover policies (`hard_reset`, `capital_only`, `full_carryover`) with deterministic state transitions.
- Acceptance criteria:
  - Carryover policy selectable per experiment config.
  - Same seed + same carryover policy reproduces identical multi-run trajectories.
  - State snapshots are serialized and replayable between episodes.
- Dependencies: PT-031
- Estimate: L

### PT-033: Longitudinal panel artifact bundle + metrics
- Problem: Existing artifacts are run-local and do not support panel regressions.
- Scope: Extend output schema for panel indexing and longitudinal metrics.
- Acceptance criteria:
  - Artifacts include run index, cohort ID, agent UID, and carryover policy metadata.
  - Panel-ready exports (agent-run rows) are emitted in canonical schema.
  - Longitudinal metrics include persistence and regime-shift diagnostics.
- Dependencies: PT-031, PT-032
- Estimate: M

### PT-034: Credit account and collateral ledger abstractions
- Problem: Lending behavior cannot be modeled with spot-only accounting primitives.
- Scope: Add credit account model (`cash`, `collateral`, `debt`, `health_factor`) and ledger events.
- Acceptance criteria:
  - Credit account state reconciles with spot ledger and settlement logic.
  - Borrow/repay/collateral transfer events are versioned in event schema.
  - Invariant checks include debt conservation and collateral consistency.
- Dependencies: PT-004, PT-022
- Estimate: L

### PT-035: Lending mechanism interface + baseline implementation
- Problem: No mechanism contract exists for lending market interactions.
- Scope: Add mechanism interface for borrow/lend requests, matching/allocation, and repayment handling.
- Acceptance criteria:
  - Baseline lending mechanism runs with deterministic matching/allocation policy.
  - Borrow/lend event flow is integrated into runner and recorder.
  - Edge cases (insufficient collateral, partial fills, expired offers) are tested.
- Dependencies: PT-003, PT-034
- Estimate: L

### PT-036: Interest-rate and liquidation policy engine
- Problem: Credit dynamics require explicit rate and liquidation rules to be economically meaningful.
- Scope: Implement pluggable interest-rate curves and deterministic liquidation policies.
- Acceptance criteria:
  - Interest accrual is reproducible and auditable at event level.
  - Liquidation triggers are deterministic and parameterized.
  - Policy changes are sweepable without modifying mechanism code.
- Dependencies: PT-034, PT-035
- Estimate: M

### PT-037: Lending stress and invariant regression suite
- Problem: Credit systems are fragile without permanent regression coverage.
- Scope: Add deterministic scenarios for utilization spikes, collateral shocks, and liquidation cascades.
- Acceptance criteria:
  - CI runs lending sanity suite with golden outputs.
  - Failures identify violated invariant class and scenario ID.
  - Reports include leverage/liquidation summary diagnostics.
- Dependencies: PT-019, PT-035, PT-036
- Estimate: M

### PT-038: Integrated spot + lending experiment pack
- Problem: Research comparisons require joint-market experiments, not isolated subsystems.
- Scope: Build scenario sweeps combining execution mechanism choice with leverage/credit settings.
- Acceptance criteria:
  - Common-seed comparisons run across spot-only vs leveraged variants.
  - Outputs include market quality + credit risk metrics with CIs.
  - Repro command and runbook entries are documented.
- Dependencies: PT-018, PT-033, PT-037
- Estimate: L
