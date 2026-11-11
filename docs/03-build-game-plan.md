# 03 — Build Game Plan & Roadmap

**Version 0.6 · 2026-11-10**

## Status (2026-11-10)
- **Repo:** github.com/alexeatondev/meridian · **App:** https://d3maw6l4k5cc0v.cloudfront.net (AWS us-east-2, CDK, GitHub OIDC, no stored keys) · **Cost:** about $1 spent so far (product owner's Cost Explorer check, 2026-11-10); budget $75/month with alerts and an automatic spend block.
- **Agent pipeline (Phase 1):** macro regime, 13 asset classes with CMA judge, covariance, 7 construction methods, peer review and Borda vote, CRO, CIO ensemble, board memo; real public data with synthetic only for some non-US valuations (flagged); live LLM judgment in the `agent-run` workflow; runs are ad hoc.
- **Governance (Phase 2):** deterministic compliance engine, Agentic Compliance Officer (draft only), hash-chained ledger that the database refuses to edit, approvals with reason and segregation of duties, Investment Committee / CCO / Trade route manager permissions, exceptions workflow, ledger search across runs, evidence pack. Not yet: kill switch, autonomy controls, WORM copy.
- **Workspaces (Phase 3):** eight role workspaces, **Why?** panels, changes since last run, risk analytics (fund, factor, stress, history, look-through), User access screen. UAT round 1 run by hand; 115 automated tests (57 in the browser). Not yet: Ask Meridian.
- **Implementation (Phase 6, brought forward):** Trading screen in shadow mode with mutual fund and CIT product lines, cashflow intake (Excel/CSV/API), three allocation tables, pro-rata trade lists, tilts, exclusions, full exits, single-security tickets, tranches, ETF cash buffer, routing by security type, post-trade preview with IPS check, approval, mock Charles River file (doc 17). Positions, prices and the CIT line are example data.
- **Docs:** all 17 docs refreshed on 2026-11-10; repository docs now use the Project's numbers; user guide (doc 06) rewritten step by step with 39 screenshots and published as an illustrated page.

## Assessment (2026-11-10)
| Area | State | Comment |
|---|---|---|
| Phase 0 Foundations | Done | |
| Phase 1 SAA MVP | Mostly done | 7 of 20 construction methods and 13 of the paper's 18 asset classes; enough for the pilot |
| Phase 2 Governance | Mostly done | Kill switch, autonomy controls and WORM records missing; WORM deferred for cost |
| Phase 3 Workspaces | Mostly done | UAT run by Claude on the product owner's login; real people in each role have not tested; Ask Meridian not built |
| Phase 4 Multi-asset hierarchy | Partial | Look-through via public proxies; security-level positions exist only as example data |
| Phase 5 Manager selection | Not started | |
| Phase 6 Implementation | About half, shadow only | Built ahead of Phases 4–5 at the product owner's request |
| Phase 7 Learning agents | Not started | |
| Phase 8 Production readiness | Not started | Needs named people (CCO, IC sponsor, model-risk owner), counsel review, security hardening, WORM, parallel run ≥ 2 quarters |

**Main risks right now**
1. **Trading runs on example data.** Until real positions and cashflows arrive from SS&C and State Street, every trade list is a demonstration; exported trades also don't change holdings (no booking or fills yet).
2. **The trading targets aren't linked to the approved agent proposal.** Neutral follows the glide path and Strategic is a separate table; an approved tactical proposal doesn't yet feed trading. This is the main seam between the agent pipeline and implementation.
3. **One person holds every role.** Segregation of duties is enforced in code but has only been exercised with test logins.
4. **Security hardening is held** (admin deploy role, no MFA). Acceptable with test users only.
5. **No human CCO or counsel review.** Blocks production, not development.

## Built 2026-11-10 (evening)
- **Fund-level regulations (doc 18):** tag funds with US and ex-US regulations (ACT 40, ERISA, CIT/OCC 9.18, CFTC 4.5, UCITS, AIFMD, UK COLL, NI 81-102, SFC); controls checked on current holdings and on every trade list (FAIL blocks); obligations tracked with owner, due date and evidence; overdue obligations open an exception; removal and waivers need the CCO permission.
- **Next steps 1, 2, 4, 5 done:** Approved-proposal trading table and **rebalance** trade lists; **positions upload** and **fills with booking** (positions and cash update); F-4 (US Treasury issuer consolidated) and F-11 (pending adjustment on the risk budget) fixed; **market-holiday calendar** for tranche dates (2026–2028).
- 125 automated tests (63 in the browser); user guide updated with 50 screenshots.

## Next steps (not blocked, in order)
1. **Custom calculations (doc 17 item 13):** named, versioned sell-down and liquidity-capped templates that produce tranches.
2. **Leadership controls:** kill switch (pause per pipeline or globally) and autonomy level in the app, with ledger records; a KPI view (approvals vs overrides, exceptions, obligations on time).
3. **Fiscal year ends per fund** for annual and semiannual obligations (doc 18 §5).
4. **You:** run RISK-6 with the RCTest login; try the Trading (TRD) and Regulations (REG) scripts in doc 16; tag the real funds with their regulations once the CCO confirms them.

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
