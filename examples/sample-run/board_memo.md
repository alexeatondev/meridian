# Board Memo — Meridian Target Retirement Series

**Run:** `run_tds_20261031_64181e` · **As of:** 2026-10-31 · **Policy:** `ips-mtrs@1.0.0` · **Data snapshot:** `snap_3f592900a4dda39a`  
**Judgment engine:** offline-deterministic · **Compliance review:** CONDITIONAL · **Autonomy:** L3 (human approval required)

> **SYNTHETIC DATA — SYSTEM TEST ONLY.** Figures below come from generated data, not market data. They are hypothetical, are not investment advice, and must not be used in any marketing material.

## 1. Recommendation

Hold each vintage within its tactical band around the strategic glide path, implementing the CIO agent's ensemble allocations below once approved by the designated approvers. No vintage requires a glide-path (strategic) change.

| Vintage | Yrs to target | Equity neutral | Equity proposed | Tilt | E[r] | Vol | TE vs glide path | Compliance |
|---|---|---|---|---|---|---|---|---|
| 2030 | 3.2 | 48.1% | 46.6% | -1.5pp | 5.6% | 8.0% | 0.52% | PASS (attestations pending) |
| 2035 | 8.2 | 57.3% | 56.1% | -1.3pp | 5.9% | 9.4% | 0.57% | PASS (attestations pending) |
| 2040 | 13.2 | 67.3% | 66.3% | -1.0pp | 6.2% | 11.0% | 0.61% | PASS (attestations pending) |
| 2045 | 18.2 | 74.8% | 73.8% | -1.0pp | 6.4% | 12.1% | 0.64% | PASS (attestations pending) |
| 2050 | 23.2 | 80.8% | 79.7% | -1.1pp | 6.5% | 13.0% | 0.65% | PASS (attestations pending) |
| 2055 | 28.2 | 83.6% | 82.6% | -1.0pp | 6.6% | 13.4% | 0.66% | PASS (attestations pending) |
| 2060 | 33.2 | 84.6% | 83.6% | -1.0pp | 6.6% | 13.6% | 0.67% | PASS (attestations pending) |
| 2065 | 38.2 | 85.6% | 84.6% | -1.1pp | 6.7% | 13.7% | 0.69% | PASS (attestations pending) |
| 2070 | 43.2 | 86.0% | 84.9% | -1.1pp | 6.7% | 13.8% | 0.69% | PASS (attestations pending) |

## 2. Macro view

**Regime:** late-cycle (confidence 0.69).  
Scores — growth -1.03, inflation 0.8, monetary policy 1.0, financial conditions 0.47.  
Growth score -1.03, inflation 0.8, policy 1.0, financial conditions 0.47 → late_cycle (rule-based classifier).

## 3. Capital market assumptions (10-year, nominal)

| Asset class | Historical | Equilibrium | Valuation/Yield | Auto-blend | Judge | Judge − blend | Vol |
|---|---|---|---|---|---|---|---|
| US Large Cap Equity | 8.0% | 9.6% | 5.4% | 7.2% | **6.7%** | -0.4pp | 15.5% |
| US Small/Mid Cap Equity | 7.1% | 10.8% | 6.3% | 7.5% | **7.6%** | +0.0pp | 19.5% |
| International Developed Equity | 5.5% | 9.7% | 7.7% | 7.1% | **7.2%** | +0.0pp | 16.5% |
| Emerging Markets Equity | 4.5% | 11.4% | 9.4% | 7.7% | **8.3%** | +0.6pp | 21.5% |
| Global Real Estate (REITs) | 4.0% | 10.5% | 7.6% | 6.5% | **6.7%** | +0.2pp | 19.5% |
| Diversified Commodities | 1.3% | 5.7% | 3.9% | 3.7% | **3.8%** | +0.1pp | 16.5% |
| US Core Bond (Aggregate) | 4.7% | 4.1% | 4.3% | 4.4% | **4.4%** | -0.0pp | 4.5% |
| US Long Treasury | 5.7% | 3.5% | 4.8% | 4.7% | **4.8%** | +0.0pp | 12.0% |
| Short-Term TIPS | 3.6% | 4.0% | 3.9% | 3.9% | **3.9%** | +0.0pp | 3.0% |
| US High Yield | 5.2% | 6.0% | 5.4% | 5.5% | **5.4%** | -0.1pp | 9.0% |
| International Bonds (USD-hedged) | 4.7% | 4.1% | 4.2% | 4.3% | **4.2%** | -0.1pp | 4.0% |
| Emerging Markets Debt (USD) | 6.3% | 5.7% | 5.7% | 5.9% | **5.8%** | -0.1pp | 9.5% |
| Cash / Treasury Bills | 2.9% | 3.9% | 3.9% | 3.6% | **3.8%** | +0.1pp | 0.6% |

