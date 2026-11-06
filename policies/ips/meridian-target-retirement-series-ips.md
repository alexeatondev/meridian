# Investment Policy Statement
## Meridian Target Retirement Series
### Vintages 2030 · 2035 · 2040 · 2045 · 2050 · 2055 · 2060 · 2065 · 2070

| | |
|---|---|
| **Document ID** | IPS-MTRS-001 |
| **Version** | 1.0 (DRAFT — pending adoption) |
| **Effective date** | Upon adoption by the Governing Body |
| **Prepared for** | The Governing Body of the Series (see §2.1) |
| **Prepared by** | Meridian Investment Management (hypothetical) — Investment Committee |
| **Machine-readable policy** | `policies/target_date_series.yaml` (`ips-mtrs@1.0.0`) |
| **Review cycle** | At least annually; ad hoc upon a material event (§11) |

> **Hypothetical document.** Meridian Investment Management, the Series, and all figures in this statement are illustrative and were created to pilot the Meridian platform. This is not an offering document and not investment advice. Structure follows widely used institutional practice: the CFA Institute's *Elements of an Investment Policy Statement for Institutional Investors*, U.S. Department of Labor *Target Date Retirement Funds — Tips for ERISA Plan Fiduciaries*, and the policy and prospectus conventions of large U.S. target-date series. The operating entity is selectable (§2.2), so regulatory sections apply only where that entity type is selected.

---

## 1. Purpose and Scope

1.1 **Purpose.** This Investment Policy Statement ("IPS") sets out the objectives, risk tolerances, strategic asset allocation (the "glide path"), permissible investments, constraints, governance, and monitoring framework for the Meridian Target Retirement Series (the "Series"). It is intended to:

- (a) define clearly the investment objectives and constraints of each vintage ("Fund");
- (b) set out the roles and responsibilities of every party, including autonomous software agents operating on the Meridian platform;
- (c) establish the criteria for evaluating investment performance and the process followed; and
- (d) provide a written, reviewable record of a prudent investment process.

1.2 **Scope.** The IPS governs nine Funds, each named for an approximate year in which investors expect to retire and begin withdrawals (the "Target Date"): 2030, 2035, 2040, 2045, 2050, 2055, 2060, 2065 and 2070. Each Fund is a fund of funds that invests in underlying building-block funds ("Underlying Funds"), each representing one asset class in §6.

1.3 **Investor profile.** The Series is designed for participants in defined-contribution retirement plans and similar long-horizon investors who:

- expect to retire at or near age 65 in, or within two to three years of, the Target Date;
- make periodic contributions until retirement and gradual withdrawals after it;
- may be defaulted into the Series and may not actively manage their allocation.

1.4 **Precedence.** If this IPS conflicts with applicable law, the governing documents of a Fund (prospectus, declaration of trust, plan document), or a written direction of the Governing Body, those take precedence, and the IPS shall be amended promptly.

## 2. Governance

### 2.1 Governing Body
The "Governing Body" is the body with fiduciary oversight of the Series, determined by the operating entity (§2.2): the board of trustees/directors (registered fund), the trust or fiduciary committee (bank collective investment trust), the plan's investment committee (ERISA plan), or the investment committee of the adviser (separately managed or private vehicle).

### 2.2 Operating entity
The Series may be operated through one or more of: an SEC-registered investment adviser; a 1940 Act registered fund; a bank collective investment trust; an ERISA plan investment structure; a private fund; or an asset owner / OCIO. The selected entity types are recorded in `config/entity_profile.yaml`. The Meridian platform applies the matching regulatory obligations, rules, record-retention period and required approvers automatically. No selection relieves any person of obligations that apply by law.

### 2.3 Roles and responsibilities

