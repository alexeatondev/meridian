# 15 — User Personas

**Version 0.3 · 2026-11-10 · Living document: refine after every round of user testing (doc 16) and as new roles are added.**

Personas describe the people Meridian must serve: what they do for the business, what their days look like, what they cannot do without, and what they need from an agentic portfolio platform. Each ends with what Meridian covers today, the gaps, and the top three tasks used for user testing (doc 16). Names are fictional.

Sources are listed at the end. Role descriptions draw on current job descriptions at large multi-asset and target-date managers, SEC examination priorities, the DOL's target-date guidance for ERISA fiduciaries, the IIA Global Internal Audit Standards and model-risk guidance (SR 11-7).

## Fictional roster (for testing and demos)

Made-up people assigned to each persona, so test scripts, demo data and screenshots use consistent names. **None of them is a real person or a real appointment.** The automated browser tests sign in as these names.

| Person | Title | Workspace roles | Permissions | Notes |
|---|---|---|---|---|
| Maya Chen | Senior Portfolio Manager, Target-Date | `portfolio_manager` | — | Primary PM approver |
| Jordan Ellis | Portfolio Manager | `portfolio_manager` | — | Second PM: approves risk-budget changes Maya requests (requester can't self-approve) |
| Daniel Okafor | Investment Risk Manager | `risk` | — | Risk co-approver |
| Kenji Watanabe | Investment Risk Analyst | `risk` | — | Builds risk packs; backup risk approver |
| Priya Raman | Multi-Asset Research Analyst (CMAs) | `analyst` | — | Proposes weight adjustments for approval |
| Marcus Webb | Manager Research Analyst | `manager_selection` | — | |
| Elena Rossi | Chief Investment Officer, IC Chair | `leadership` | `investment_committee` | |
| Thomas Greene | Independent Investment Committee Member | `leadership` | `investment_committee` | |
| Catherine Moore | Chief Executive Officer | `leadership` | — | Sees committee material; doesn't vote |
| **Robert Hayes** | **Chief Compliance Officer (temporary fictional placeholder)** | `compliance` | `chief_compliance_officer` | Recorded in `config/entity_profile.yaml` as a placeholder: the CCO role stays a **production blocker** until a real, named CCO is appointed |
| Nina Alvarez | Compliance Analyst | `compliance` | — | Reviews rule results; can't approve as CCO |
| Grace Liu | Internal Audit Manager | `audit` | — | Read-only |
| Sam Patel | Platform Admin & Model Risk Owner | `admin` | — | Read-only Console; manages users and deploys |

**Segregation of duties in the roster.** No one holds both a proposing role (PM, analyst) and the committee or CCO permission; Risk is held by different people from the PMs.

**Permissions vs workspaces.** Workspace roles decide which screens a person sees. Permissions (`investment_committee`, `chief_compliance_officer`) are switched on or off per person on top of that and allow recording decisions that need that authority (IPS §10.4). A permission alone gives no screens: an IC member also needs the `leadership` workspace.

## Cross-cutting themes

| Theme | Why it matters to every role |
|---|---|
| **Trust through traceability** | Every role must be able to say *why* a number or decision is what it is. Regulators now ask firms to show how AI use is supervised and to back up any claims about AI capabilities. |
| **Exceptions first** | Busy professionals want what changed, what breached and what needs them, not every number. |
| **One source of truth** | PM, risk, compliance and audit must see the same weights, limits and records, as of the same date. |
| **Evidence on demand** | Committee packs, exam requests and audit tests all need exportable, dated evidence. |
| **Segregation of duties** | Whoever proposes can't approve their own change; approvers are named people. |

---

## 1. Portfolio Manager: "Maya Chen, Senior PM, Target-Date Multi-Asset"

**Business role.** Owns investment decisions for the target-date series within the IPS: strategic allocation along the glide path, tactical tilts within ranges, underlying fund and manager mix, and rebalancing. Accountable to the investment committee for results and to compliance for staying within limits. At large firms a small team of PMs runs a whole series, supported by researchers and associate PMs who own the daily process: start-of-day positions, cash and rebalancing.

**Typical day.**
- *Early:* overnight markets and news; start-of-day positions and cash; anything that moved a fund near a range edge.
- *Mid-day:* proposals and research from the team; tactical asset allocation discussion; risk check with the risk team; approve or adjust rebalances.
- *Periodic:* monthly or quarterly allocation review, committee materials, client and consultant questions about the glide path and fees.

**Critical needs.**
- Current vs proposed vs last approved weights, per vintage, in one view.
- Expected return, volatility, tracking error and risk budget used, before approving.
- Compliance status before, not after, a decision.
- The reasoning and dissent behind any agent proposal, in plain language.
- Fast what-ifs: "what if I take 2% out of EM?"

**Pain points.** Rebuilding the same spreadsheet each month; risk and compliance numbers that come back a day later; explaining decisions to the committee from scattered notes.

**What they need from Meridian.**
- A queue of proposals that need them, with the three biggest changes and why.
- Adjust in place, with risk and compliance recalculated instantly and the override recorded.
- A one-click committee summary (board memo) that matches what was approved.
- Confidence the agents stay inside the IPS: hard limits enforced in code, not by the model.

**Covered today:** Positioning with drill-down, proposals per vintage with **Why?** evidence, adjustments with instant recompute, **changes since last run**, risk budget, fund risk, look-through, approvals with reason and checklist, exceptions, board memo. **Trading (2026-11-10):** cashflow intake, three allocation tables, pro-rata trade lists, tilts, exclusions, full exits, single-security tickets, tranches, current vs post-trade preview with IPS check, approval and the Charles River import file (shadow mode, example positions).
**Gaps:** No rebalance trades that close gaps to target; no what-if on the proposal itself (the scenario builder covers factor shocks only); no performance or attribution; positions are example data until custodian/TA files are connected; Charles River results don't come back yet.
**UAT top tasks:** (1) review and approve a vintage's proposal; (2) adjust a weight and see risk and compliance update; (3) explain the largest change using the memo and dissent.

---

## 2. Risk Analytics: "Daniel Okafor, Investment Risk Manager"

**Business role.** Independent of the PMs, measures and reports investment risk: ex-ante volatility, tracking error, VaR, factor exposures, concentration, liquidity and stress results. Checks that each fund stays within its risk profile and guidelines, investigates triggers, escalates breaches and follows remediation. Produces risk packs for PMs, senior management and risk or oversight committees. For registered funds, supports the liquidity risk program and derivatives risk (VaR) requirements.

**Typical day.**
- *Morning:* overnight alerts and limit monitoring report; investigate anything near or over a threshold; check data quality.
- *Day:* deep dives for PMs (what drives active risk, stress scenarios); second-approver role for material changes.
- *Month/quarter end:* fund risk, stress testing, liquidity and exposure reports for committees.

**Critical needs.**
- The same covariance and factor model as portfolio construction, so numbers reconcile.
- Total, benchmark and active risk with contributions that add up.
- Stress tests from normal to extreme, historical and hypothetical, with clear assumptions.
- Point-in-time history: what the risk *was* at the time, not recomputed with today's data.
- Clear escalation trail: who was told, when, and what was done.

**Pain points.** Reconciling vendor risk numbers with the PM's; stress scenarios buried in spreadsheets; no record of when a warning was raised.

**What they need from Meridian.**
- Exceptions dashboard first (warnings, near-limit funds), then drill-down.
- Factor, stress and history views with exportable data.
- Model transparency: definitions, data sources and known limitations on the screen.
- A recorded escalation or sign-off on each risk review.

**Covered today:** Fund risk, factor risk with 18-month history, stress tests (12 historical, 7 hypothetical, scenario builder), risk history with point-in-time storage, look-through and ticker search, candidate risk, risk budget with proximity colors, second-approver role, exceptions (raise and work cases), read-only Trading with post-trade preview.
**Gaps:** No liquidity metrics (days to liquidate, 22e-4 buckets), no expected shortfall or VaR backtesting, no ex-post vs ex-ante comparison (doc 13 §8, awaiting direction); no recorded "risk review" sign-off separate from approvals; no CSV export from most Console screens; Treasury issuer names split in look-through (F-4).
**UAT top tasks:** (1) find the vintage closest to its tracking-error budget and explain why; (2) run a "rates +100bp, equities −20%" scenario and read the loss by vintage; (3) co-approve an adjusted proposal as Risk.

---

## 3. Research / Strategist: "Priya Raman, Multi-Asset Research Analyst (Capital Markets Assumptions)"

**Business role.** Builds and maintains the long-term capital market assumptions (expected returns, risk, correlations) that feed strategic allocation, typically updated annually or quarterly and reviewed by the investment committee. Researches portfolio construction methods, valuation signals and the macro regime, and translates bottom-up views from asset-class specialists into forward-looking inputs.

**Typical day.**
- *Ongoing:* model maintenance, data quality, research on new methods.
- *Update cycle:* recompute CMAs by method, compare with external surveys and the prior update, write the rationale, present to the committee.
- *Ad hoc:* sensitivity analysis for the PM ("how much does the allocation move if equity returns fall 1%?").

**Critical needs.**
- Every method's estimate side by side, with the judge's choice and the reason.
- Forecast vs realized tracking for each method over time.
- Sensitivity of the allocation to each assumption.
- Change control: new or changed methods tested before they affect portfolios.

**Pain points.** Assumptions that feed decisions without anyone seeing how they were chosen; methods that change silently.

**What they need from Meridian.**
- A CMA workbench with every method, confidence, judge choice and history.
- Ability to propose a change (method, weight, bound) as a change request with evidence.
- Notebook access to reproduce and extend any Console number.

**Covered today:** CMA tab with **Why?**, agent votes, positioning and adjustments, changes since last run, factor risk, look-through; research notebook (CMA lab) and risk notebook; can load cashflows and prepare trade lists in Trading.
**Gaps:** No forecast-vs-realized history; no in-app change-request flow for methods; no allocation-sensitivity view in the Console.
**UAT top tasks:** (1) find the asset class where the CMA judge moved furthest from the auto-blend and read why; (2) see which PC methods the agents ranked highest; (3) propose a weight adjustment as analyst for PM/Risk approval.

---

## 4. Manager Selection: "Marcus Webb, Manager Research Analyst"

**Business role.** Sources, evaluates and monitors the funds and managers used as building blocks. Investment due diligence covers strategy, team, process, performance, style and fees; operational due diligence covers service providers, valuation, compliance, cybersecurity, financial statements and conflicts. Writes recommendations for a manager-selection or investment committee and keeps a watch list.

**Typical day.**
- *Ongoing:* monitor current managers (performance, style drift, team changes, assets); read updated offering documents and financial statements.
- *Pipeline:* questionnaires, calls and meetings with candidates; scoring; peer review within the team.
- *Committee:* recommendation write-ups with strengths, weaknesses and a clear opinion.

**Critical needs.**
- Holdings-based and returns-based view of each underlying fund.
- What each building block contributes to risk, fees and exposures at the total-fund level.
- Document-backed claims: every fact linked to its source page.
- A watch list with triggers and history.

**Pain points.** Due diligence questionnaires that sit unread; overlap between funds discovered late; no single place for the decision history on a manager.

**What they need from Meridian.**
- Look-through of every building block, including overlap between funds.
- Due diligence workflow with agent extraction and source links (roadmap Phase 5).
- Manager scorecards and monitoring alerts.

**Covered today:** Funds & vintages, underlying funds with return and holdings proxies, look-through and search (with holdings date), positioning; Trading fund pages list held securities and candidates not yet held.
**Gaps:** Due diligence workflow, scorecards, watch list and alerts (Phase 5); no fee view; no overlap analysis between building blocks.
**UAT top tasks:** (1) find which building blocks hold a given issuer and how much each vintage owns; (2) open an underlying fund and read its holdings and data date; (3) compare the underlying fund mix of two vintages.

---

## 5. Leadership / Investment Committee: "Elena Rossi, CIO and Investment Committee Chair"

**Business role.** Sets investment philosophy and approves strategic decisions: glide path, asset-allocation policy, new products, autonomy levels and material exceptions. As an ERISA fiduciary (for plan products), must follow and document a prudent process for selecting and periodically reviewing the target-date series: understand the glide path ("to" or "through" retirement), the underlying funds and the fees, and record the review.

**Typical day.**
- *Weekly:* short status and exception briefings; approvals that need the committee.
- *Monthly/quarterly:* committee meetings with performance, risk, compliance and recommendations; the record of what was decided and why.
- *Annually:* glide-path and CMA review; product and resourcing decisions.

**Critical needs.**
- A clear one-page view: recommendation, key risks, compliance status, dissent.
- Confidence that controls work: who approved what, and that nothing bypassed policy.
- Documented, defensible process for regulators, boards and plan sponsors.
- Control over the pace of automation (autonomy levels, kill switch).

**Pain points.** Long committee packs with the key point buried; decisions that can't be traced back to the analysis.

**What they need from Meridian.**
- Board memo with recommendation, risks, changes, compliance statement and dissent.
- Decision queue for items that need the committee.
- Governance controls: autonomy level per pipeline, pause switch, KPIs (overrides, accuracy, breaches).

**Covered today:** Home with outstanding approvals, blockers and compliance status; board memo; changes since last run; fund risk; stress tests; risk budget; metrics; glide path; approvals with the Investment Committee permission; exceptions; read-only Trading.
**Gaps:** No kill switch or autonomy controls in the UI; no KPI view (override rate, forecast accuracy, parallel-run comparison); no fee review.
**UAT top tasks:** (1) read the board memo and state the recommendation, top risk and any dissent; (2) check which vintages need committee approval; (3) see each vintage's worst historical stress loss.

---

## 6. Compliance: "Robert Hayes, Chief Compliance Officer" (and compliance analysts)

**Business role.** Administers the compliance program required under the Advisers Act Compliance Rule (and the fund compliance rule for registered funds): written policies and procedures, testing, at least an annual review of their adequacy and effectiveness, and remediation. Recent SEC exam priorities emphasize compliance-program effectiveness in marketing, valuation, trading, portfolio management, disclosures and custody; how firms supervise AI and whether their AI claims are accurate; and data-protection programs under amended Regulation S-P.

**Typical day.**
- *Daily/weekly:* guideline and limit exceptions; trade and portfolio monitoring results; questions from the business.
- *Periodic:* forensic testing, policy updates, training, marketing review, regulatory filings calendar.
- *Annual:* compliance review with documented testing, findings and remediation; exam readiness.

**Critical needs.**
- Deterministic rule results with the rule, measured value, limit and data lineage.
- Exception queue with owner, deadline and resolution.
- Proof of supervision of AI: what the agents did, what humans approved, and that agents can't override rules.
- Evidence packs for exams and the annual review.

**Pain points.** Testing by sampling spreadsheets; no audit trail of who saw what before approving; AI tools whose outputs can't be explained to an examiner.

**What they need from Meridian.**
- Compliance center: rules by policy, results per run, exceptions, attestations.
- Approval audit (approver, reason quality, time on screen).
- One-click evidence export by decision, portfolio, rule or date range.
- The Agentic Compliance Officer's draft review, clearly marked as draft and never a sign-off.

**Covered today:** Compliance tab with rule results and **Why?**; **exception workflow** (owner, due date, notes, remediation, CCO time-limited acceptance, close with separation of duties); ledger search across runs with CSV; evidence-pack download; compliance report (ACO draft); look-through for issuer exposure; trading records (type `trading`, route changes `routes.change`) in the ledger; read-only access review and access log.
**Gaps:** No approval-quality audit view; no annual-review package; no marketing-review routing; the CCO is still a placeholder (production blocker).
**UAT top tasks:** (1) find any WARN or FAIL and read the rule, value and limit; (2) open the decision ledger and trace one approval to the proposal it approved; (3) read the ACO report and list the production blockers.

---

## 7. Audit: "Grace Liu, Internal Audit Manager" (and external auditors)

**Business role.** Provides independent assurance over governance, risk management and controls. Under the IIA Global Internal Audit Standards (effective January 2025), audit plans are risk-based, work is evidenced, and findings are reported to the board or audit committee. For an AI-driven investment process, audit tests whether controls are designed and operating: approvals, segregation of duties, change control, data integrity and record retention.

**Typical day.**
- *Planning:* risk assessment, scoping, request lists.
- *Fieldwork:* walkthroughs, sample selection, re-performance, evidence review.
- *Reporting:* findings, management responses, follow-up on remediation.

**Critical needs.**
- Read-only access to complete, tamper-evident records.
- Ability to re-perform: recompute hashes, reproduce a run from its snapshot.
- Population-level queries (all approvals in a period) to draw samples.
- Clear evidence of who did what, when, and under which policy version.

**Pain points.** Evidence spread across email and spreadsheets; records that could have been edited; systems that can't produce a full population.

**What they need from Meridian.**
- Ledger explorer with search and filters, lineage, and **Verify integrity**.
- Evidence pack export with integrity instructions.
- Replay of what an approver saw.

**Covered today:** Decision ledger with hash-chain verification, **search across runs and CSV**, **evidence-pack download**, exceptions, compliance tab and report, read-only access review and log; append-only enforcement in the database for ledger and access log.
**Gaps:** No replay of an approver's screen; no WORM copy (deferred to production because it adds cost).
**UAT top tasks:** (1) confirm the ledger verifies and find the approvals for one vintage; (2) identify who approved and their stated reason; (3) confirm a user can't approve the same vintage in two roles (segregation of duties).

---

## 8. Platform Admin / Model Risk Owner: "Sam Patel, Investment Technology & Model Risk"

**Business role.** Keeps the platform running and governed: user access, deployments, cost, and the inventory of models and agents. Model-risk practice (SR 11-7, increasingly applied to AI and LLMs) expects an inventory of every model with its purpose, owner, risk tier, validation status and next review date; independent validation; ongoing monitoring; and change control.

**Typical day.**
- *Ongoing:* access requests, deployments, cost and health checks.
- *Periodic:* access reviews, model inventory updates, validation scheduling, change-request approvals.

**Critical needs.**
- Simple, auditable user and role management.
- Model and agent inventory with versions, owners and validation status.
- Safe deploys and rollback; cost guardrails; monitoring.

**What they need from Meridian.**
- Agent registry and change requests in the app.
- Access review report (who has which roles).
- Health and cost dashboard.

**Covered today:** User access screen (add, edit, permissions on/off including Investment Committee, CCO and Trade route manager, disable/enable, delete, access review with CSV, append-only access log, immediate sign-out on access changes); deploys and runs through GitHub Actions; cost guard; runbooks (doc 14).
**Gaps:** No agent registry or model inventory; no alarms (deferred for cost).
**UAT top tasks:** (1) add a user with specific roles and confirm what they see; (2) disable a user and confirm sign-in is blocked; (3) find the deploy that changed the app last and what it changed.

---

## Gap summary (for prioritization)

| Gap | Roles that need it | Roadmap fit |
|---|---|---|
| ~~"Why?" link from any number to its decision record; diff vs last run~~ | PM, Leadership, Compliance, Audit | **Built 2026-11-10** |
| ~~Evidence-pack export button; ledger search across runs~~ | Compliance, Audit | **Built 2026-11-10** |
| ~~Exception workflow (owner, deadline, resolution)~~ | Compliance, Risk | **Built 2026-11-10** |
| ~~Cashflow trading, routing, tilts, exclusions, exits, tickets, tranches, Charles River file~~ | PM, Analyst, Compliance | **Built 2026-11-10** (doc 17) |
| Rebalance trades; real positions from custodians/TAs; Charles River results back | PM, Analyst, Risk | Doc 17 |
| Derivatives, in-kind, mandates, margin and leverage, capital calls | PM, Risk, Compliance | Doc 17 Phase F (needs answers to §6 questions 6–8) |
| Kill switch and autonomy controls; governance KPIs | Leadership, Admin | Phase 2/3 |
| Risk add-ons: liquidity, expected shortfall, VaR backtest, ex-post vs ex-ante | Risk, Compliance | Doc 13 §8 (awaiting direction) |
| Performance and attribution | PM, Leadership, Manager Selection | Not yet planned |
| CMA forecast-vs-realized; method change requests | Research | Phase 3/7 |
| Due diligence workflow, scorecards, watch list, fees, overlap | Manager Selection | Phase 5 |
| Agent registry, model inventory (access review and user management built 2026-11-10) | Admin / Model Risk | Phase 7/8 |

## Sources
- [A day in the life of a multi-asset portfolio manager (Investment Week)](https://investmentweek.co.uk/investment-week/sponsored/3018582/industry-voice-day-life-multi-asset-portfolio-manager)
- [Associate Portfolio Manager, Target-Date Multi-Asset (Nuveen job description)](https://jobsnyc.usnlx.com/new-york-ny/nuveen-associate-portfolio-manager-target-date-multi-asset-tdma/9348E885CE5B4B2AAA42D23AA2A6B190/job)
- [Target Date Funds – Portfolio Manager (Fidelity job description)](https://jobs.fidelity.com/job-details/21188058)
- [Risk Analyst in Asset Management (BNP Paribas AM job description)](https://group.bnpparibas/en/careers/job-offer/assistant-manager-inv-rimc-2)
- [Investment Risk & Analytics Specialist (job description)](https://www.albedis.com/stellenangebot/3933951019-investment-risk-analytics-specialist-basel-de/)
- [Solutions Analyst – Capital Markets Assumptions (Capital Group job description)](https://www.wallstreetcareers.com/jobs/769083085/apply)
- [Manager Research Analyst (Schroders job description)](https://careers.cfainstitute.org/job/8968665/manager-research-analyst-fund-analyst-/)
- [Operational Due Diligence Analyst (BNP Paribas AM job description)](https://group.bnpparibas/en/careers/job-offer/operational-due-diligence-analyst)
- [Target Date Retirement Funds – Tips for ERISA Plan Fiduciaries (U.S. DOL)](https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/resource-center/fact-sheets/target-date-retirement-funds-tips-for-erisa-plan-fiduciaries)
- [SEC Division of Examinations announces 2026 examination priorities (Weil via Mondaq)](https://www.mondaq.com/unitedstates/financial-services/1711470/sec-division-of-examinations-announces-2026-examination-priorities)
- [2026 SEC examination priorities for investment advisers (Proskauer)](https://www.proskauer.com/alert/2026-sec-examination-priorities-for-investment-advisers)
- [SEC exam observations on annual compliance reviews, Sept 2026 (King & Spalding)](https://www.kslaw.com/insights/articles/sec-division-of-examinations-publishes-observations-on-investment-adviser-annual-compliance-reviews)
- [Complete Global Internal Audit Standards (The IIA)](https://theiia.org/en/content/standards/complete-global-internal-audit-standards)
- [Model risk governance under SR 11-7](https://presencis.com/regulations/occ-sr117/article-model-governance-detail/)
