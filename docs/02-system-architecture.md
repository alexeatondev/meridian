# 02 — System Architecture

**Version 0.4 · 2026-11-11**

## 1. What we take from the paper, and what we change

| Paper design | Keep / Change | Why |
|---|---|---|
| ~50 specialized agents, workflow manager | **Keep** | Proven decomposition |
| Agent = description (md) + Python scripts + shared skills + output contract (JSON + md) | **Keep exactly** | Maps cleanly to the Claude Agent SDK / skills model; versionable in git |
| LLM for judgment, scripts for computation | **Keep, and add a third tier:** deterministic compliance engine | Compliance determinations must be deterministic and testable |
| IPS governs the pipeline | **Extend** to a policy *hierarchy* (IPS → mandate → sleeve guidelines → fund docs) compiled to code | Multi-level portfolios |
| Macro → AC agents (6 CMA methods + LLM judge) → covariance → 20 PC agents → review & Borda vote → CIO ensemble → board memo | **Keep** as the SAA pipeline | Core of paper |
| PC-researcher proposes new methods | **Keep, sandboxed**; promotion via change control | Model risk |
| Adversarial diversifier | **Keep** | Ensemble diversity |
| Meta-agent auto-modifies code and prompts | **Change:** meta-agent opens change requests; humans approve; validation suite gates deploy | Advisers Act/FINRA supervision; model risk management |
| Single base LLM | **Change:** model-agnostic runtime; optional multi-model PC agents and deterministic baselines | Monoculture risk (paper §5.1) |
| SAA only, 18 ETFs | **Extend** to TAA, sleeve construction, security selection, FoF/manager selection, derivatives overlay, rebalancing | Your scope |

## 2. Layered architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 7. EXPERIENCE   Role workspaces · Ask Meridian (RBAC chat) · Board memos │
├──────────────────────────────────────────────────────────────────────────┤
│ 6. GOVERNANCE   Approvals · Autonomy levels · Kill switch · Change ctrl  │
├──────────────────────────────────────────────────────────────────────────┤
│ 5. COMPLIANCE   Policy-as-code compiler · Rule engine (pre/post-trade)   │
│                 Exceptions · Surveillance · Attestations                 │
├──────────────────────────────────────────────────────────────────────────┤
│ 4. AGENT        Pipelines (SAA, TAA, Sleeve, FoF, Overlay, Rebalance)    │
│    LAYER        Agents · Skills · Deliberation protocols · CIO ensemble  │
├──────────────────────────────────────────────────────────────────────────┤
│ 3. ANALYTICS    Deterministic libraries: CMA methods, covariance, 20+    │
│    (scripts)    optimizers, risk (VaR/CVaR/stress), FI & derivatives     │
│                 analytics, look-through, attribution, backtests          │
├──────────────────────────────────────────────────────────────────────────┤
│ 2. DATA         Point-in-time store · Snapshots · Portfolio graph ·      │
│                 Reference data · Vendor connectors (MCP)                 │
├──────────────────────────────────────────────────────────────────────────┤
│ 1. LEDGER       Immutable decision records · Lineage graph · WORM store  │
│    (cross-cut)  Observability (traces of every agent step)               │
└──────────────────────────────────────────────────────────────────────────┘
```

## 3. Portfolio model (multi-asset, multi-level)

A **Portfolio Graph** of typed nodes:

| Node type | Examples | Carries |
|---|---|---|
| `TotalFund` | Pension plan, endowment, OCIO client | IPS (policy root), benchmark, liquidity needs |
| `Mandate` / `Strategy` | Growth, Defensive, Real Assets | Allocation ranges, risk budget |
| `Sleeve` | US Equity sleeve, Core FI sleeve, Overlay sleeve | Guidelines, benchmark, manager(s) |
| `FundHolding` | External fund, ETF, LP interest, SMA | Fund docs constraints, liquidity terms, fees, holdings (reported or estimated) |
| `Position` | Security, future, option, swap, FX forward, cash | Instrument terms, exposures |

Each edge has a weight and a **constraint inheritance** rule: child constraints must satisfy parent constraints; the compiler checks consistency (e.g., sleeve allows 10% EM but parent IPS caps total EM at 8% → aggregated check).

**Structures supported**
- *Fund of Funds:* `TotalFund → FundHolding*` with look-through to `Position` where holdings are available; returns-based style analysis where not.
- *Fund of Sleeves:* `TotalFund → Sleeve* → Position*` (SMA-style; full transparency).
- *Fund of Equities:* `TotalFund/Sleeve → Position*` (direct securities).
- *Hybrids:* any mix; overlay sleeves hold derivatives referencing exposures elsewhere in the graph.

**Exposure engine** normalizes every holding into a common factor/exposure vector: asset class, region, sector, currency, duration & key-rate durations, spread duration, credit quality, equity beta/delta-adjusted notional, liquidity bucket, ESG tags. Derivatives contribute delta-adjusted or notional exposure per policy; cash collateral and margin tracked separately.

## 4. Agent anatomy (from paper §3.2)

```
agents/<agent-slug>/
  AGENT.md            # role, position in pipeline, step-by-step workflow, asset-specific guidance
  agent.yaml          # inputs, required skills, tools allowed, model, autonomy, output schema refs
  scripts/            # deterministic Python called by the agent
  tests/              # golden-input tests + schema tests