| Party | Responsibilities |
|---|---|
| **Governing Body** | Adopt and amend this IPS; approve the glide path and any change to it; appoint the Investment Manager; approve the autonomy level of the Meridian platform; review performance and compliance reports at least quarterly. |
| **Investment Committee (IC)** | Recommend the glide path; approve capital market assumptions annually; approve tactical-tilt ranges; review the CIO agent's board memo each quarter; escalate breaches. |
| **Portfolio Manager(s)** | Approve or reject each rebalancing and tactical proposal with a recorded reason; ensure implementation; own day-to-day management. |
| **Chief Compliance Officer (human)** | Administer the compliance program; sign attestations; approve exceptions; approve changes to the machine-readable policy. **This role must be held by a natural person and cannot be delegated to an AI agent.** |
| **Risk function** | Independent review of risk reports; second approver for tactical tilts; model-risk challenge. |
| **Meridian platform agents** | Perform analysis and produce proposals inside this IPS (§10). Agents do not hold authority to trade, approve, amend policy, or waive limits. |
| **Agentic Compliance Officer (AI)** | Reviews every run against this IPS and the selected regimes; drafts compliance reports for the human CCO. |
| **Custodian / Administrator** | Safekeeping, accounting, NAV, and books of record. |

### 2.4 Delegation
The Governing Body delegates day-to-day investment management to the Investment Manager within this IPS. The Investment Manager may use the Meridian platform's autonomous agents to perform analytical work, provided that: (a) every decision that changes holdings is approved by an authorized person; (b) every agent output is recorded in the decision ledger; and (c) the platform operates at the autonomy level approved by the Governing Body (initially **L3 — agents propose, humans approve**).

## 3. Investment Objectives

3.1 **Primary objective.** Each Fund seeks the highest total return over time consistent with an asset mix that becomes more conservative as its Target Date approaches, and then continues to seek current income and capital preservation, with some capital growth, for seven years after the Target Date.

3.2 **Return objectives (long term, net of fees, not guaranteed).**

| Phase | Years to Target Date | Return objective |
|---|---|---|
| Accumulation | > 25 | CPI + 4.0% to 5.0% annualized over rolling 10-year periods |
| Transition | 25 to 10 | CPI + 3.0% to 4.0% |
| Pre-retirement | 10 to 0 | CPI + 2.0% to 3.0% |
| Decumulation | 0 to −7 (landing) | CPI + 1.0% to 2.0%, with emphasis on income and inflation protection |

3.3 **Benchmarks.**
- **Primary (policy) benchmark:** for each Fund, a custom composite of the asset-class benchmarks in §6.1 weighted at that Fund's strategic glide-path weights, rebalanced monthly.
- **Secondary (peer) benchmark:** the S&P Target Date Index of the same vintage.
- **Peer group:** the Morningstar target-date category of the same vintage.

3.4 **Value-added objective.** Tactical decisions (§6.3) seek to add 0.25% to 0.50% per year over the policy benchmark over rolling five-year periods, within the active-risk budget in §5.3.

## 4. Investor Considerations and Constraints

4.1 **Time horizon.** Multi-decade. The horizon of each Fund extends past the Target Date through the landing point (Target Date + 7 years), recognizing that investors draw down savings over 20–30 years in retirement.

4.2 **Liquidity.** Each Fund must meet daily contributions and redemptions. All Underlying Funds must offer daily liquidity. No illiquid investments are permitted. Where the registered-fund regime applies, the illiquid-investment limit of 15% applies in any case.

4.3 **Taxes.** The Series is designed for tax-deferred accounts. Tax efficiency is a secondary consideration.

4.4 **Legal and regulatory.** See §9.

4.5 **Unique circumstances.** Participants may be defaulted into the Series. The Series is therefore designed so that a reasonable participant with no other retirement assets is adequately diversified.

## 5. Risk Tolerance

5.1 **Risk factors considered.** Market risk; **longevity risk** (outliving savings); **sequence-of-returns risk** near the Target Date; inflation risk; interest-rate risk; credit risk; currency risk; liquidity risk; model risk (including the risk of error in autonomous agents).

5.2 **Glide-path philosophy.** The Governing Body judges that, for the typical participant, longevity and inflation risk dominate early and sequence risk dominates near retirement. The glide path therefore holds a high allocation to growth assets for younger investors and lowers it steadily to roughly 43% equity at the Target Date. It keeps declining to roughly 29% equity seven years later (a "through" glide path).

5.3 **Risk limits.**

