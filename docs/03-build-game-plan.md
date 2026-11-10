# 03 — Build Game Plan & Roadmap

**Version 0.4 · 2026-11-09**

## Status (2026-11-09)
- Repo live: github.com/alexeatondev/meridian
- Done: entity-regime selection, policy-as-code + IPS for the target-date pilot, plug-and-play data layer (direct + Snowflake), CMA judge, 7 PC agents, peer review and Borda vote, CRO, CIO ensemble, board memo, deterministic compliance engine, Agentic Compliance Officer, hash-chained ledger, tests, CI (offline on the committed data cache).
- Real public data end to end (Yahoo, FRED via API, US Treasury, cited manual inputs, iShares holdings); synthetic only for non-US valuations (flagged). Live LLM judgment via the `agent-run` workflow. Key rotation reminder scheduled for 2026-12-02.
- Console and notebooks: role-adaptive Meridian Console; positioning with drill-down, risk budgets and governed changes, portfolio metrics, PM/analyst weight adjustments; Jupyter workbenches (PM, research, compliance/audit, risk analytics).
- Risk analytics (doc 12): fund-level risk, risk breakdown, weight-vs-risk, 10-factor model with 18-month history, historical and hypothetical stress tests with a scenario builder, risk time series, iShares look-through and ticker search.
- **Hosted app live (2026-11-09):** https://d3maw6l4k5cc0v.cloudfront.net on AWS (us-east-2, CDK). GitHub → AWS sign-in via OIDC works (no stored keys); first deploy succeeded; first live-LLM run (`run_tds_20261031_48d07c`) published to the app; two users (full-access product owner, risk/compliance test user) signed in. Cost guard: $75/month budget with email alerts and an automatic spend block at 100%. Runbooks in doc 13 (Hosting & Operations).
- Account history: Free → Paid plan (2026-11-06); organization advanced features activated (2026-11-09) to lift the free-plan SCP; AWS support case updated as resolved.

## Next steps (agreed order, 2026-11-09)
1. ~~Documentation catch-up (hosting & operations doc, architecture as deployed, sign-in guide, status).~~ Done 2026-11-09.
2. *Deferred by the product owner (2026-11-09) until later in the build:* security before more users: split the GitHub deploy role per workflow and require a GitHub environment; require MFA for approvers and admins; record approvals against the Cognito user ID/email.
3. Records integrity: WORM evidence store (S3 Object Lock), daily ledger anchor, insert-only ledger grants, longer backups. Needs the retention period (baseline ≥ 5 years per doc 04 REC-3 until the CCO confirms).
4. UAT of the role screens with both test users (Phase 3 exit criterion); fix what testing finds.
5. Operating loop: schedule `agent-run` after the monthly data refresh, with notifications.
6. Smaller items: CloudWatch alarms; Node 20 action updates; remaining least-privilege steps (CDK execution role, Access Analyzer review).
- Later: vendor data (holdings, characteristics, factor model); second product type; human CCO; suggested risk add-ons await direction.

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
3. **Provide a pilot IPS.** Done (generated IPS, `policies/ips/`).
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
| Hosted app runs with broad cloud permissions and no WORM records yet | Hardening plan in doc 13 §12, done before parallel-run output is treated as books and records |
| AWS spend exceeds budget | Cost guard: alerts at 80%/forecast, automatic spend block at 100% (doc 13 §7) |
