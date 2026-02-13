# Proteus: System Architecture + Experimental Roadmap

## 1. Modeling stance (v1)
Assumptions for rigor and comparability:

1. Single binary contract, terminal payoff `X in {0,1}`.
2. Latent fundamental probability `p_t in [0,1]` exists and is unobservable.
3. Agents get heterogeneous, delayed, noisy views of `p_t`.
4. Same agent population and information path across mechanisms (common random numbers).
5. Execution mechanism is the only treatment variable unless explicitly swept.

## 2. Core architecture (modular, mechanism-pluggable)

```text
proteus/
  core/
    config.py          # experiment/scenario dataclasses
    clock.py           # event or hybrid time engine
    rng.py             # deterministic RNG stream manager
    events.py          # typed events (news, order, fill, batch_clear)
  info/
    latent_process.py  # p_t dynamics (jump + noise, bounded)
    signal_model.py    # per-agent observation model (delay/noise/partial)
  agents/
    base.py
    market_maker.py
    informed.py
    noise.py
    sniper.py          # optional
  mechanisms/
    base.py            # submit/cancel/quote/clear interface
    clob.py
    fba.py
    rfq.py
    dual_flow_fba.py   # optional advanced
  execution/
    latency.py         # submission/ack/fill delays
    leakage.py         # what info is public/private by mechanism
  metrics/
    recorder.py
    mm_metrics.py
    trader_metrics.py
    market_metrics.py
  experiments/
    scenarios.py       # parameter grids / sweeps
    runner.py          # batched Monte Carlo runs
    analysis.py        # summary tables, CIs, plots
```

Key design rule: `agents` produce order intents, `mechanisms` map intents to fills, `metrics` are mechanism-agnostic consumers of event logs.

## 3. Minimal stochastic information model (not GBM)
Use latent log-odds `x_t`, then `p_t = sigma(x_t)` to enforce bounds.

`x_{t+Delta t} = phi x_t + eta_t + J_t, eta_t ~ N(0, sigma_eta^2 Delta t), J_t = sum_{k=1}^{N_t} Y_k, N_t ~ Poisson(lambda_J Delta t)`

- `Y_k`: signed jump sizes (e.g., mixture of small/large news shocks).
- `phi <= 1`: optional mild mean reversion in log-odds.
- Agent `i` signal:

`s_t^(i) = p_{t-tau_i} + epsilon_t^(i), epsilon_t^(i) ~ N(0, sigma_i^2)`

with clipping to `[0,1]`.

This captures bursty news, bounded probabilities, and heterogeneous informational edge.

## 4. Agent behavior specs (simple, interpretable)

1. Market maker
- Belief `p_hat_t` from public tape (+ optional private filter).
- Reservation price:

`r_t = p_hat_t - kappa_I I_t`

- Half-spread:

`h_t = h_0 + a|I_t| + b sigma_hat_t + c AS_hat_t`

- Quotes: bid `= r_t - h_t`, ask `= r_t + h_t`, clipped to `[0,1]`.
- Risk limits: max inventory, quote pull/widen on breach.

2. Informed trader
- Computes edge from signal vs executable price.
- Trades aggressively if:

`|s_t - p_exec_t| > theta + fees/latency risk term`

- Size increasing in edge magnitude.

3. Noise trader
- Poisson arrivals, random side, random size from fixed distribution.
- Optional weak time clustering.

4. Sniper (optional)
- Monitors stale quotes; submits IOC only when mispricing `> theta_snipe`.
- No passive liquidity provision.

## 5. Mechanism definitions in Proteus

1. CLOB (baseline): continuous matching, price-time priority.
2. Frequent Batch Auction: collect over interval `Delta`, single uniform clearing price, configurable tie/allocation rule.
3. RFQ: taker requests quote; MM responds with firm quote + TTL; private acceptance/reject path.
4. Dual-flow Batch (optional): maker/taker segregation, separate buy/sell batch clears, no maker-maker matching.

All mechanisms share identical latency and signal primitives unless explicitly changed.

## 6. Metrics (non-negotiable outputs)

1. MM metrics: PnL, Sharpe, max drawdown, inventory variance, adverse-selection loss.
2. Trader metrics: execution error vs `p_t`, slippage, fill probability, time-to-execution.
3. Market metrics: RMSE(price, `p_t`), spread, depth, realized volatility, shock-resilience half-life.

Implement adverse selection explicitly:

`AS = sum_{MM fills j} q_j * (p_{t_j+delta} - fill_price_j)`

with signed `q_j`, fixed horizon `delta`.

## 7. Experimental roadmap (apples-to-apples)

Phase 0: Validation harness
1. Determinism checks by seed.
2. Accounting invariants (cash/inventory/PnL consistency).
3. Mechanism sanity cases.

Phase 1: CLOB baseline
1. Calibrate so MM survives under low informed intensity.
2. Measure degradation as informed intensity/latency rise.

Phase 2: Batch auctions
1. Sweep `Delta in {50,100,250,500,1000}` ms-equivalent.
2. Compare AS loss, spread, fill delay, price RMSE.

Phase 3: RFQ
1. Sweep quote TTL, response latency, dealer competition.
2. Compare protection vs price discovery speed tradeoff.

Phase 4: Optional dual-flow batch
1. Add only after parity tests pass for phases 1-3.

Use factorial Monte Carlo with common seeds and confidence intervals for each treatment contrast.

## 8. Early pitfalls to avoid

1. Comparing mechanisms with different information leakage assumptions unintentionally.
2. Letting MM strategy be mechanism-specific too early (confounds treatment effect).
3. Using one seed per scenario (high variance, unstable claims).
4. Mixing objective truth `p_t` and market-consensus price in evaluation.
5. Ignoring queue-position effects in CLOB while claiming fairness vs batch.

## 9. Forward path: longitudinal agents + lending markets

These are post-MVP extensions intended for economic research questions around adaptation,
institutional memory, and credit cycles.

### 9.1 Persistent agent identity across runs

Goal: support panel-style studies where agents retain identity and state across episodes.

Minimum requirements:
- Stable `agent_uid` separate from per-run instance IDs.
- Versioned agent profile schema (strategy family, risk constraints, capital state).
- Optional carryover state at run boundaries (capital, inventory limits, learned params).
- Explicit reset policy by experiment (`hard_reset`, `capital_only`, `full_carryover`).
- Longitudinal artifact schema with run index and cohort metadata.

Research questions enabled:
- Do agent policies converge, cycle, or destabilize under repeated exposure?
- How persistent are PnL/risk outcomes by agent type?
- Does mechanism ranking change once agents have memory and adaptation?

### 9.2 Lending market extension

Goal: model credit supply, borrowing costs, margin constraints, and liquidation dynamics.

Minimum requirements:
- Credit account abstraction (cash, collateral, debt, health factor).
- Borrow/lend event model and accrual process.
- Interest-rate policy module (utilization curve or exogenous schedule).
- Liquidation policy with deterministic trigger and penalty accounting.
- Cross-market accounting invariants (spot + lending + settlement coherence).

Research questions enabled:
- How does leverage alter adverse selection and liquidity provision?
- Which mechanisms are more robust under deleveraging shocks?
- How do liquidation rules affect volatility and spread dynamics?