skills/<skill-slug>/
  SKILL.md            # methodology the agent follows (e.g., cma-judge)
  scripts/
schemas/<output>.json # output contracts
```

Every agent run emits: JSON outputs (validated against schema), markdown narrative, and a **Decision Record** (doc 05).

**Tool permissions** are declared per agent (read-only data, compute sandbox, web search on/off, no write access outside its run directory). The orchestrator — not the agent — persists outputs.

## 4a. How agents run today (pilot, 2026-11-11)

The roster in §5 is the target design. In the pilot, four roles are model-driven and the rest are code.

| Step | Today | Calls per run |
|---|---|---|
| `macro-regime` | **Model** reviews the rule-based regime and may confirm or change it | 1 |
| `asset-class-analyst` (CMA judge) | **Model** weights the forecast methods; code bounds the result to the methods' range | 13 |
| `cio` | **Model** picks the ensemble per vintage; code rejects a pick with any FAIL | 9 |
| `compliance-officer` | **Model** drafts the narrative; findings and status are code | 1 |
| `pc-*` proposals (7 methods incl. the adversarial one) | Code (optimizers) | 0 |
| `cro` risk report, review and vote | Code (rule-based lenses and Borda count) | 0 |
| `board-memo-writer` | Code template | 0 |

The ledger records code-only steps as `system` actors with `implemented_by: deterministic code` and no model name; `design_agent` names the agent role they are meant to become. A judgment that falls back to the deterministic policy is recorded as `offline-deterministic` even when a model backend is on.

**Two backends** (`MERIDIAN_AGENT_BACKEND`, an input on the `agent-run` workflow):

| Backend | What a judgment is | Tools | Notes |
|---|---|---|---|
| `messages` | One Anthropic Messages API call, single shot | None | Original pilot path; still the default for local runs |
| `sdk` | One **Claude Agent SDK** session: AGENT.md + skills as the system prompt, schema-validated output | Read-only Meridian tools (below) | Default for `agent-run`. Capped by run budget, per-session budget and turn limit |

**Agent tools (read-only, results computed by code, `src/meridian/agents/tools.py`):**

| Agent | Tools |
|---|---|
| macro-regime | `indicator_detail`, `rescore_regime` (what-if on the rule-based classifier) |
| asset-class-analyst | `blend_preview`, `asset_facts`, `cross_section` |
| cio | `ensemble_detail`, `candidate_detail`, `dissent` |
| compliance-officer | `rule_results`, `judgment_paths`, `ledger_search` |

**Limits on the SDK backend (`src/meridian/agents/sdk_backend.py`):** no built-in tools (no shell, files or web), no project or user settings loaded, an empty working directory, `MERIDIAN_RUN_BUDGET_USD` (default 3.00) for the whole run, `MERIDIAN_AGENT_BUDGET_USD` (0.25) and `MERIDIAN_AGENT_MAX_TURNS` (8) per session. When the run budget is used up, or three sessions fail in a row, the remaining judgments use the deterministic policy and the ledger says so. Each agent record carries an `agent_trace` (turns, tool calls with inputs, cost, session ID), and the run's `llm.usage` record carries total cost against the budget.

**Choosing the model (`config/models.yaml`):** `default` is the standing model (currently `claude-haiku-5-5`, the cheapest). The `agent-run` workflow's `model` dropdown overrides it for one run. An entry under `agents` (for example `cio: claude-sonnet-5-5`) pins one agent to a model whatever the run's choice. Precedence, highest first: `MERIDIAN_MODEL_<SLUG>` env, `agents.<slug>` in the file, `MERIDIAN_MODEL` env (the dropdown), `default` in the file. The model each judgment used is on its ledger record.

## 5. Agent roster (v1.0)

**Shared / control agents**
- `orchestrator` (deterministic workflow, not an LLM) · `policy-interpreter` (explains constraints in plain language; never decides compliance) · `cro` (neutral risk assessor, no vote) · `cio` (LLM-as-judge ensemble) · `board-memo-writer` · `compliance-explainer` · `meta-learner` (P2) · `pc-researcher` (P2) · `ledger-qa` (answers questions over the ledger)

**SAA pipeline (paper)**
- `macro-regime` (P2: Chief Economist + Fed, fiscal, geopolitics, FX, commodities sub-agents)
- `ac-<asset-class>` × N — equity template (6 CMA methods + judge), fixed-income template (yield/roll/spread/default-loss building blocks), real-asset and alts templates
- `covariance` (sample, shrinkage, factor, regime-conditional; desmoothing for private assets)
- `pc-<method>` × 20 (+ researcher method, + adversarial diversifier)
- review protocol (peer review, vote), `cio`, `board-memo-writer`

**Extended pipelines**
| Pipeline | Agents | Output |
|---|---|---|
| TAA / DAA | regime, signal agents (value, momentum, carry), tilt-sizer | Tilts within SAA ranges |
| Sleeve construction — equity | factor model, security-research agents (one per name or sector), optimizer, risk | Target holdings |
| Sleeve construction — fixed income | curve, credit, issuer-research, optimizer (duration/KRD/spread targets) | Target holdings |
| Derivatives overlay | exposure-gap, hedge-designer (futures/options/swaps/FX), margin & counterparty, 18f-4/VaR checker (registered funds) | Overlay trades |
| Manager selection / FoF | sourcing, DD (questionnaire & document reading), quant (returns-based style, alpha/beta, drawdown), ops DD, fee & terms, peer review & vote, allocator | Manager recommendations, FoF weights |
| Private markets pacing | commitment pacing, cash-flow (Takahashi-Alexander style), liquidity | Commitment plan |
| Rebalance & implementation | drift monitor, trade-list builder, tax/cost estimator, pre-trade compliance (engine), OMS exporter | Approved trade lists |
| Monitoring | limit monitor, regime-change watcher, manager-event watcher, CMA invalidation watcher | Alerts, off-cycle triggers |

## 6. Deliberation protocols (reusable)
- **Peer review:** each agent reviews one intra-family and one inter-family peer; randomized with recorded seed; reviews released simultaneously.
- **Modified Borda vote:** top-5 (5..1 pts) + one bottom flag (−2), self excluded; blended with quantitative composite using regime-dependent weights; family-diversity constraint on shortlist.
- **Revision round:** shortlisted agents revise with full visibility of reviews + CRO report.
- **Dissent capture:** bottom-flagged and minority views carried into the CIO input and board memo.
- Used for PC selection, manager selection, and (P2) macro sub-agent aggregation.

## 7. Compliance engine
- **Policy-as-code:** IPS and guidelines authored in structured YAML (with the human-readable IPS attached). Compiler validates and versions. Example rule types: allocation ranges, issuer/sector/country caps, credit-quality floors, duration bands, tracking-error budget, drawdown limit, liquidity buckets, leverage/derivatives limits, prohibited lists, 1940 Act diversification, 12(d)(1) fund-of-funds limits, ERISA restrictions, ESG screens.
- **Evaluation points:** (a) candidate portfolio (CRO step), (b) CIO output, (c) pre-trade on trade lists, (d) daily post-trade on actual holdings from custodian/accounting.
- **Results** are deterministic `PASS / WARN / FAIL` with rule ID, measured value, limit, and data lineage. LLMs may write the explanation; they cannot change the result.
- **Exceptions** require a reason code, approver, and expiry.

## 8. Orchestration & governance
- Durable workflow engine runs pipelines as DAGs; each step idempotent and resumable; human-approval steps are workflow "signals".
- **Approval matrix** (policy-driven): e.g., SAA change → IC; sleeve rebalance > X% → PM + Risk; < X% → PM; exceptions → CCO.
- **Kill switch:** global and per pipeline; blocks new runs and freezes the approval queue.
- **Change control:** all agent descriptions, skills, scripts, schemas and policies live in git. Merges to `main` require code-owner approval (Research/Risk/Compliance as relevant) + passing validation suite. Production runs pin a release tag.

## 9. Recommended technology stack (adjustable)
| Concern | Recommendation | Notes |
|---|---|---|
| Language | Python 3.12 | Quant ecosystem |
| Agent runtime | Claude Agent SDK (model-agnostic adapter layer so other models can be added) | Agent/skill structure matches paper |
| Orchestration | Temporal (or Prefect) | Durable workflows, human-in-loop signals |
| Optimization & risk | cvxpy, Riskfolio-Lib, PyPortfolioOpt, scikit-learn, arch, QuantLib (FI/derivatives) | All open source |
| Data | Postgres (+TimescaleDB) for operational; Parquet/Iceberg lake for point-in-time history | Bitemporal tables |
| Ledger & WORM | Postgres append-only + hash chain; S3 Object Lock (compliance mode) or equivalent for evidence packs | See doc 05 |
| Data connectors | MCP servers per vendor (Bloomberg, FactSet, MSCI, eVestment, custodians); FRED/public data for pilot | License review needed |
| API / UI | FastAPI + Next.js | Role workspaces |
| Observability | OpenTelemetry traces linked to decision IDs | |
| Secrets & access | Cloud KMS/Vault, SSO (Okta/Entra), RBAC/ABAC | |
| Hosting | Your cloud tenant (AWS/Azure/GCP), private networking | Data residency |

## 9a. As deployed (pilot, updated 2026-11-10)
The pilot runs a deliberately smaller stack than the recommendation above. Details, runbooks and planned hardening are in doc 14.

| Concern | Pilot implementation |
|---|---|
| Hosting | AWS account 950088505912, us-east-2, defined in AWS CDK (`infra/app.py`), stacks `Meridian` and `MeridianCostGuard` |
| Edge | CloudFront (HTTPS) → Application Load Balancer that only accepts CloudFront's secret origin header |
| App | FastAPI + server-rendered Meridian Console on ECS Fargate (1 task) |
| Data | RDS PostgreSQL (encrypted, isolated subnets): runs, decision ledger (append-only triggers), governance ledger (exceptions, trading, regulations), access log (append-only), exceptions, positions, change requests, policy overrides, cashflows, trade lists, trading settings (incl. positions, glide-path adjustments), fund regulations, compliance obligations |
| Identity | Amazon Cognito (admin-created users; groups = eight workspaces plus three permissions: `investment_committee`, `chief_compliance_officer`, `route_manager`; optional TOTP MFA). Managed in the app's **User access** screen; any access change signs the person out at once |
| Secrets | AWS Secrets Manager (app); GitHub secrets (Anthropic and FRED keys) |
| Orchestration | GitHub Actions: `ci`, `deploy`, `manage-users`, `agent-run` (live model judgment; Claude Agent SDK backend by default, see §4a), `data-refresh` (monthly). Temporal is not used yet |
| CI/CD auth | GitHub OIDC → IAM role `meridian-github-deploy`; no long-lived keys |
| Cost control | AWS Budgets: $75/month, email alerts, automatic deny policy on deploy roles at 100% |
| Ledger & WORM | Hash-chained records in Postgres; WORM evidence store not yet built (doc 14 §12) |
| Observability | CloudWatch Logs (30 days); no alarms yet |

```
GitHub (code, CI, agent-run) ──OIDC──▶ AWS (us-east-2)
                                        CloudFront ─▶ ALB ─▶ ECS Fargate (Meridian app) ─▶ RDS PostgreSQL
                                                                   │
                                                          Cognito · Secrets Manager · CloudWatch
