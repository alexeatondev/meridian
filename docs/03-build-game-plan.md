# 03 — Build Game Plan & Roadmap

**Version 0.2 · 2026-11-06**

## Status (2026-11-06)
- Repo live: github.com/alexeatondev/meridian
- Done: entity-regime selection, policy-as-code + IPS for the target-date pilot, plug-and-play data layer (direct + Snowflake), CMA judge, 7 PC agents, peer review and Borda vote, CRO, CIO ensemble, board memo, deterministic compliance engine, Agentic Compliance Officer, hash-chained ledger, tests, CI.
- Real public data end to end (Yahoo, FRED via API, US Treasury, cited manual inputs); synthetic only for non-US valuations (flagged). Live LLM judgment via the `agent-run` workflow. Key rotation reminder scheduled for 2026-12-02.
- Console and notebooks: role-adaptive Meridian Console; positioning with drill-down, risk budgets and governed changes, portfolio metrics, PM/analyst weight adjustments; Jupyter workbenches (PM, research, compliance/audit, risk analytics).
- Risk analytics (docs/12): fund-level risk (total/benchmark/active, relative duration, credit spread duration, VaR 95, active VaR 95, diversification), risk breakdown by asset class and fund, weight-vs-risk, 10-factor model with 18-month history, historical and hypothetical stress tests (normal → crisis) with a scenario builder, risk time series, iShares holdings look-through and ticker search.
- Hosted multi-user app (FastAPI + Postgres + Cognito + CloudFront on AWS via CDK) built and tested; first deploy waiting on AWS to finish lifting Free-plan restrictions after the upgrade to the Paid plan.
- Next: first AWS deploy and sign-in; operating loop automation/notifications; vendor data (holdings, characteristics, factor model); second product type; human CCO.

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
- Save documentation to this project; publish dashboards/docs as artifacts.

**You need to do (step by step)**
1. **Pick where code lives.** Easiest: create a private GitHub repo named `meridian` (github.com → New repository → Private → no template). Then in this chat say "attach repo <your-user>/meridian" and I'll connect and push to it. Without a repo, code lives only in this session's workspace and I'll send you files to download.
2. **Bring your CCO/compliance counsel in now.** Share docs 04 and 05 with them. Ask them to confirm which regimes apply (doc 04 §2) and the retention schedule.
3. **Provide a pilot IPS.** Upload your actual IPS (PDF/Word) to this project, or tell me to use the paper's example IPS.
4. **Data access.** For the pilot I'll use free public data. For production, confirm which vendors you license (Bloomberg, FactSet, MSCI, eVestment, custodian feeds) and ask each vendor whether their license permits use in LLM/AI workflows — many contracts restrict this.
5. **Cloud & keys (Phase 2+).** Provision a cloud account/tenant and an Anthropic API key (console.anthropic.com) for the agent runtime. Never paste keys into chat; I'll give you instructions for storing them as secrets.
6. **Name a model-risk owner and an IC sponsor.** They approve change requests and autonomy levels.
7. **Schedule parallel-run reviews** (monthly) once Phase 1 is running.

## Open questions (answers change the build)
1. What type of entity will operate this — SEC-registered adviser, broker-dealer, registered fund (1940 Act), private funds, pension/endowment/OCIO? Several apply?
2. What is the pilot portfolio (structure and approximate asset mix)? Is there an existing FoF?
3. Which data vendors, OMS, and accounting/custody systems are in place?
4. GitHub (or other) for code? Which cloud?
5. Target autonomy at go-live: L2 (analysis only) or L3 (proposals with approval)?

## Key risks to the plan
| Risk | Mitigation |
|---|---|
| Lookahead bias makes LLM backtests unreliable | Backtest deterministic components only; mark LLM-judgment backtests as indicative; rely on live parallel run |
| Vendor data licensing blocks LLM use | Check early; keep computation in scripts so LLM sees summaries, not raw licensed data, where required |
| Over-trust by users | Mandatory reasoned approvals; periodic "challenge" reviews; display dissent prominently |
| Scope creep across asset classes | Strict phase gates; each asset class added via template + tests |