| Measure | Limit | Rule ID |
|---|---|---|
| Ex-ante tracking error vs. policy benchmark | ≤ 1.50% (warning at 1.00%) | TE-NEUTRAL, TE-WARN |
| Ex-ante volatility vs. glide-path portfolio | ≤ 1.15× (warning) | RISK-VOL-BAND |
| Deviation of total equity from glide path | ± 5 percentage points | POL-BAND-EQUITY |
| Deviation of growth assets from glide path | ± 5 percentage points | POL-BAND-GROWTH |
| Deviation of any asset class from glide path | ± 3 percentage points | POL-BAND-ASSET |
| Operating risk budget (ex-ante TE vs glide path), per vintage, ≤ the TE limit above | default 1.20%; 2030: 0.80%; 2035: 1.00% | RISK-BUDGET |

5.4 **Drawdown awareness.** The Funds are not designed to avoid losses. Near the Target Date, the Investment Manager reports simulated and realized drawdowns to the IC each quarter. If a Fund within five years of its Target Date has a peak-to-trough decline of more than 15%, that triggers an off-cycle IC review.

## 6. Strategic Asset Allocation

### 6.1 Asset classes and benchmarks

| Asset class | Role | Benchmark |
|---|---|---|
| US Large Cap Equity | Growth | S&P 500 |
| US Small/Mid Cap Equity | Growth, size diversification | S&P Completion |
| International Developed Equity | Growth, geographic diversification | MSCI EAFE (net) |
| Emerging Markets Equity | Growth | MSCI Emerging Markets (net) |
| Global Real Estate (REITs) | Real assets, income | FTSE EPRA Nareit Developed |
| Diversified Commodities | Inflation hedge | Bloomberg Commodity |
| US Core Bond | Ballast, income | Bloomberg US Aggregate |
| US Long Treasury | Equity-crisis hedge, duration | Bloomberg US Long Treasury |
| Short-Term TIPS | Near-term inflation protection | Bloomberg US 0–5 Year TIPS |
| US High Yield | Income | Bloomberg US Corporate High Yield |
| International Bonds (USD-hedged) | Diversified ballast | Bloomberg Global Aggregate ex-USD (USD hedged) |
| Emerging Markets Debt (USD) | Income | J.P. Morgan EMBI Global Diversified |
| Cash / Treasury Bills | Liquidity, capital preservation | ICE BofA 3-Month T-Bill |

### 6.2 Glide path (strategic weights, %)
Weights between anchor points are linearly interpolated and updated monthly. Each row sums to 100%.

| Years to Target | US LC | US SMID | Intl Dev | EM | REITs | Cmdty | Core | Long Tsy | ST TIPS | HY | Intl Bd | EMD | Cash | **Total equity** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 40+ | 47 | 9 | 24 | 6 | 3 | 1 | 6 | 2 | 0 | 1 | 1 | 0 | 0 | **86** |
| 25 | 46 | 8 | 23 | 6 | 3 | 1 | 8 | 2 | 0 | 1 | 2 | 0 | 0 | **83** |
| 15 | 40 | 6 | 20 | 5 | 3 | 1 | 14 | 3 | 2 | 2 | 3 | 1 | 0 | **71** |
| 10 | 35 | 5 | 17 | 4 | 2 | 1 | 18 | 3 | 5 | 2 | 5 | 1 | 2 | **61** |
| 5 | 30 | 4 | 14 | 3 | 2 | 1 | 20 | 2 | 9 | 2 | 6 | 1 | 6 | **51** |
| 0 (Target) | 26 | 3 | 12 | 2 | 2 | 1 | 22 | 1 | 12 | 2 | 7 | 1 | 9 | **43** |
| −7 (Landing) | 18 | 2 | 8 | 1 | 1 | 0 | 25 | 0 | 17 | 1 | 8 | 0 | 19 | **29** |

Total equity = US LC + US SMID + Intl Dev + EM. Growth assets = total equity + REITs. After the landing point, a Fund may be merged into a retirement-income fund holding the landing-point allocation, subject to the Governing Body's approval.

### 6.3 Tactical ranges
The Investment Manager may deviate from the strategic weights within the limits in §5.3 to reflect capital market views. Tactical tilts must be proposed with a written rationale and approved under §10.4. The glide path itself may only be changed by the Governing Body.

### 6.4 Capital market assumptions
The Investment Manager reviews forward-looking 10-year capital market assumptions (expected return, volatility, correlation) at least quarterly using multiple methods: historical, equilibrium, valuation building-block, yield-based and regime-conditional. The IC approves the CMA methodology annually. All estimates and the reasoning used to select them are retained (§12).

## 7. Permissible Investments and Restrictions