agent-run: pulls approved positions from the app ─▶ runs the pipeline; judging agents call Claude (§4a) ─▶ publishes run bundle to the app
```

## 10. Security model (agent-specific)
- Agents run in sandboxes with no network except allow-listed data endpoints.
- Web content is treated as untrusted data: retrieved text is tagged, never executed as instructions; web-derived claims are labeled in outputs.
- Agents cannot modify policy, other agents, or ledger records. Only the orchestrator writes.
- Meta-learner and PC-researcher run in a separate research environment; output is a pull request, never a deploy.
- Client PII is never sent to agent context (portfolio IDs only).

## 11. Trading and implementation (built 2026-11-10/11, shadow mode)
```
Cashflows (Excel/CSV upload · hand entry · API from TA/custodian)
        │
        ▼
Allocation engine (meridian.trading, deterministic)
  table: previous close | neutral (glide path on the fund's roll-down) | strategic (custom or follows glide path)
  → exits removed → tilts applied → no-target / excluded skipped → pro rata split → ETF cash buffer → lot rounding
        │
        ▼
Trade list (draft) ── preview (current vs post-trade) ── IPS engine + regulation controls on post-trade weights ── tranches
        │ PM approval (checkbox + reason; FAIL blocks)
        ▼
Charles River import file (mock CSV; one row per order or tranche; destination per security type)
   mutual fund → SS&C (formerly DST) · CIT → State Street · ETF, stock, bond → internal trading desk
        │
        ▼
Fills (file or "mark all filled") ── booked to positions and cash ── positions also loadable from files
```
- **Other trade-list sources:** rebalance to a target table (approved proposal, neutral or strategic), single-security tickets, full exits.
- **Glide path and bulk changes:** settings carry a scope (all funds, all mutual funds, all CITs, one fund, optional vintage range). Glide-path adjustments are asset-class shifts within the IPS bands, applied to the Neutral table only after Investment Committee approval.
- **Regulations (doc 18):** `regimes/fund_regulations.yaml` (US and international); `src/meridian/regulations.py` (controls, schedules); `src/meridian/app/regulations.py` + `regulations.html` (tags, obligation tasks, escalation to exceptions).
- **Model:** `config/trading.yaml` (product lines, funds, roll-down schedules, security master, routes, buffer); `src/meridian/trading/` (model, allocation, tilts, tickets, tranches, Charles River rows); `src/meridian/app/trading.py` + `trading.html` (API and screen).
- **Records:** every load, setting, route change, table change, trade list, approval, tranche plan, cancel and export is a governance ledger record (`dr_type` "trading").
- **Not yet:** automatic custodian/TA feeds, Charles River API and returns, derivatives, in-kind, mandates, margin, capital calls (doc 17); the agent pipeline does not read glide-path adjustments.