## 4. How the agents decided (per vintage)

**2030** — ensemble: `inverse_tracking_error`. Peer-vote leaders: max_sharpe_tilt (+8), black_litterman_tilt (+6), risk_budget_tilt (+9). Lowest ranked: adversarial_diversifier (-7).  
Effective N 6.0; simulated max drawdown -22.5% vs glide path -24.0%.

**2035** — ensemble: `inverse_tracking_error`. Peer-vote leaders: max_sharpe_tilt (+9), min_variance_tilt (+10), black_litterman_tilt (+5). Lowest ranked: adversarial_diversifier (-8).  
Effective N 5.3; simulated max drawdown -27.4% vs glide path -29.0%.

**2040** — ensemble: `inverse_tracking_error`. Peer-vote leaders: max_sharpe_tilt (+8), black_litterman_tilt (+7), min_variance_tilt (+11). Lowest ranked: adversarial_diversifier (-8).  
Effective N 4.5; simulated max drawdown -32.8% vs glide path -34.4%.

**2045** — ensemble: `inverse_tracking_error`. Peer-vote leaders: max_sharpe_tilt (+10), risk_budget_tilt (+8), min_variance_tilt (+11). Lowest ranked: adversarial_diversifier (-9).  
Effective N 4.0; simulated max drawdown -36.6% vs glide path -38.2%.

**2050** — ensemble: `inverse_tracking_error`. Peer-vote leaders: risk_budget_tilt (+8), min_variance_tilt (+11), max_sharpe_tilt (+8). Lowest ranked: adversarial_diversifier (-9).  
Effective N 3.6; simulated max drawdown -39.4% vs glide path -40.9%.

**2055** — ensemble: `inverse_tracking_error`. Peer-vote leaders: min_variance_tilt (+12), risk_budget_tilt (+8), max_sharpe_tilt (+8). Lowest ranked: adversarial_diversifier (-9).  
Effective N 3.4; simulated max drawdown -40.6% vs glide path -42.1%.

**2060** — ensemble: `inverse_tracking_error`. Peer-vote leaders: min_variance_tilt (+12), risk_budget_tilt (+8), max_sharpe_tilt (+8). Lowest ranked: adversarial_diversifier (-8).  
Effective N 3.4; simulated max drawdown -41.0% vs glide path -42.6%.

**2065** — ensemble: `inverse_tracking_error`. Peer-vote leaders: min_variance_tilt (+12), risk_budget_tilt (+6), max_sharpe_tilt (+6). Lowest ranked: adversarial_diversifier (-8).  
Effective N 3.3; simulated max drawdown -41.4% vs glide path -43.0%.

**2070** — ensemble: `inverse_tracking_error`. Peer-vote leaders: min_variance_tilt (+12), max_sharpe_tilt (+8), risk_budget_tilt (+6). Lowest ranked: adversarial_diversifier (-8).  
Effective N 3.3; simulated max drawdown -41.6% vs glide path -43.2%.

## 5. Rationale and what would make this wrong

Inverse-tracking-error ensemble (paper §4.4): weights methods closer to the consensus more heavily, keeps every method's information, and stays well inside the TE budget; individual optimizers are sensitive to CMA error in a late-cycle regime.

- Macro regime shifts away from late-cycle
- Any CMA moves outside its method range on the next run
- Equity drawdown > 15% from run date (off-cycle review trigger)
- Tracking error vs. glide path rises above 1.0% (warning threshold)

## 6. Largest tactical positions (2050 vintage)

| Asset class | Glide path | Proposed | Active |
|---|---|---|---|
| global_reits | 3.0% | 1.3% | -1.7pp |
| us_long_treasury | 2.2% | 3.6% | +1.4pp |
| us_small_mid_cap | 7.6% | 6.5% | -1.2pp |
| emerging_eq | 5.8% | 4.7% | -1.2pp |
| us_core_bond | 9.1% | 9.9% | +0.8pp |
| intl_developed_eq | 22.4% | 23.2% | +0.7pp |

## 7. Compliance statement

Deterministic rule engine evaluated every proposal against `ips-mtrs@1.0.0` with entity regimes ['sec_ria', 'registered_fund', 'erisa_plan', 'cftc_derivatives']. Agentic Compliance Officer status: **CONDITIONAL** (DRAFT — requires human CCO sign-off).

- Run used SYNTHETIC data. Outputs are for system testing only; they are not investment advice and may not be used in marketing (hypothetical performance).
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
