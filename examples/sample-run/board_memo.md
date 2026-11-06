# Board Memo — Meridian Target Retirement Series

**Run:** `run_tds_20261031_1dacf5` · **As of:** 2026-10-31 · **Policy:** `ips-mtrs@1.0.0` · **Data snapshot:** `snap_63c4285ae5bb6af6`  
**Judgment engine:** offline-deterministic · **Compliance review:** CONDITIONAL · **Autonomy:** L3 (human approval required)

> **CONTAINS SYNTHETIC DATA — SYSTEM TEST ONLY.** Generated data was used for — returns.monthly: mode=merge; synthetic_rows=334/4961; synthetic_assets=['cash']; macro.indicators: mode=merge; synthetic_rows=11/11; fundamentals.valuation: mode=merge; synthetic_rows=5/5; synthetic_assets=['emerging_eq', 'global_reits', 'intl_developed_eq', 'us_large_cap', 'us_small_mid_cap']; yields.current: mode=merge; synthetic_rows=8/8; synthetic_assets=['cash', 'commodities', 'em_debt', 'intl_bond_hedged', 'us_core_bond', 'us_high_yield', 'us_long_treasury', 'us_tips_short']. Figures are hypothetical, are not investment advice, and must not be used in any marketing material.

**Data sources:** returns.monthly ← cache (4627), synthetic (334); macro.indicators ← synthetic (11); fundamentals.valuation ← synthetic (4), cache+manual+synthetic (1); yields.current ← synthetic (8)

## 1. Recommendation

Hold each vintage within its tactical band around the strategic glide path, implementing the CIO agent's ensemble allocations below once approved by the designated approvers. No vintage requires a glide-path (strategic) change.

| Vintage | Yrs to target | Equity neutral | Equity proposed | Tilt | E[r] | Vol | TE vs glide path | Compliance |
|---|---|---|---|---|---|---|---|---|
| 2030 | 3.2 | 48.1% | 47.8% | -0.3pp | 5.9% | 8.3% | 0.15% | PASS (attestations pending) |
| 2035 | 8.2 | 57.3% | 56.4% | -1.0pp | 6.3% | 9.4% | 0.30% | PASS (attestations pending) |
| 2040 | 13.2 | 67.3% | 65.8% | -1.6pp | 6.6% | 10.7% | 0.49% | PASS (attestations pending) |
| 2045 | 18.2 | 74.8% | 73.0% | -1.8pp | 6.9% | 11.6% | 0.60% | PASS (attestations pending) |
| 2050 | 23.2 | 80.8% | 78.9% | -1.9pp | 7.1% | 12.3% | 0.63% | PASS (attestations pending) |
| 2055 | 28.2 | 83.6% | 81.7% | -1.9pp | 7.2% | 12.7% | 0.61% | PASS (attestations pending) |
| 2060 | 33.2 | 84.6% | 82.6% | -2.0pp | 7.2% | 12.9% | 0.61% | PASS (attestations pending) |
| 2065 | 38.2 | 85.6% | 83.7% | -1.9pp | 7.2% | 13.0% | 0.59% | PASS (attestations pending) |
| 2070 | 43.2 | 86.0% | 84.0% | -2.0pp | 7.3% | 13.1% | 0.60% | PASS (attestations pending) |

## 2. Macro view

**Regime:** late-cycle (confidence 0.69).  
Scores — growth -1.03, inflation 0.8, monetary policy 1.0, financial conditions 0.47.  
Growth score -1.03, inflation 0.8, policy 1.0, financial conditions 0.47 → late_cycle (rule-based classifier).

## 3. Capital market assumptions (10-year, nominal)

