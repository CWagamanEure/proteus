# Proteus Research Notes (Longitudinal Agents + Lending)

## Purpose
Capture near-term research design requirements so implementation work stays aligned with econometric questions.

## A. Longitudinal agent identity

### Core hypotheses
- H1: Agent performance persistence differs by mechanism (CLOB/FBA/RFQ).
- H2: Mechanism ranking changes when agents adapt with memory across episodes.
- H3: Capital path dependence amplifies winner-take-most dynamics under latency shocks.

### Required data fields
- `agent_uid` (stable across runs)
- `run_index`, `cohort_id`, `seed`, `mechanism_name`
- carryover policy (`hard_reset`, `capital_only`, `full_carryover`)
- per-agent starting/ending capital
- per-agent diagnostic metrics (EV error, calibration, regret stubs)

### Minimal identification strategy
- Common random numbers across mechanisms and carryover policies.
- Hold strategy family fixed; vary mechanism first.
- Use panel estimators with agent fixed effects for persistence claims.

## B. Lending market extension

### Core hypotheses
- H4: Leverage increases adverse selection and spread under information shocks.
- H5: Liquidation policy shape (threshold + penalty) materially changes volatility tails.
- H6: Some mechanisms are more resilient to deleveraging cascades than others.

### Required state/event extensions
- Credit account: cash, collateral, debt, health factor.
- Events: borrow, lend, repay, accrue_interest, margin_call, liquidate.
- Policy metadata: rate curve ID, liquidation rule ID.

### Minimal stress scenarios
- Collateral jump down with high utilization.
- Borrow-demand spike with thin lender depth.
- Correlated liquidation wave under latency stress.

## C. Sequencing guidance

1. Land persistent identity and carryover (`PT-031`, `PT-032`) before substantive adaptation claims.
2. Land panel artifact schema (`PT-033`) before large sweeps.
3. Land credit ledger and policy engine (`PT-034` to `PT-036`) before cross-market welfare claims.
4. Add lending regression suite (`PT-037`) before publishing mechanism comparisons under leverage.

## D. Guardrails
- Do not mix strategy upgrades with mechanism changes in one sweep.
- Keep schema versions explicit and bump on any field semantics change.
- Predefine primary endpoint per study to avoid metric-shopping.
