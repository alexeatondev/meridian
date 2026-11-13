# 03 — Build Game Plan & Roadmap

**Version 0.9 · 2026-11-13 (console UX, Trading redesign, step-by-step guide)**

## Status (2026-11-13)
- **Repo:** github.com/alexeatondev/meridian · **App:** https://d3maw6l4k5cc0v.cloudfront.net (AWS us-east-2, CDK, GitHub OIDC, no stored keys) · **Cost:** about $1 spent so far (product owner's Cost Explorer check, 2026-11-10); budget $75/month with alerts and an automatic spend block.
- **Agent pipeline (Phase 1):** macro regime, 13 asset classes with CMA judge, covariance, 7 construction methods, peer review and Borda vote, CRO, CIO ensemble, board memo; real public data with synthetic only for some non-US valuations (flagged); live LLM judgment in the `agent-run` workflow; runs are ad hoc.
- **Governance (Phase 2):** deterministic compliance engine, Agentic Compliance Officer (draft only), hash-chained ledger that the database refuses to edit, approvals with reason and segregation of duties, Investment Committee / CCO / Trade route manager permissions, exceptions workflow, ledger search across runs, evidence pack. Not yet: kill switch, autonomy controls, WORM copy.
- **Workspaces (Phase 3):** eight role workspaces, **Why?** panels, changes since last run, risk analytics (fund, factor, stress, history, look-through), User access screen. UAT round 1 run by hand; 154 automated tests (76 in the browser). One shared app shell on every screen (app bar, My work inbox, in-app Help, in-page confirmations, persistent error messages, keyboard and screen-reader support; doc 11). Not yet: Ask Meridian.
- **Implementation (Phase 6, brought forward):** Trading screen in shadow mode with mutual fund and CIT product lines, cashflow intake (Excel/CSV/API), three allocation tables, pro-rata trade lists, tilts, exclusions, full exits, single-security tickets, tranches, ETF cash buffer, routing by security type, a task-based **New trade** builder with goal shortcuts and a now-vs-after impact view before saving (2026-11-13), IPS check, approval, mock Charles River file, rebalance, positions upload, fills and booking, bulk changes across product lines and IC-approved glide-path adjustments (doc 17); fund-level regulations with controls and obligations (doc 18). Positions, prices and the CIT line are example data.
- **Docs:** all docs checked and current on 2026-11-13; repository docs use the Project's numbers; user guide (doc 06 v0.8) rewritten so every task is numbered start-to-finish steps with "you're done when" and "if something goes wrong", 75 screenshots regenerated from the app, published as an illustrated page and served in the app under **Help**.

## Assessment (2026-11-10)
| Area | State | Comment |
|---|---|---|
| Phase 0 Foundations | Done | |
| Phase 1 SAA MVP | Mostly done | 7 of 20 construction methods and 13 of the paper's 18 asset classes; enough for the pilot. Agents run 50 sessions per run on the Agent SDK backend with read-only tools and spend caps (2026-11-11). Strategy review by agents added 2026-11-12: thesis, risk officer commentary, peer review with recorded random assignments, vote, revision by the shortlist, and an agent-drafted memo summary (doc 02 §4a). Weights, risk numbers, tallies and compliance stay code. Still to do: grow 7 methods to 20 and add the PC researcher |
| Phase 2 Governance | Mostly done | Kill switch, autonomy controls and WORM records missing; WORM deferred for cost |
| Phase 3 Workspaces | Mostly done | UAT run by Claude on the product owner's login; real people in each role have not tested; Ask Meridian not built |
| Phase 4 Multi-asset hierarchy | Partial | Look-through via public proxies; security-level positions exist only as example data |
| Phase 5 Manager selection | Not started | |
| Phase 6 Implementation | About half, shadow only | Built ahead of Phases 4–5 at the product owner's request |
| Phase 7 Learning agents | Not started | |
| Phase 8 Production readiness | Not started | Needs named people (CCO, IC sponsor, model-risk owner), counsel review, security hardening, WORM, parallel run ≥ 2 quarters |