| Asset class | Historical | Equilibrium | Valuation/Yield | Auto-blend | Judge | Judge − blend | Vol |
|---|---|---|---|---|---|---|---|
| US Large Cap Equity | 11.2% | 8.9% | 4.9% | 8.1% | **7.1%** | -1.0pp | 14.6% |
| US Small/Mid Cap Equity | 11.1% | 9.9% | 6.3% | 8.9% | **8.9%** | -0.1pp | 18.6% |
| International Developed Equity | 7.9% | 9.5% | 7.7% | 8.1% | **8.1%** | -0.0pp | 16.8% |
| Emerging Markets Equity | 9.7% | 9.7% | 9.4% | 9.4% | **9.6%** | +0.1pp | 19.9% |
| Global Real Estate (REITs) | 8.3% | 9.5% | 7.6% | 8.1% | **8.1%** | +0.1pp | 20.9% |
| Diversified Commodities | 5.2% | 6.8% | 3.9% | 4.9% | **4.3%** | -0.6pp | 18.4% |
| US Core Bond (Aggregate) | 3.1% | 4.4% | 4.3% | 4.1% | **4.3%** | +0.2pp | 4.5% |
| US Long Treasury | 3.4% | 4.1% | 4.8% | 4.3% | **4.6%** | +0.3pp | 11.9% |
| Short-Term TIPS | 4.0% | 4.4% | 3.9% | 4.0% | **4.0%** | -0.1pp | 4.7% |
| US High Yield | 5.6% | 6.4% | 5.4% | 5.7% | **5.5%** | -0.2pp | 9.3% |
| International Bonds (USD-hedged) | 4.1% | 4.4% | 4.2% | 4.2% | **4.2%** | -0.0pp | 4.0% |
| Emerging Markets Debt (USD) | 7.0% | 6.5% | 5.7% | 6.3% | **5.9%** | -0.3pp | 10.8% |
| Cash / Treasury Bills | 2.8% | 3.9% | 3.9% | 3.6% | **3.7%** | +0.2pp | 0.6% |

## 4. How the agents decided (per vintage)

**2030** — ensemble: `inverse_tracking_error`. Peer-vote leaders: max_sharpe_tilt (+11), risk_budget_tilt (+7), min_variance_tilt (+6). Lowest ranked: adversarial_diversifier (-1).  
Effective N 6.3; simulated max drawdown -30.3% vs glide path -30.6%.

**2035** — ensemble: `inverse_tracking_error`. Peer-vote leaders: black_litterman_tilt (+8), max_sharpe_tilt (+8), risk_budget_tilt (+8). Lowest ranked: adversarial_diversifier (-9).  
Effective N 5.7; simulated max drawdown -34.6% vs glide path -35.6%.

**2040** — ensemble: `inverse_tracking_error`. Peer-vote leaders: black_litterman_tilt (+10), risk_budget_tilt (+8), max_sharpe_tilt (+5). Lowest ranked: adversarial_diversifier (-10).  
Effective N 4.8; simulated max drawdown -39.5% vs glide path -41.0%.

**2045** — ensemble: `inverse_tracking_error`. Peer-vote leaders: risk_budget_tilt (+10), max_sharpe_tilt (+7), black_litterman_tilt (+8). Lowest ranked: adversarial_diversifier (-8).  
Effective N 4.3; simulated max drawdown -42.8% vs glide path -44.7%.

**2050** — ensemble: `inverse_tracking_error`. Peer-vote leaders: risk_budget_tilt (+11), max_sharpe_tilt (+7), black_litterman_tilt (+9). Lowest ranked: adversarial_diversifier (-8).  
Effective N 3.8; simulated max drawdown -45.4% vs glide path -47.3%.

**2055** — ensemble: `inverse_tracking_error`. Peer-vote leaders: risk_budget_tilt (+11), max_sharpe_tilt (+7), black_litterman_tilt (+8). Lowest ranked: adversarial_diversifier (-8).  
Effective N 3.6; simulated max drawdown -46.7% vs glide path -48.5%.

**2060** — ensemble: `inverse_tracking_error`. Peer-vote leaders: risk_budget_tilt (+11), max_sharpe_tilt (+7), black_litterman_tilt (+8). Lowest ranked: adversarial_diversifier (-8).  
Effective N 3.6; simulated max drawdown -47.1% vs glide path -48.9%.

**2065** — ensemble: `inverse_tracking_error`. Peer-vote leaders: risk_budget_tilt (+11), max_sharpe_tilt (+7), black_litterman_tilt (+8). Lowest ranked: adversarial_diversifier (-8).  
Effective N 3.5; simulated max drawdown -47.6% vs glide path -49.3%.

