# Proteus Seed Protocol (PT-002)

## Goal
Guarantee reproducibility and fair cross-mechanism comparisons via common random numbers.

## Rules

1. Scenario-level seed
- Each scenario defines `scenario.seed` as the root seed.

2. Repetition seed
- For repetition index `r`, derive:
  - `rep_seed = derive_repetition_seed(scenario.seed, r)`

3. RNG manager per run
- Initialize exactly one `RNGManager(base_seed=rep_seed)` for each run.

4. Named subsystem streams
- Use stable stream names for each subsystem and entity. Recommended names:
  - `latent`
  - `signal`
  - `latency`
  - `mechanism`
  - `metrics`
  - `agents.<agent_id>`

5. Isolation contract
- Each subsystem draws randomness only from its own named stream.
- Additional draws in one stream must not perturb sequences in other streams.

6. Deterministic ordering
- Iterate entities (for example, agents) in deterministic order (for example, sorted `agent_id`) to avoid accidental non-determinism.

## Cross-mechanism parity requirements
For treatment comparisons, keep the following fixed:
- `scenario.seed`
- repetition indices
- stream names
- draw order in shared components outside mechanism-specific logic

## Current implementation references
- Seed derivation and stream manager: `proteus/core/rng.py`
- RNG behavior tests: `tests/test_rng_manager.py`
