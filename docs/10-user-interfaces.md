# 10 — User Interfaces

**Version 0.1 · 2026-11-06**

Meridian has three interfaces over the same data and the same decision ledger. Each user gets the one that fits how they work.

| Interface | For | What it is |
|---|---|---|
| **Meridian Console** (role-adaptive web app) | Everyone: PMs, risk, research, manager selection, leadership/IC, compliance, audit | One application whose navigation, home page, actions and permissions change with the signed-in role |
| **Jupyter workbenches** | Power users: research, quants, PMs, compliance analysts | Executable notebooks over the same Python library; anything in the Console can be reproduced and extended here |
| **CLI** | Operators, CI, scheduled runs | `meridian run / ui / approve / verify / entities / data` |

## Console — what each role sees
| Role | Workspace tabs | Home page shows | Can act |
|---|---|---|---|
| Portfolio Manager | Home · Funds & vintages · Positioning · Portfolios & proposals · Risk budget · Metrics · Glide path · Approvals · Agent votes | Proposals awaiting you, largest tilt, expected returns | Approve / reject / request changes; adjust weights; request risk-budget changes |
| Risk Analytics | Home · Risk budget · Metrics · Risk · Positioning · Portfolios · Approvals | Max TE vs limit, worst simulated drawdown, warnings | Co-approve tilts and adjustments; request/approve risk-budget changes |
| Research / Analyst | Home · Positioning · Metrics · CMAs · Agent votes · Glide path | Regime, biggest CMA-judge adjustment, competing methods | Adjust weights (absolute/relative) for approval |
| Manager Selection | Home · Funds & vintages · Underlying funds · Positioning | Funds, derivatives use, liquidity | (DD workflow — roadmap Phase 5) |
| Leadership / IC | Home · Funds & vintages · Board memo · Risk budget · Metrics · Glide path · Approvals | Approvals outstanding, production blockers, compliance status | Approve glide-path changes |
| Compliance | Home · Compliance · Risk budget · Compliance report · Decision ledger | FAILs, warnings, attestations, blockers | Attest; approve exceptions |
| Audit | Home · Decision ledger · Compliance · Report | Ledger integrity, actors, retention | Read-only |

Design rules applied across every view:
- **"Why?" is always one click away.** Every proposal shows its rationale, ensemble, invalidation conditions, dissent and links to its decision records.
- **Approvals cannot be rubber-stamped.** The approver must tick that they read the rationale, dissent and compliance results, and must give a reason. FAILs block approval in the UI and again in code.
- **Synthetic-data and compliance status banners** appear on every page.
- The ledger opens only in the Compliance and Audit workspaces; other roles see record IDs.

**Prototype vs production.** Today the Console is generated per run as one self-contained page (`meridian ui`), with a role picker to preview each workspace. Approvals made there produce a `meridian approve` command that writes the decision to the ledger. In production the same front end is served by the API: the role comes from SSO and approvals write directly to the ledger.

See doc 11 for positioning, risk budgets, metrics and adjustments.

## Notebooks (`notebooks/`)
| Notebook | Audience | Contents |
|---|---|---|
| `01_portfolio_manager_workbench.ipynb` | PMs | Run pipeline, series summary, glide path chart, vintage drill-down, entity what-if, approval |
| `02_research_cma_lab.ipynb` | Research | Every CMA method, judge vs blend, PC-method sensitivity to CMA shocks |
| `03_compliance_audit_workbench.ipynb` | Compliance, audit | Obligations by entity type, rule matrix, ledger tamper detection, evidence extract |

Launch: `pip install -e ".[dev]" jupyterlab && jupyter lab notebooks/`. Notebooks are committed with outputs so they read on GitHub without running.