**2070** — ensemble: `inverse_tracking_error`. Peer-vote leaders: risk_budget_tilt (+11), max_sharpe_tilt (+7), black_litterman_tilt (+8). Lowest ranked: adversarial_diversifier (-8).  
Effective N 3.5; simulated max drawdown -47.8% vs glide path -49.5%.

## 5. Rationale and what would make this wrong

*CIO agent reasoning for the 2030 vintage shown; every vintage's reasoning is in the Console and the decision ledger.*

Inverse-tracking-error ensemble (paper §4.4): weights methods closer to the consensus more heavily, keeps every method's information, and stays well inside the TE budget; individual optimizers are sensitive to CMA error in a late-cycle regime.

- Macro regime shifts away from late-cycle
- Any CMA moves outside its method range on the next run
- Equity drawdown > 15% from run date (off-cycle review trigger)
- Tracking error vs. glide path rises above 1.0% (warning threshold)

## 6. Largest tactical positions (2050 vintage)

| Asset class | Glide path | Proposed | Active |
|---|---|---|---|
| intl_developed_eq | 22.4% | 20.4% | -2.1pp |
| cash | 0.0% | 1.5% | +1.5pp |
| us_long_treasury | 2.2% | 3.6% | +1.4pp |
| global_reits | 3.0% | 1.7% | -1.3pp |
| us_tips_short | 0.4% | 1.5% | +1.1pp |
| emerging_eq | 5.8% | 6.8% | +1.0pp |

## 7. Compliance statement

Deterministic rule engine evaluated every proposal against `ips-mtrs@1.0.0` with entity regimes ['sec_ria', 'registered_fund', 'erisa_plan', 'cftc_derivatives']. Agentic Compliance Officer status: **CONDITIONAL** (DRAFT — requires human CCO sign-off).

- Run used SYNTHETIC data for: returns.monthly (mode=merge; synthetic_rows=334/4961; synthetic_assets=['cash']); macro.indicators (mode=merge; synthetic_rows=11/11); fundamentals.valuation (mode=merge; synthetic_rows=5/5; synthetic_assets=['emerging_eq', 'global_reits', 'intl_developed_eq', 'us_large_cap', 'us_small_mid_cap']); yields.current (mode=merge; synthetic_rows=8/8; synthetic_assets=['cash', 'commodities', 'em_debt', 'intl_bond_hedged', 'us_core_bond', 'us_high_yield', 'us_long_treasury', 'us_tips_short']). Outputs are for system testing only; they are not investment advice and may not be used in marketing (hypothetical performance).
- Public data sources in use carry non-commercial or series-level terms (see config/data_sources.yaml → license_review); licensed data is required before production.
- Production blocker: Required human role unfilled: chief_compliance_officer
- Production blocker: Required human role unfilled: derivatives_risk_manager
- Production blocker: Required human role unfilled: liquidity_program_administrator
- Production blocker: Required human role unfilled: fund_board
- Production blocker: Required human role unfilled: plan_fiduciary_committee
- Production blocker: Regime pack needs counsel/CCO review: sec_ria
- Production blocker: Regime pack needs counsel/CCO review: registered_fund
- Production blocker: Regime pack needs counsel/CCO review: erisa_plan
- Production blocker: Regime pack needs counsel/CCO review: cftc_derivatives
- 3 attestation(s) require a named human: CONF-AFFILIATE-DISCLOSE, ERISA-AFFILIATE-PT, FOF-12D1

## 8. Rebalancing plan

Quarterly calendar rebalance; off-cycle if any asset class drifts more than 2.0pp from target, or any invalidation condition triggers. Glide path steps monthly.

## 9. Approvals required

- portfolio_manager: pending
- risk: pending

## 10. Disclosures

Prepared by Meridian's autonomous agents operating at autonomy level L3 under the Investment Policy Statement. Expected returns are estimates, not guarantees. Backtests are hypothetical, may be affected by look-ahead bias, and do not reflect actual trading, fees or taxes. All agent reasoning and data lineage are retained in the decision ledger.