**Main risks right now**
1. **Trading runs on example data.** Until real positions and cashflows arrive from SS&C and State Street (uploads work today), every trade list is a demonstration; fills are booked from a file or marked filled in shadow mode.
2. **The agent pipeline doesn't read approved glide-path adjustments.** Trading can now target the approved proposal (**Approved proposal** table) and the adjusted glide path, but the agents still build one proposal per vintage against the IPS glide path, shared by both product lines.
3. **One person holds every role.** Segregation of duties is enforced in code but has only been exercised with test logins.
4. **Security hardening is held** (admin deploy role, no MFA). Acceptable with test users only.
5. **No human CCO or counsel review.** Blocks production, not development.

## Built 2026-11-10 (evening)
- **Fund-level regulations (doc 18):** tag funds with US and ex-US regulations (ACT 40, ERISA, CIT/OCC 9.18, CFTC 4.5, UCITS, AIFMD, UK COLL, NI 81-102, SFC); controls checked on current holdings and on every trade list (FAIL blocks); obligations tracked with owner, due date and evidence; overdue obligations open an exception; removal and waivers need the CCO permission.
- **Next steps 1, 2, 4, 5 done:** Approved-proposal trading table and **rebalance** trade lists; **positions upload** and **fills with booking** (positions and cash update); F-4 (US Treasury issuer consolidated) and F-11 (pending adjustment on the risk budget) fixed; **market-holiday calendar** for tranche dates (2026–2028).
- 125 automated tests at the time; user guide updated with 50 screenshots.

## Built 2026-11-11
- **Bulk changes across product lines:** glide path (IC-approved, within IPS bands), Strategic table, tilts (security or asset class), exclusions, exits, roll-down and buffer, for all funds, all mutual funds, all CITs or one fund, with an optional vintage range (doc 17, doc 06 §10.9).