7.1 **General.** Each Fund invests only in Underlying Funds representing the asset classes in §6.1, cash, and derivatives as permitted in §7.5. Weights must sum to 100% (± 0.05%). Short positions in Underlying Funds are prohibited.

7.2 **Underlying Funds.** Underlying Funds may be index or actively managed, affiliated or unaffiliated, and must be selected and monitored under §8.

7.3 **Concentration limits.**

| Limit | Value | Rule ID |
|---|---|---|
| Below-investment-grade fixed income (HY + EMD) | ≤ 10% of Fund | CONC-BELOW-IG |
| Non-US equity as a share of total equity | ≤ 45% | CONC-NONUS-EQ |
| Cash and equivalents | ≤ 25% | CONC-CASH |
| Any single Underlying Fund | ≤ 50% | CONC-SINGLE-FUND |

7.4 **Liquidity.** All Underlying Funds must offer daily liquidity (LIQ-DAILY). Where the registered-fund regime applies: illiquid investments ≤ 15% (LIQ-ILLIQUID-15), measured under the Fund's liquidity risk management program.

7.5 **Derivatives.** Derivatives may be used only to (a) hedge currency exposure in hedged fixed-income sleeves, (b) obtain commodity exposure through futures inside the commodity Underlying Fund, and (c) manage cash flows (equitize cash) with exchange-traded futures. Leverage for speculation is prohibited. Where the registered-fund or CFTC regime applies, derivatives exposure is limited to 10% of net assets, consistent with the limited-derivatives-user approach (DERIV-LDU). Above that level a derivatives risk management program and VaR limits would be required before any increase.

7.6 **Prohibited.** Direct real estate; private equity or private credit; securities lending by the Fund itself (Underlying Funds may lend under their own policies); cryptocurrencies; and any investment that would cause a prohibited transaction under applicable law.

## 8. Selection and Monitoring of Underlying Funds

8.1 **Selection criteria.** Benchmark fit and style consistency; tracking error appropriate to the mandate; total expense ratio; liquidity and capacity; operational quality (custody, valuation, audit); stability of team and process; for active funds, a documented and repeatable source of excess return.

8.2 **Monitoring.** Quarterly review of performance against benchmark and peers, tracking error, style drift, holdings concentration, expense ratio and organizational changes. Holdings-based look-through of every Fund is reviewed at least monthly.

8.3 **Watch list and replacement.** An Underlying Fund is placed on the watch list after any of: three-year performance below benchmark by more than its expected tracking error; a material change in team, process or ownership; style drift; or an operational event. Any replacement goes to the IC for approval with a written rationale.

8.4 **Use of agents.** Manager-research agents may screen, summarize due-diligence documents and score candidates. Every factual claim they make must cite its source document, and selection decisions are made by authorized persons.

## 9. Regulatory and Fiduciary Considerations (applied by selected entity type)

9.1 **Investment adviser.** The Investment Manager acts as a fiduciary. It discloses its use of autonomous agents, affiliated Underlying Funds and related conflicts in Form ADV, and keeps records under the Advisers Act books-and-records rule (rule CONF-AFFILIATE-DISCLOSE).

9.2 **Registered fund.** Fund-of-funds investments are made in reliance on Rule 12d1-4 or another applicable exemption, with the required conditions documented (FOF-12D1). The derivatives (Rule 18f-4) and liquidity (Rule 22e-4) programs apply as described in §§7.4–7.5. The fund board receives the CCO's reports.

9.3 **ERISA plan / CIT.** The Series is managed under ERISA's prudence and loyalty standards. Any use of affiliated Underlying Funds must be covered by an applicable prohibited-transaction exemption or fee arrangement reviewed by the plan fiduciary (ERISA-AFFILIATE-PT). Where a Fund is a qualified default investment alternative, the Investment Manager supports the plan sponsor's QDIA notice and fee-disclosure obligations. Consistent with DOL guidance, the plan fiduciary should understand the glide path, whether it is "to" or "through" retirement, the Underlying Funds and the fees.

9.4 **Broker-dealer.** If the Series is distributed or supervised through a broker-dealer, supervisory, communications and record-keeping obligations apply to Meridian outputs used externally.

9.5 **Marketing.** Simulated or back-tested results produced by the platform are hypothetical performance. They may be used only in compliance with applicable marketing rules and with Compliance approval. Claims about the platform's AI capabilities must be accurate and substantiated.

