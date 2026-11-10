# 10 — User Interfaces

**Version 0.2 · 2026-11-09**

Meridian has three interfaces over the same data and the same decision ledger. Each user gets the one that fits how they work.

| Interface | For | What it is |
|---|---|---|
| **Meridian Console** (role-adaptive web app) | Everyone: PMs, risk, research, manager selection, leadership/IC, compliance, audit | One application whose navigation, home page, actions and permissions change with the signed-in role. Live at https://d3maw6l4k5cc0v.cloudfront.net |
| **Jupyter workbenches** | Power users: research, quants, PMs, compliance analysts | Executable notebooks over the same Python library; anything in the Console can be reproduced and extended here |
| **CLI** | Operators, CI, scheduled runs | `meridian run / ui / approve / verify / entities / data` |

## Console — what each role sees
| Role (sign-in group) | Workspace tabs | Home page shows | Can act |
|---|---|---|---|
| Portfolio Manager (`portfolio_manager`) | Home · Funds & vintages · Positioning · Portfolios & proposals · Fund risk · Risk budget · Metrics · Look-through & search · Glide path · Approvals · Agent votes | Proposals awaiting you, largest tilt, expected returns | Approve / reject / request changes; adjust weights; request risk-budget changes |
| Risk Analytics (`risk`) | Home · Fund risk · Factor risk · Stress tests · Risk history · Look-through & search · Risk budget · Metrics · Candidate risk · Positioning · Portfolios & proposals · Approvals | Max TE vs limit, worst simulated drawdown, warnings | Co-approve tilts and adjustments; request/approve risk-budget changes |
| Research / Analyst (`analyst`) | Home · Positioning · Metrics · Factor risk · Look-through & search · Capital market assumptions · Agent votes · Glide path | Regime, biggest CMA-judge adjustment, competing methods | Adjust weights (absolute/relative) for approval |
| Manager Selection (`manager_selection`) | Home · Funds & vintages · Underlying funds · Look-through & search · Positioning | Funds, derivatives use, liquidity | (DD workflow — roadmap Phase 5) |
| Leadership / IC (`leadership`) | Home · Funds & vintages · Board memo · Fund risk · Stress tests · Risk budget · Metrics · Glide path · Approvals | Approvals outstanding, production blockers, compliance status | Approve glide-path changes |
| Compliance (`compliance`) | Home · Compliance · Risk budget · Look-through & search · Compliance report · Decision ledger | FAILs, warnings, attestations, blockers | Attest; approve exceptions |
| Audit (`audit`) | Home · Decision ledger · Compliance · Compliance report | Ledger integrity, actors, retention | Read-only |
| Admin (`admin`) | Same read-only view as Audit | — | User management and deploys happen in GitHub Actions (doc 13), not in the Console |

A person with several roles picks the workspace from the role selector in the side bar; only their own roles are listed.

Design rules applied across every view:
- **"Why?" is always one click away.** Every proposal shows its rationale, ensemble, invalidation conditions, dissent and links to its decision records.
- **Approvals cannot be rubber-stamped.** The approver must tick that they read the rationale, dissent and compliance results, and must give a reason. FAILs block approval in the UI and again in code.
- **Segregation of duties.** One person can't decide the same vintage in two roles, and a requester can't approve their own risk-budget change.
- **Synthetic-data and compliance status banners** appear on every page.
- The ledger opens only in the Compliance and Audit workspaces; other roles see record IDs.

## Hosted app vs local console
**Hosted (built, 2026-11-09).** The FastAPI app serves the Console at https://d3maw6l4k5cc0v.cloudfront.net. People sign in with Amazon Cognito (doc 06, "Signing in"); their Cognito groups decide which workspaces they see. Approvals, weight adjustments and risk-budget requests write directly to the ledger in the app's database, and the run picker lists every run published by the `agent-run` workflow. Sessions last 8 hours. Exports for the next run: `/api/export/positions.csv`, `/api/export/risk-history.csv`, `/api/export/policy-overrides`. Hosting and operations: doc 13.

**Local (for development and offline review).** `meridian ui` generates one self-contained page per run, with a role picker to preview every workspace. Approvals made there produce a `meridian approve` command that writes the decision to the local ledger.

See doc 11 for positioning, risk budgets, metrics and adjustments, and doc 12 for the risk analytics tabs.

## Notebooks (`notebooks/`)
| Notebook | Audience | Contents |
|---|---|---|
| `01_portfolio_manager_workbench.ipynb` | PMs | Run pipeline, series summary, glide path chart, vintage drill-down, entity what-if, approval |
| `02_research_cma_lab.ipynb` | Research | Every CMA method, judge vs blend, PC-method sensitivity to CMA shocks |
| `03_compliance_audit_workbench.ipynb` | Compliance, audit | Obligations by entity type, rule matrix, ledger tamper detection, evidence extract |
| `04_risk_analytics_workbench.ipynb` | Risk, PMs, research | Every risk-analytics figure in the Console, with editable weights, scenarios and factors |

Launch: `pip install -e ".[dev]" jupyterlab && jupyter lab notebooks/`. Notebooks are committed with outputs so they read on GitHub without running.
