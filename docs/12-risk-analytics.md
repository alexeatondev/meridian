# 12 — Risk Analytics

**Audience:** risk analytics, portfolio managers, research, leadership, compliance, audit
**Code:** `src/meridian/analytics/risk.py` · **Settings:** `config/risk.yaml` · **Console:** Fund risk, Factor risk, Stress tests, Risk history, Look-through & search · **Notebook:** `notebooks/04_risk_analytics_workbench.ipynb`

All risk figures are computed by deterministic code. Agents may explain them, but they never calculate them. The console, notebook, board memo and ledger all read the same numbers, so every screen shows the same figure for the same measure.

## 1. What you can see

| Need | Where | What it shows |
|---|---|---|
| Fund-level risk | **Fund risk** (top table) | Every vintage: total risk and benchmark total risk, active risk, effective duration (fund, benchmark, relative), credit spread duration (fund, benchmark, relative), VaR 95 and active VaR 95, diversification and benchmark diversification |
| Risk by asset class across funds | **Fund risk** (second table) | Share of total risk from Equity, Fixed Income and Real Assets per vintage, fund vs benchmark |
| Risk breakdown of one fund | **Fund risk → drill-down** | Expandable tree (Equity → US/Non-US → size; Developed/Emerging; Fixed Income → long/short-dated → core/HY/TIPS/short-term income), or per underlying fund: weight, % of total risk, benchmark % of risk, difference, % of active risk, standalone and marginal risk |
| Weight vs risk | **Fund risk → Weight vs. risk by holding** | Paired bars per underlying fund: % of fund and % of total risk, with a marker for the benchmark's % of risk; hover for risk per unit of weight |
| Factor decomposition | **Factor risk** | Contribution of each factor (and specific risk) to total, active or benchmark variance; exposures (β) fund vs benchmark; factor volatilities; how each factor is built |
| Factor history | **Factor risk → Factor history** | 18 months of each factor family's share of variance; drill into one family's factors, or hide Equity to see the smaller risks |
| Stress tests | **Stress tests** | 12 historical replays (GFC, Lehman, euro crisis, taper tantrum, China/oil, Q4 2018, COVID, 2022, SVB, 2025 tariffs, plus two rallies); 7 hypothetical scenarios at five severities (Normal 1σ → Crisis 5σ); worst month on record; an interactive scenario builder |
| Risk time series | **Risk history** | 18 months of total risk, active risk, effective duration, spread duration, diversification and VaR, fund vs benchmark, with where each month's weights came from |
| Security exposure | **Look-through & search** | Per vintage: each underlying fund, expandable to its holdings (top 25 or all), and the largest look-through exposures across funds |
| Who holds a security | **Look-through & search → search box** | Type a ticker or name: every vintage's exposure, and through which underlying funds |

Roles: Risk Analytics gets all five views. PMs get Fund risk and Look-through. Research gets Factor risk and Look-through. Manager Selection and Compliance get Look-through. Leadership gets Fund risk and Stress tests.

## 2. Definitions

| Measure | Definition |
|---|---|
| Total risk | Annualized ex-ante volatility, √(wᵀΣw) |
| Benchmark total risk | Same, for the vintage's glide-path (neutral) weights |
| Active risk | Tracking error vs the glide path, √((w−b)ᵀΣ(w−b)), the same number the risk budget uses |
| Effective duration | Σ wᵢ × effective durationᵢ of each building block (years) |
| Credit spread duration | Σ wᵢ × spread durationᵢ (years); Treasury and cash lines carry none |
| Relative duration / relative CSD | Fund − benchmark |
| VaR 95 | Parametric (normal) loss not exceeded with 95% confidence over the horizon: 1.645 × σ × √(h/12), with h = 1 month by default. Shown as a positive loss |
| Active VaR 95 | Same on the active positions: 1.645 × tracking error × √(h/12) |
| Diversification | 1 − fund volatility ÷ Σ \|wᵢ\| × σᵢ (share of standalone risk removed by imperfect correlation) |
| % of total risk | Euler contribution wᵢ(Σw)ᵢ / σ²; contributions add up to 100% |
| % of active risk | Same on the active weights; adds up to 100% of tracking error |

## 3. Risk model

- **Covariance (Σ):** Ledoit-Wolf shrinkage of monthly total returns for the 13 building-block proxies, using the common history (August 2002 onward). It is the same estimator portfolio construction and the risk budget use, so total and active risk match the Risk budget screen exactly. The window and estimator are set in `config/risk.yaml`.
- **Factors:** ten systematic factors built from proxy excess returns: global equity market, size, non-US developed vs US, EM vs developed, US rates (duration), credit spread (high yield, rate-hedged), EM sovereign spread (rate-hedged), inflation breakeven (rate-hedged), real estate vs equity, and commodities. They are grouped into six families for charts: Equity, Rates, Credit, Inflation, Real assets, Specific. The definitions are editable in `config/risk.yaml`.
- **Consistency:** factor returns are linear in asset returns (f = Dᵀr). The factor covariance is F = DᵀΣD, and the loadings are B = ΣDF⁻¹. Specific risk Σ − BFBᵀ is a Schur complement, so it is never negative, and factor plus specific contributions add up to 100%.
- **Fit:** most building blocks are almost fully explained by the factors (R² ≈ 1). US Core Bond (≈ 0.82) and International Bonds hedged (≈ 0.54) carry real specific risk.
- **Vendor models:** Barra, Axioma or Bloomberg PORT factor returns can replace the built-in factors through a `factors.monthly` dataset routed in `config/data_sources.yaml` (design hook; not yet wired).