## 10. Use of Autonomous Agents

10.1 **Authority.** Agents operate only within this IPS and the machine-readable policy compiled from it. Agents have no authority to trade, approve proposals, amend policy, waive limits or sign attestations.

10.2 **Deterministic controls.** All limits in §§5, 7 are evaluated by a deterministic rule engine. An agent cannot change a rule result.

10.3 **Records.** Every agent output (inputs, data snapshot, model version, prompt version, code version, rationale, alternatives considered, peer reviews, votes and dissent) is written to an immutable decision ledger. The ledger is retained for the longest period required by the selected regimes.

10.4 **Approval matrix.**

| Action | Approver(s) |
|---|---|
| Glide-path change | Governing Body (on IC recommendation) |
| Tactical tilt within ranges | Portfolio Manager + Risk |
| PM/analyst weight adjustment to a proposal | Portfolio Manager + Risk |
| Operating risk-budget change (within the TE limit) | Portfolio Manager + Risk (requester cannot approve) |
| Routine rebalance to targets | Portfolio Manager |
| IPS / machine-readable policy change | Portfolio Manager + Chief Compliance Officer; adoption by Governing Body |
| Exception to any limit | Chief Compliance Officer (time-limited, with remediation plan) |
| Change of autonomy level | Governing Body |

10.5 **Model risk.** Agents, skills and analytics are inventoried, independently validated before production use and at least annually, and changed only through documented change control. Self-improvement agents may propose changes but cannot deploy them.

10.6 **Kill switch.** The Portfolio Manager, CCO or IC Chair may suspend all agent activity at any time. While suspended, the Funds are managed to their strategic weights by authorized persons.

## 11. Rebalancing

11.1 **Calendar.** Each Fund is reviewed quarterly and rebalanced to its target weights (strategic plus approved tactical tilts).

11.2 **Drift.** Off-cycle rebalancing is required if any asset class drifts more than 2.0 percentage points from target.

11.3 **Glide-path roll-down.** Strategic weights move monthly along the glide path. Cash flows are used first to move toward targets.

11.4 **Triggers for off-cycle review.** A macro-regime change, a breach of any invalidation condition stated by the CIO agent in the most recent board memo, a hard-limit breach, or a drawdown trigger in §5.4.

## 12. Monitoring, Reporting and Records

| Report | Frequency | Recipient |
|---|---|---|
| Board memo (allocation, rationale, dissent, risks, compliance statement) | Quarterly | Governing Body, IC |
| Performance vs. policy and peer benchmarks | Monthly / quarterly | IC |
| Risk report (volatility, tracking error, drawdown, exposures) | Monthly | IC, Risk |
| Compliance report (rule results, exceptions, attestations) | Quarterly; breaches within 1 business day | CCO, Governing Body |
| Underlying Fund monitoring and watch list | Quarterly | IC |
| Annual IPS and glide-path review | Annually | Governing Body |

Records are kept for no less than the longest retention period required by the selected entity types (at least five years), on immutable storage.

## 13. Review and Amendment

This IPS is reviewed at least annually and whenever there is a material change in law, the investor profile, the operating entity, the capital market environment or the Meridian platform's autonomy level. Amendments require approval by the Governing Body and must be reflected in the machine-readable policy before taking effect.

## 14. Adoption

| Role | Name | Signature | Date |
|---|---|---|---|
| Chair, Governing Body | | | |
| Chief Investment Officer | | | |
| Chief Compliance Officer | | | |
| Portfolio Manager | Dev (Alex Eaton) | | |

---

### Appendix A — Glide path chart data
See `policies/target_date_series.yaml` → `glide_path.anchors`.

### Appendix B — Rule cross-reference
Every rule ID in this IPS appears in `policies/target_date_series.yaml` → `rules`, with the IPS section it implements.

### Appendix C — Real-world references used as models for structure
- CFA Institute, *Elements of an Investment Policy Statement for Institutional Investors* (2010).
- U.S. Department of Labor, *Target Date Retirement Funds — Tips for ERISA Plan Fiduciaries* (2013).
- Public prospectuses and glide-path disclosures of large U.S. target-date series (structure of "through" glide paths, 5-year vintages, landing seven years after target).