## Built 2026-11-11 (UX update)
- **One shell for every screen:** app bar with role-filtered navigation (Console, Trading, Regulations, User access), **My work** inbox across modules (trade lists to approve or fill, IC glide-path decisions, obligations due or overdue, exceptions owned), **Help** (the user guide in the app, opened at the current screen's section, with search), user and sign-out. Duplicate per-page links removed.
- **Feedback and safety:** in-page confirmation dialogs replace browser prompts (cancel cashflow, cancel trade list, delete account with typed email); error messages stay until dismissed; live character counters on reason fields; busy state prevents double submission; session-expiry dialog.
- **Navigation and accessibility:** console tabs grouped under Overview, Portfolio, Risk and Governance with an open-exceptions count; skip link, focus outlines, ARIA tablists with arrow keys, live regions, dark mode and reduced motion respected.
- Docs 06 (§1 rewritten, v0.7), 11 (v0.5), 16 (UX-1 to UX-8) updated; 5 new screenshots.

## Built 2026-11-12 and 2026-11-13
- **Agents on the Agent SDK**, cheapest model by default with one-line model switching (`config/models.yaml`, workflow dropdown), spend caps; **strategy review by agents** (thesis, risk officer, peer review, vote, revision, memo summary) with a code-computed fact sheet (doc 02 §4a).
- **Console UX (product-owner feedback):** a Home with series tiles, "needs your attention" and the series at a glance; mutual funds vs CITs on Funds & vintages and Positioning; series summaries; "What is being approved" on proposals; an approval queue with summaries; Agent votes in plain words; risk budget across the series with a before/after preview; glide-path adjustments from the console; ticker search that doesn't move the page.
- **Trading redesign:** **New trade** with four tasks (invest cashflows, rebalance, trade a security, exit) and **Start from your goal** shortcuts; tickets by amount or **to a target weight** with a live cash check; **See the impact** (dry run, nothing saved) showing totals, off-target bars by fund and each fund's asset mix now vs after against target and glide path; the same impact view on saved lists (doc 17, doc 06 §10).
- **Docs:** doc 06 rewritten step by step (v0.8) with 75 regenerated screenshots; docs 00, 02, 03, 11, 15, 16 (TRD-19 to TRD-23), 17 updated.

## Built 2026-11-13 (evening)
- **Approver permission:** approval authority is now its own permission (`approver`), switched on or off per person in User access and logged like the others. PM and Risk decisions on proposals, risk-budget changes and trade lists need it; without it a PM or Risk user reviews only. Analyst permissions unchanged.
- **Vintage picker:** glide-path changes (Console → Glide path) and every bulk change (Trading → Glide path & bulk changes) choose vintages by clicking them, with All / 2030–2045 / 2050–2070 / Clear, replacing From/To vintage boxes. Older range entries keep working.
- **"Portfolios & proposals" renamed "Proposals".**

## Next steps (not blocked, in order)
1. **Custom calculations (doc 17 item 13):** named, versioned sell-down and liquidity-capped templates that produce tranches.
2. **Leadership controls:** kill switch (pause per pipeline or globally) and autonomy level in the app, with ledger records; a KPI view (approvals vs overrides, exceptions, obligations on time).
3. **Feed approved glide-path adjustments to the agent pipeline** (it builds one proposal per vintage today, shared by both product lines).
4. **Fiscal year ends per fund** for annual and semiannual obligations (doc 18 §5).
5. **You:** run RISK-6 with the RCTest login; try the Trading (TRD) and Regulations (REG) scripts in doc 16; tag the real funds with their regulations once the CCO confirms them.

## Blocked (and what unblocks each)
| Item | Blocked by |
|---|---|
| Derivatives (17 #7) and margin and leverage (#18) | Your answer to doc 17 §6 Q6 (instruments in scope; 18f-4 limited-user status); CCO view on 18f-4 and §18 |
| Redemptions in kind (#14) | In-kind policy per fund, custodian/TA delivery format, liquidity program (22e-4); CCO |
| Mandates (#17) | Example domestic and international mandate documents (Q8) |
| Capital calls (#19) | Which vehicles make calls and how notices arrive (Q7) |
| Trade-list approval thresholds (PM alone vs PM + Risk) | Your answer to Q9 |
| Real positions and cashflows | Sample files or API access from SS&C (mutual funds) and State Street (CITs), plus their data terms |
| Real Charles River file, API, results back, official positions (IBOR) | **Held by you** (doc 17 §9); then Charles River version, hosting and import specification from your Charles River admins |
| Who holds the route permission; second approver for route changes | **Held by you** (doc 17 §9) |
| Security hardening (deploy-role split, MFA, approvals by user ID) | **Held by you** until more users join (doc 14 §12) |
| WORM copy, daily ledger anchor, longer backups, CloudWatch alarms | **Deferred to production by you** (adds AWS cost) |
| Scheduled monthly run; next ad hoc run | **Held by you** (cost) |
| Portfolio-level entitlements (F-3) | Your decision on who may see which funds |
| Risk add-ons (doc 13 §8) | Your direction |
| Vendor data (holdings, factor models, prices) and AI-use licensing | Vendor contracts |
| Confirming the regulation library (controls, citations, due dates, owners) | CCO and counsel (doc 18 §5) |
| Production go-live | Named human CCO, IC sponsor and model-risk owner; counsel review of regimes and the IPS (including whether it governs the CITs and whether `bank_cit` applies); written policies (doc 04 §6); independent validation; parallel run ≥ 2 quarters |

## Open UAT findings (remediate later; do not drop)
| ID | Finding | Plan |
|---|---|---|
| F-3 | Run data not filtered by entitlement | Entitlements design |
| F-4 | Issuer names not normalized in look-through | **Fixed 2026-11-10** for US Treasury; other issuers by a vendor security master |
| F-11 | Risk budget doesn't show pending adjustments | **Fixed 2026-11-10** ("With adjustment" column) |

## Backlog (held by the product owner; keep visible)
| Item | Status | Why it matters |
|---|---|---|
| Security hardening: split the GitHub deploy role, require a GitHub environment, require MFA for approvers and admins, record approvals against the Cognito user ID/email (doc 14 §12) | **Held** until later in the build; must be done before anyone beyond test users signs in | Least privilege; unambiguous identity for audit |
| WORM evidence copy (S3 Object Lock), daily ledger anchor, longer database backups | **Deferred to production** (adds AWS cost) | Books and records (doc 04 REC-2/REC-3) |
| Scheduled monthly agent run with notifications | **Held**: runs stay ad hoc during development | Operating loop |
| Next ad hoc run (as of 2026-11-30) | **Held** | Gives "Changes since last run" real data |
| CloudWatch alarms; Node 20 action updates; remaining least-privilege steps | Backlog | Operations |
| **Friendly web address** (e.g. `meridian.<your-domain>` instead of `d3maw6l4k5cc0v.cloudfront.net`). A `*.cloudfront.net` name can't be chosen; it needs a domain you own (about $15/year), an ACM certificate in us-east-1 (the organization SCP blocks the deploy role there, so you'd request it in the console or allow it), a DNS record (Route 53 about $0.50/month), the CloudFront alternate name, and new Cognito callback URLs (doc 14 §12) | **Held until production** (raised 2026-11-11) | Easier to remember and share; looks like the firm's own system |
| Risk add-ons (doc 13 §8); vendor data; second product type; human CCO | Awaiting your direction | Product scope |
| **Question for the CCO and counsel:** does the IPS (doc 07) also govern the target-date CITs, or do they need their own investment policy under the declaration of trust? | Open (raised 2026-11-10) | Every CIT trade is checked against the mutual-fund IPS today |
| **Question for the CCO and counsel:** should the firm-level `bank_cit` entity pack (doc 08) be switched on for the CITs? | Open (raised 2026-11-10) | Adds bank-trustee obligations, roles and retention |

## Strategy in one paragraph
Rebuild the paper's SAA pipeline first on public data in **shadow mode** (no money moves), wrapped from day one in the decision ledger and the compliance engine — those two are what make this a product rather than a research demo. Then widen: portfolio hierarchy and look-through, fixed income and derivatives analytics, manager selection/FoF, and finally implementation proposals to your OMS. Learning agents come last, behind change control. Run in parallel against the human process for at least two quarters before any approval workflow is live.

## Phases

| Phase | Weeks* | Outcome | Exit criteria |
|---|---|---|---|
| **0 Foundations** | 0–3 | Decisions made, repo, schemas, policy-as-code v0, ledger schema | IPS for pilot encoded; schemas reviewed by Compliance |
| **1 SAA MVP (paper replica)** | 3–10 | Macro, 18 AC agents, covariance, 20 PC methods, review/vote, CIO, board memo — all on public data | End-to-end run < 2h; every output schema-valid; results within reason vs. paper |
| **2 Governance layer** | 8–14 | Decision ledger + lineage, compliance engine, approvals, kill switch, evidence pack export | Audit can reconstruct any run; 100% hard rules unit-tested |
| **3 Workspaces & Ask Meridian** | 12–18 | Role-based UI, board memo viewer, ledger Q&A | Each persona completes their top 3 tasks in UAT |
| **4 Multi-asset hierarchy** | 16–24 | Portfolio graph, look-through, FI analytics, derivatives exposures, overlay pipeline, TAA | Pilot portfolio modeled at all levels; overlay proposals pass engine |
| **5 Manager selection / FoF** | 22–30 | DD agents, style analysis, manager review & vote, FoF allocator, pacing | Back-test on historical manager decisions; IC review |
| **6 Implementation** | 28–34 | Drift monitor, trade lists, pre-trade compliance, OMS export, TCA loop | Paper-trade proposals for one full rebalance cycle |
| **7 Learning & research agents** | 32–40 | Meta-learner and PC-researcher producing change requests | Change control exercised end-to-end |
| **8 Production readiness** | 36–48+ | Independent model validation, security review/pen test, parallel run ≥ 2 quarters, policies & procedures adopted, ADV/disclosure updates | CCO + IC sign-off; go-live at L3 |

*Indicative for a small team (you + Claude + 1–3 engineers/quants). Phases overlap.

## Phase 0 — detailed checklist
1. **Decisions (you):** firm/regulatory profile, pilot portfolio, data vendors, cloud, repo hosting (see "Open questions" below).
2. **Repo scaffold (Claude):** monorepo layout below, CI, linting, test harness.
3. **Schemas (Claude, reviewed by you + Compliance):** policy YAML schema, agent output schemas (macro-view, cma, covariance, pc-proposal, review, vote, cro-report, cio-decision, board-memo), decision-record schema.
4. **Pilot IPS as code (Claude drafts from your IPS or from the paper's example IPS):** 18 asset classes; CPI+3–4%; vol 8–12%; max DD −25%; TE vs 60/40 ≤ 6%.
5. **Data plan (Claude):** public pilot sources (FRED macro, ETF price history) and point-in-time snapshot design.

### Proposed repository layout
```
meridian/
  policies/            # IPS + guideline YAML, versioned
  agents/              # one folder per agent (AGENT.md, agent.yaml, scripts, tests)
  skills/              # shared skills (cma-judge, macro-regime, historical-analysis, ...)
  schemas/             # JSON schemas for every output + decision record
  analytics/           # deterministic library: cma/, covariance/, optimizers/, risk/, fi/, derivatives/, lookthrough/
  compliance/          # rule engine, rule library, compiler, tests
  orchestration/       # pipeline DAGs, approval workflows
  ledger/              # decision record writer, hash chain, evidence-pack exporter
  data/                # connectors, snapshotter, point-in-time store
  app/                 # API + UI
  infra/               # AWS CDK: hosted app and cost guard
  docs/                # this documentation set
  validation/          # model validation suite, golden runs, backtests
```

## Build order inside Phase 1 (what we'll do together first)
1. Deterministic analytics library: historical stats, 6 equity CMA methods + FI building-block CMA, covariance estimators, 20 PC optimizers. Unit tests against known results.
2. Agent harness: load AGENT.md + skills, call scripts, validate JSON output, write decision record.
3. Macro agent → AC agents (start with 3, scale to 18) → CMA judge.
4. PC agents + CRO report + peer review + Borda vote.
5. CIO ensemble (7 combination methods) + board memo.
6. Golden-run test: freeze a snapshot; any code change must reproduce deterministic outputs.

## What I (Claude) can do vs. what you must do

**I can do directly in this workspace**
- Write all code, schemas, agent/skill definitions, tests, and documentation.
- Run Python, install open-source packages, execute pipelines on public data, generate backtests and reports.
- Deploy through GitHub Actions, manage app users, and read AWS configuration (with your approval for account-level changes).
- Save documentation to this project; publish dashboards/docs as artifacts.

**You need to do (step by step)**
1. **Pick where code lives.** Done: github.com/alexeatondev/meridian.
2. **Bring your CCO/compliance counsel in now.** Share docs 04 and 05 with them. Ask them to confirm which regimes apply (doc 04 §2) and the retention schedule.
3. **Provide a pilot IPS.** Done (generated IPS, doc 07).
4. **Data access.** For the pilot Meridian uses free public data. For production, confirm which vendors you license (Bloomberg, FactSet, MSCI, eVestment, custodian feeds) and ask each vendor whether their license permits use in LLM/AI workflows — many contracts restrict this.
5. **Cloud & keys.** Done: AWS account on the Paid plan with organization advanced features; app deployed via GitHub OIDC (no AWS keys); Anthropic and FRED keys stored as GitHub secrets. Never paste keys into chat.
6. **Name a model-risk owner and an IC sponsor.** They approve change requests and autonomy levels.
7. **Schedule parallel-run reviews** (monthly) once Phase 1 is running.
8. **Sign in and test.** Done for the first two accounts; next, run the role test scripts (UAT) with both logins.

## Open questions (answers change the build)
1. Which entity types will operate this in production (currently selected: SEC RIA, registered fund, ERISA plan, CFTC derivatives)?
2. Second product type after the target-date series?
3. Which data vendors, OMS, and accounting/custody systems are in place?
4. Target autonomy at go-live: L2 (analysis only) or L3 (proposals with approval)?
5. Record retention period for the decision ledger (baseline ≥ 5 years per doc 04 REC-3 until the CCO confirms)?

## Key risks to the plan
| Risk | Mitigation |
|---|---|
| Lookahead bias makes LLM backtests unreliable | Backtest deterministic components only; mark LLM-judgment backtests as indicative; rely on live parallel run |
| Vendor data licensing blocks LLM use | Check early; keep computation in scripts so LLM sees summaries, not raw licensed data, where required |
| Over-trust by users | Mandatory reasoned approvals; periodic "challenge" reviews; display dissent prominently |
| Scope creep across asset classes | Strict phase gates; each asset class added via template + tests |
| Proxy data differs from the real building-block funds | Proxies labeled everywhere; vendor/custodian holdings and characteristics plug into the same datasets |
| Hosted app runs with broad cloud permissions and no WORM records yet | Hardening plan in doc 14 §12, done before parallel-run output is treated as books and records |
| AWS spend exceeds budget | Cost guard: alerts at 80%/forecast, automatic spend block at 100% (doc 14 §7) |
