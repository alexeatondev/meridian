# 12 — Positioning, Risk Budgets, Metrics & Adjustments

**Version 0.2 · 2026-11-10**

## Exposure taxonomy (look-through)
Every building-block fund is decomposed into leaves (`config/taxonomy.yaml`), giving a drill-down tree and alternative groupings:

```
Equity ── US ── Large Cap / Mid Cap / Small Cap
       └─ Non-US ── Developed ── Large Cap / Mid Cap
                 └─ Emerging  ── Large Cap / Mid Cap
Fixed Income ── Long-dated (>7y)  ── Core Bonds / High Yield
             └─ Short-dated (≤7y) ── Core Bonds / High Yield / TIPS / Short-term Income
Real Assets ── REITs / Commodities
```
Pivot views: Equity by US vs Non-US, by size, by Developed vs Emerging; Fixed Income by maturity, by sector.
Size and maturity splits are **approximations** of typical index characteristics until holdings-based look-through from a vendor is plugged in.

## Positioning report (every vintage, every node)
| Column | Meaning |
|---|---|
| Current | This run's proposal (or the adjusted proposal) |
| Last week / Last month | Latest recorded positions on or before as-of − 7 days / − 1 month (`data/positions/history.csv`; approved beats proposed). If none is recorded, the glide path on that date, labelled as such |
| Glide path | Strategic policy weights for the vintage |
| Market | Market reference portfolio — Global 60/40 proxy (`taxonomy.yaml → market_benchmark`) |
| Δ vs last wk / mo | Change in weight (pp) |
| Active vs market | Current − market (pp) |
| Relative vs market | Current ÷ market − 1 (n/a where the market holds none) |
| % of risk budget used | The node's contribution to ex-ante tracking error vs the glide path ÷ the vintage's risk budget. Contributions add up to total TE; negative = reduces active risk |

## Risk budgets
- Measure: ex-ante tracking error vs the glide path, using the run's Ledoit-Wolf covariance.
- IPS hard limit 1.50% (§5.3). Operating budgets per vintage (`policies/target_date_series.yaml → risk_budgets`): default 1.20%; 2030 0.80%; 2035 1.00%. Warning at 80% used.
- The optimizers use each vintage's budget; rule **RISK-BUDGET** fails any proposal above it.
- **Changing a budget:** `meridian risk-budget set --vintage 2050 --te 1.0% --name … --role portfolio_manager --reason …` creates a change request. It is applied to the policy file only after **portfolio_manager + risk** approve (`meridian risk-budget approve --id cr_… --name … --role risk …`). The requester cannot approve their own request. Budgets above the IPS hard limit are refused; that needs an IPS amendment. Every step is written to `data/governance/ledger.jsonl`.

## Portfolio metrics
Computed for the proposal, the glide path and the market, over the last 5 years and the full common history. All use constant weights, monthly rebalancing, before fees, and are hypothetical.
Annualized return, volatility, Sharpe and Sortino (excess over T-bills), **beta and alpha vs market** (monthly excess returns), max drawdown, tracking error and information ratio vs market and vs glide path, up/down capture, correlation, R².

## Adjusting weights (portfolio managers and analysts)
- **Absolute:** set a group or fund to a weight, e.g. `Equity=78%`.
- **Relative:** move it by an amount, e.g. `Equity=+1.5pp`.
- **Funded moves:** `Fixed Income/Short-dated=+2pp from Fixed Income/Long-dated` moves duration without touching equity or real assets. Any top-level group not involved is held constant.
- **Single fund:** `asset:us_tips_short=+1pp`.
- **Method:** the smallest possible change to fund weights that meets the request, with weights kept long-only (funds that would go negative are pinned at zero and the problem re-solved). The Console preview uses the same math, so the preview and the recorded result match.
- **Governance:** the compliance engine and risk budget re-check the adjusted portfolio. It is recorded as an `override` decision record (before/after, who, why) and needs re-approval by **portfolio_manager + risk**. FAILs block approval.

## Console
| Tab | Who | What |
|---|---|---|
| Funds & vintages | PM, Manager Selection, Leadership | Every product and vintage with Equity / Fixed Income / Real Assets %, 1-month change, risk budget used; click to drill down |
| Positioning | PM, Risk, Research/Analyst, Manager Selection | Tree or pivot view with all comparison columns; adjustment editor for PMs and analysts |
| Risk budget | PM, Risk, Leadership, Compliance | Budget vs used by vintage, contributors, change requests |
| Metrics | PM, Risk, Research, Leadership | Metrics table across vintages; proposed vs glide path vs market |

## In the hosted app (2026-11-10)
- Adjustments and risk-budget change requests are made in the Console (**Positioning → Adjust weights → Submit adjustment**; **Risk budget → Submit change request**) and written straight to the ledger. The CLI commands above remain for local use.
- Security-level tilts (± bp on one holding) for trading are on the Trading screen (doc 17); they apply to cashflow allocations, not to the asset-class proposal.
- F-11 fixed 2026-11-10: the Risk budget tab has a **With adjustment** column.
- **Glide-path adjustments (2026-11-11):** on the Trading screen, PMs and analysts can request asset-class shifts on the glide path for all funds, all mutual funds, all CITs or one fund (optionally only chosen vintages), inside the IPS bands. They apply only after an Investment Committee member approves (`approvals.glide_path_change`), and they drive the trading Neutral table. Changes beyond the bands still need an IPS amendment.
