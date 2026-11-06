# 06 — User Guides by Role

**Version 0.1 · 2026-11-06 · Applies to: Meridian v1.0 (planned). Screens named here are the target design and will be updated as built.**

## Common concepts (all users)
- **Run:** one pipeline execution (e.g., quarterly SAA). Find runs under *Runs*.
- **Proposal:** an agent-generated recommendation awaiting human action. Find yours under *My Queue*.
- **Decision Record (DR):** the permanent record behind every number. Click **Why?** next to any figure.
- **Status chips:** `PASS / WARN / FAIL` (compliance), `L2/L3/L4` (autonomy of the pipeline), `Dissent` (minority views exist — read them).
- **Ask Meridian:** type a question; answers cite DR IDs. It only sees what you're entitled to see and cannot change anything.
- **Golden rule:** your approval is a decision you own. Read the rationale and dissent; record your reason.

---

## 1. Portfolio Manager
**Your top tasks**
1. *Review a rebalance proposal* — My Queue → open proposal → check: target vs. current weights, expected return/vol/TE, compliance chips, CRO risk report, dissent panel → **Approve / Modify / Reject** with reason.
2. *Modify a proposal* — use **Adjust** to change weights or constraints; Meridian re-runs compliance and risk instantly; your edit is recorded as an *override* DR.
3. *Run a what-if* — Portfolio cockpit → **Scenario** → change CMAs, add a constraint, or shock a factor → compare against the proposal.
4. *Understand a change* — **Diff vs. last run** shows the biggest weight changes with the agents' explanations.
5. *Request an off-cycle run* — Runs → New → choose pipeline and scope; requires your entitlement for that portfolio.

**Good practice:** challenge at least one assumption per approval; if the CIO memo's "what would make this wrong" conditions are already near, escalate.

## 2. Risk Analytics
Workspace tabs: **Fund risk · Factor risk · Stress tests · Risk history · Look-through & search · Risk budget · Metrics · Candidate risk**. Methods and definitions: `docs/12-risk-analytics.md`.
1. *Fund-level check* — **Fund risk**: scan every vintage's total vs benchmark risk, active risk, relative duration, relative credit spread duration, VaR 95 / active VaR 95 and diversification. Click a vintage to drill down: risk breakdown by asset class (expand Equity → US/Non-US → size, Developed/Emerging; Fixed Income → long/short-dated → core/HY/TIPS/short-term income) or by underlying fund, and the weight-vs-risk chart (a holding whose risk bar is far longer than its weight bar is a concentrated risk).
2. *Factor review* — **Factor risk**: switch Total / Active / Benchmark; read which factors drive variance and how exposures differ from the glide path. In **Factor history** pick *All except Equity* to see rates, credit, inflation and real-asset risk over the last 18 months, or drill into one family.
3. *Stress testing* — **Stress tests**: choose Fund / Benchmark / Active, read historical replays, then step the hypothetical ladder from Normal (1σ) to Crisis (5σ). Use **Build a scenario** for ad-hoc moves (e.g. equities −20%, yields +100bp); switch Correlated/Isolated to see how much of the loss comes from correlation assumptions. Scenario definitions live in `config/risk.yaml` (change-controlled).
4. *Trend monitoring* — **Risk history**: pick a metric; the tooltip and table show whether each month is a recorded point-in-time snapshot, reconstructed from recorded positions, or reconstructed from the glide path.
5. *Look-through & search* — type a ticker or name (e.g. `NVDA`, `Treasury`) to see every vintage's exposure and the underlying funds it comes through; expand an underlying fund to see its holdings.
6. *Limit monitoring* — **Risk budget** shows % of the tracking-error budget used per vintage, with proximity colors at the policy warning threshold.
7. *Validate CRO reports* — **Candidate risk**: each PC method's ex-ante vol, TE vs limit and compliance before the CIO ensemble.
8. *Approve material rebalances* — second approver where the approval matrix requires Risk.
9. *Deeper work* — `notebooks/04_risk_analytics_workbench.ipynb` reproduces every console figure and lets you change weights, scenarios and factors.