## 4. Durations and look-through

**Durations** (`fund.characteristics` dataset), highest priority first:
1. A vendor feed (Bloomberg or FactSet via Snowflake) or a file drop.
2. **Holdings look-through:** weight-averaged per-line duration from the proxy fund's holdings. Spread duration counts every non-government, non-cash line. The government sector list is in `config/risk.yaml`.
3. **Cited values** in `config/manual_inputs.yaml`, with source and as-of date for each.

**Holdings** (`holdings.lookthrough` dataset) come from the daily public holdings files of an iShares fund tracking the same or a similar index as each building block (`config/universe.yaml → identifiers.holdings`; a blend such as 70% IJH + 30% IJR is allowed). The monthly data refresh downloads them, and the run's snapshot stores them with a sha256 hash. Bond holdings are aggregated by issuer. A ticker that is both a stock and a bond issuer (for example JPM) appears twice, once per asset class. A building block's look-through proxy can differ from its return proxy (for example VOO returns with IVV holdings, both S&P 500); the console shows both. Licensed holdings (FactSet, Bloomberg, custodian files) plug into the same dataset.

## 5. Stress testing

- **Historical:** today's weights × the realized cumulative proxy returns over the window, with no rebalancing during the window. Only windows inside the common data history are available (from August 2002).
- **Hypothetical:** each scenario shocks one or more factors by k × their 1-month standard deviation, for k = 1 (Normal, about 1 in 6 months), 2 (Elevated), 3 (Severe), 4 (Extreme) and 5 (Crisis). Unshocked factors move by their conditional expectation given the shocked ones (*correlated*) or stay at zero (*isolated*). Asset returns are B·f. Single-driver rate scenarios are isolated by default, because the 2002–2026 stock–bond correlation was mostly negative and would make "rates up" look like an equity rally (2022 showed this can break). Stagflation is defined explicitly as equity down, rates up and inflation up.
- **Scenario builder (console):** move equities (%), Treasury yields (bp), HY and EM spreads (bp), breakevens (bp), commodities (%), REITs vs equities and EM vs DM. Basis-point moves convert to factor returns through the relevant duration: −duration × Δy for rates; −spread duration × Δs for spreads; +TIPS duration × Δbreakeven. Results update for every vintage instantly.
- **Limits:** linear (no convexity or optionality); proxies stand in for the funds; one-month horizon; no liquidity or path effects.

## 6. History and storage

- Each run computes an 18-month month-end history. Each month uses only data available at that month-end. Weights come from recorded positions where they exist, otherwise from the glide path for that date. The latest point is the run's proposal.
- Each run also records a **point-in-time snapshot** (every metric plus each factor's share) in `data/risk/history.csv`, or in the hosted app's database. A later run uses the recorded snapshot for that month instead of reconstructing it, so history keeps what was known at the time. The hosted app exposes these snapshots at `/api/export/risk-history.csv`, and the agent-run workflow pulls them before each run.
- The ledger has a `risk.analytics` decision record per run, with the headline metrics and the duration sources.

## 7. Known limitations (pilot)

- Proxy ETFs and index funds stand in for the building-block funds, for returns, durations and holdings.
- Durations are current values applied to every month in the history until a vendor or holdings history is loaded.
- VaR is parametric (normal); fat tails are better seen in the historical stress replays.
- Reconstructed months use glide-path weights where no positions were recorded, so their active risk is zero.
- Look-through is equally detailed for every fund only after the data refresh has downloaded holdings. iShares holdings are published for informational use; review the terms before production or redistribution.

## 8. Suggested add-ons (not built; awaiting direction)

Common in institutional risk teams and natural next steps here. None of these has been implemented.

1. **Expected shortfall (CVaR) and historical/Monte Carlo VaR** next to parametric VaR, plus a fat-tail (Cornish-Fisher) adjustment.
2. **VaR backtesting:** count breaches of realized monthly returns vs predicted VaR (Kupiec/Christoffersen tests), a standard model-validation check.
3. **Ex-post vs ex-ante risk:** realized volatility and tracking error vs forecast, with a bias statistic per vintage.
4. **Liquidity risk:** days-to-liquidate and liquidity buckets (needed for the Rule 22e-4 program of a registered fund) and redemption stress.
5. **Derivatives and FX:** delta-adjusted notional, commitment approach and Rule 18f-4 VaR tests (relative VaR vs the designated reference portfolio), and FX exposure before and after hedging.
6. **Concentration and issuer limits on look-through:** top-10 issuer exposure, single-issuer and sector caps, and overlap between building blocks (the same issuer held through several funds).
7. **Sector, country, currency and credit-quality breakdowns** of the look-through holdings (rating buckets, OAS, yield to worst, key-rate durations).
8. **Key-rate durations and curve scenarios** (steepener, flattener, twist) instead of a parallel shift.
9. **Risk attribution of returns:** realized performance split into allocation, factor and selection effects.
10. **Limit monitoring with alerts:** daily proximity alerts for VaR, active risk and duration bands, sent by email or Slack, with acknowledgment logged in the ledger.
11. **Reverse stress test:** the smallest combined shock that breaches a loss threshold (for example −20% for the 2030 vintage).
12. **Glide-path risk across the lifecycle:** risk and stress losses plotted against years to target, and a sequence-of-returns risk view near retirement.