## 3. Research
1. *Own CMA methods* — CMA workbench → per asset class: each method's estimate, confidence, judge choice, history of forecast vs. realized.
2. *Edit an agent or skill* — changes are made as pull requests (Meridian's **Change Request** screen or git); require validation pass + reviewer approval before production.
3. *Review PC-researcher proposals* — Research lab → new methods with shadow results; recommend promotion or retirement.
4. *Review meta-learner suggestions* — Change requests tagged `meta-learner` include evidence (hit rates, errors by regime); accept, amend or reject.
5. *Signal library* — define new signals with owner, method, data and tests.

## 4. Manager Selection
1. *Manager universe* — screen by strategy, style, AUM, track record, fees, liquidity terms.
2. *Run due diligence* — DD workflow → upload DDQ, ADV, offering docs, letters → DD agents extract and summarize, flag inconsistencies, map to scoring rubric; operational DD checklist tracked separately. Every extracted claim links to its page in the source document.
3. *Quant review* — returns-based style analysis, alpha/beta, drawdowns, capture ratios, holdings-based analysis where available, fee drag after layering.
4. *Manager committee* — agent peer review and vote produce a ranked list with dissent; you finalize the recommendation for IC.
5. *Monitoring* — manager-event watcher alerts (team departures, style drift, AUM swings, performance outside expected range).
6. *Look-through* — see FoF exposures aggregated to security/factor level, with staleness flags for lagged or estimated holdings.

## 5. Leadership / CIO / Investment Committee
1. *Read the board memo* — recommendation, expected performance vs. benchmark, macro rationale, largest positions, changes since last review, key risks, rebalancing plan, IPS compliance statement, dissenting views.
2. *Decision queue* — items requiring IC approval (SAA changes, autonomy changes, new pipelines, exceptions above threshold).
3. *Set autonomy* — Governance → pipelines → current level, proposed change, risk assessment → approve (GOV-3).
4. *KPIs* — cycle time, approvals vs. overrides, forecast accuracy, parallel-run comparison vs. human process, limit breaches.
5. *Kill switch* — Governance → **Pause**: globally or per pipeline. Use if behavior is unexpected; investigation workflow opens automatically.

## 6. Compliance
1. *Rule library* — Compliance center → rules by policy and portfolio; each rule shows source clause, logic, tests, history. Edits require your approval (PC-2).
2. *Exception queue* — breaches and warnings with measured value vs. limit, lineage, owner, remediation deadline.
3. *Approval audit* — filter approvals by approver, materiality, time-on-screen, missing/weak reasons.
4. *Agent scope surveillance* — blocked out-of-scope actions, web-source usage, policy-interpreter questions.
5. *Challenge sampling* — quarterly random sample of decisions assigned for written review (SUP-5).
6. *Exam response* — Evidence → **Export pack** by decision, portfolio, rule or date range (doc 05 §6).
7. *Marketing review* — any external material citing Meridian or backtests routed here (MKT-1/2).

## 7. Audit (internal & external)
Read-only. Ledger explorer → search by run, portfolio, agent, approver, date → open any DR → lineage graph → **Verify integrity** (recomputes hashes against WORM-anchored roots) → **Replay** approver screen → export evidence pack.

## 8. Platform Admin / Model Risk Owner
Agent registry (owners, tiers, versions, validation status) · change requests · model-version pinning · access management (SSO groups → roles → portfolio entitlements) · kill-switch tests · environment health.

---

## Appendix A — Approval checklist (print on every approval screen)
- [ ] I read the rationale and the dissent.
- [ ] Compliance shows PASS, or exceptions are approved.
- [ ] I understand the largest three changes and why.
- [ ] The "what would make this wrong" conditions are not already triggered.
- [ ] My reason is recorded.

## Appendix B — Glossary
**SAA** strategic asset allocation · **TAA** tactical asset allocation · **CMA** capital market assumptions · **PC** portfolio construction · **CRO agent** neutral risk-assessor agent · **CIO agent** ensemble decision agent · **IPS** investment policy statement · **DR** decision record · **Look-through** aggregation of underlying fund holdings · **Borda count** ranked-vote scoring · **LLM-as-judge** an LLM choosing among computed candidates within fixed bounds.
