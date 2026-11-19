# 11 — User Interfaces

**Version 0.8 · 2026-11-18 (calculation templates; fiscal year ends; adjusted glide path on Proposals)**

Meridian has three interfaces over the same data and the same decision ledger. Each user gets the one that fits how they work.

| Interface | For | What it is |
|---|---|---|
| **Meridian Console** (role-adaptive web app) | Everyone: PMs, risk, research, manager selection, leadership/IC, compliance, audit | One application whose navigation, home page, actions and permissions change with the signed-in role. Live at https://d3maw6l4k5cc0v.cloudfront.net |
| **Jupyter workbenches** | Power users: research, quants, PMs, compliance analysts | Executable notebooks over the same Python library; anything in the Console can be reproduced and extended here |
| **CLI** | Operators, CI, scheduled runs | `meridian run / ui / approve / verify / entities / data` |

## One shell for every screen (UX update, 2026-11-11)
Every screen (console, Trading, Regulations, User access, Help) now shares one application shell, so people learn the controls once. The design follows common enterprise-app practice (consistent global navigation, a single task inbox, in-context help, non-blocking feedback, confirmations that name the action, and WCAG 2.1 AA patterns). Code: `src/meridian/app/shell.py` and `shell.html`; tests `tests/test_shell.py`, `tests/e2e/test_ui_shell.py` (UAT-UX, doc 16). User steps: doc 06 §1.

| Element | Behaviour |
|---|---|
| **App bar** | Fixed at the top: Meridian (home), **Console · Trading · Regulations · User access** filtered by the person's roles with the current screen marked, **My work (n)**, **? Help**, name with workspaces and permissions, **Sign out**. Replaces the per-page "Back to console / Trading / Regulations / Sign out" links and the console side-bar links |
| **My work** (`GET /api/my-work`) | One inbox across modules, most urgent first: draft trade lists to approve (PM with the Approver permission) and exported lists awaiting fills (PM, analyst); pending glide-path requests for Investment Committee holders (not their own); obligations due within 14 days or overdue for the person or their role; exceptions they own (Compliance: all overdue). Each item opens the screen with that item selected. Count refreshes every 60 s and on return to the tab; amber when something is due, red when overdue. Read-only aggregation of existing records; nothing new is stored |
| **Help** (`/help`) | The user guide (doc 06) with its screenshots, rendered in the app with a contents list and heading search. **? Help** opens the section for the current screen. Images are served only to signed-in users |
| **Page header** | Under the app bar: screen title, page-level filters (All funds / Mutual funds / CITs) and a **Read-only** label when the person can only view |
| **Console side bar** | Workspace and run pickers, then tabs grouped under **Overview · Portfolio · Risk · Governance**; **Exceptions** carries the open count |
| **Messages** | Bottom-right stack. Success and info clear themselves (4.5 s; warnings 7 s); **errors stay until dismissed** and are announced as alerts |
| **Confirmations** | In-page dialogs replace browser `prompt()` for cancelling cashflows and trade lists and for deleting accounts. They say what will happen, name the action on a red button, collect the reason, and keep the button disabled until the reason (or, for deletion, the typed email) is valid |
| **Reason fields** | Live counter ("6/10 characters minimum", then "✓ 14 characters"), matching the server's 10-character rule |
| **Busy state** | The button that started a change shows a spinner and is disabled until the server answers, so nothing is submitted twice |
| **Session expiry** | A 401 from any call opens "Your session has expired" with **Sign in** or **Stay on page**, instead of a failed action |
| **Accessibility** | Skip link, visible focus outline, tab bars exposed as ARIA tablists with ←/→/Home/End, `aria-current` on navigation, live regions for messages, honours dark mode and reduced motion |

## Brand themes (2026-11-18)
Every screen takes its colours, fonts, corner rounding, app-bar look and chart colours from one file, `config/brand.yaml`, so the app can wear any company's brand without page changes. The active theme is **Principal Financial Group** (product owner's request), built from the public Principal Design System tokens. Revised 2026-11-19 after review ("too much blue"): white cards on a Gray 6 (`#F6F6F8`) canvas; dark navy (`#002855`) for the app bar, headings, buttons, links and selected items in place of Principal blue; neutral greys (not sky blue) for highlights, table headers and notes; Gray 1 (`#333333`) body text; Principal blue only for the keyboard focus ring and one chart series; success, warning and error in darker shades of the PDS utility colours so they can be read as text; light mode only (the navy dark mode was removed). Every text colour passes WCAG AA (4.5:1) on every background it sits on, and body text and headings pass AAA (7:1): body text 12.6:1, navy 14.6:1, secondary text 5.9:1 or more. The brand typeface FS Elliot is licensed by Fontsmith: it is used where installed, or through `fonts.css` once licensed; otherwise Helvetica Neue / Arial. The original look is kept as the `meridian` theme.

| To | Do |
|---|---|
| Switch theme | `active:` in `config/brand.yaml`, or `MERIDIAN_BRAND=<key>` per deployment |
| Add a company | Copy a theme block under a new key and change the values (colours, dark mode, app bar, charts, fonts, radius, product and company names) |
| Add a logo | Put the company's licensed file in `config/brand/` and name it in `logo:`; it replaces the mark in the app bar (served at `/brand/logo`). No logo is shipped |
| Check a theme | `meridian brand check`: every token present and every text/background pair at WCAG AA contrast (4.5:1); the same check runs in the test suite |

How it works: pages keep using the shared CSS variables (`--bg`, `--surface`, `--accent`, `--crit`, `--radius-lg`, `--font`, `--appbar-bg`, `--s1`…); `src/meridian/branding.py` writes them for the active theme into every page (app shell, console, sign-in pages), after each page's own defaults. Code: `branding.py`, `config/brand.yaml`; tests `tests/test_branding.py`.

## Console update (product owner feedback, 2026-11-13)

| Screen | What changed |
|---|---|
| Home | Every workspace opens on: four headline numbers (assets by product line, proposals approved, highest risk-budget use, compliance); **Needs your attention** (proposals awaiting your role with a one-line summary, risk-budget and glide-path requests you can decide, open exceptions, risk-budget warnings, hard-limit failures); **The series at a glance** (each vintage's mutual fund and CIT assets, glide path vs proposed equity, what each fund holds today, risk budget used, approval and compliance); risk budget across the series; changes since the last run. Leadership and Compliance also see production blockers |
| Funds & vintages | Grouped by product line (mutual funds `MTRS`, CITs `MTRT`) with a product-line filter. Each fund shows its assets, holdings by asset class, its own glide path, the proposal and equity drift. Expanding a fund compares glide path, proposal and holdings by asset class |
| Positioning | Opens on a **series summary**: every vintage side by side with a series total weighted by fund assets, in three measures (tilt vs glide path, proposed weights, holdings drift). **Vintage detail** keeps the drill-down and weight adjustments and adds a mutual fund vs CIT comparison |
| Proposals | Starts with **What is being approved**: the weights, which funds they become the approved target for, that no trades are placed, a one-line summary, a **Glide path adjusted** note when the run built on an Investment Committee adjustment, and each approver's status. Then the weights table (grouped, with tilt and change since last run), the agents' reasoning, disagreement in words, compliance with any warnings, and the decision |
| Approvals | **Waiting for you** first, then every proposal with the funds affected, a short summary (equity tilt, largest tilts, tracking error and budget used, compliance) and each approver's status; pending risk-budget and glide-path requests |
| Glide path | Glide path today by fund (mutual funds roll down monthly, CITs semiannually), approved adjustments in force, requests awaiting the Investment Committee (approve or reject here), and a form to propose an adjustment (apply to all funds, a product line or one fund, then click the vintages to include) with a preview against the IPS bands. Uses the same API and approval rules as the Trading screen |
| Agent votes | A six-step plain-language account of how the agents decided, a scoreboard (plain method names, risk officer flag, peer score, vote points, times voted best and weakest, shortlist and revision) and a detail panel per method. Per-vintage vote results are folded into a section below |
| Risk budget | Series summary (highest, average and asset-weighted use; vintages at warning), a bar per vintage against the warning line and the budget, a matrix of where the budget goes across vintages, and an explanation of the two ways to change risk use (adjust weights vs change the budget). The budget request shows each vintage's use before and after |
| Look-through & search | Typing shows a suggestion list under the box without moving the page; pick one security with the mouse or arrow keys and Enter. The chosen security is shown in a highlighted "Selected" bar with a Clear button, and selected rows are highlighted in the drill-down tables |

Product-line data comes from `config/trading.yaml` and, in the hosted app, from uploaded or booked positions and approved glide-path adjustments (`meridian.trading.overview`). Holdings remain example data until custodian or transfer-agent files are loaded.

## Console — what each role sees
| Role (sign-in group) | Workspace tabs | Home page shows | Can act |
|---|---|---|---|
| Portfolio Manager (`portfolio_manager`) | Home · Funds & vintages · Positioning · Proposals · Changes since last run · Fund risk · Risk budget · Metrics · Look-through & search · Glide path · Approvals · Exceptions · Agent votes | Proposals awaiting you, largest tilt, expected returns | Approve / reject / request changes; adjust weights; request risk-budget changes |
| Risk Analytics (`risk`) | Home · Fund risk · Factor risk · Stress tests · Risk history · Look-through & search · Risk budget · Metrics · Candidate risk · Positioning · Proposals · Approvals · Exceptions | Max TE vs limit, worst simulated drawdown, warnings | Co-approve tilts and adjustments; request/approve risk-budget changes |
| Research / Analyst (`analyst`) | Home · Positioning · Changes since last run · Metrics · Factor risk · Look-through & search · Capital market assumptions · Agent votes · Glide path | Regime, biggest CMA-judge adjustment, competing methods | Adjust weights (absolute/relative) for approval |
| Manager Selection (`manager_selection`) | Home · Funds & vintages · Underlying funds · Look-through & search · Positioning | Funds, derivatives use, liquidity | (DD workflow — roadmap Phase 5) |
| Leadership (`leadership`) | Home · Funds & vintages · Board memo · Changes since last run · Fund risk · Stress tests · Risk budget · Metrics · Glide path · Approvals · Exceptions | Approvals outstanding, production blockers, compliance status | Approve glide-path changes |
| Compliance (`compliance`) | Home · Compliance · Exceptions · Risk budget · Look-through & search · Compliance report · Decision ledger | FAILs, warnings, attestations, blockers | Attest; approve exceptions |
| Audit (`audit`) | Home · Decision ledger · Exceptions · Compliance · Compliance report | Ledger integrity, actors, retention | Read-only |
| Admin (`admin`) | **User access** screen (`/admin`), plus the read-only Audit view of the console | — | Add, edit, disable and delete users; switch permissions on/off; access review and access log (doc 14 §5). Deploys happen in GitHub Actions |

A person with several roles picks the workspace from the role selector in the side bar; only their own roles are listed. The tabs appear grouped under Overview, Portfolio, Risk and Governance, so their order on screen follows those headings.

**Permissions** (switched on or off per person in User access, doc 14 §5) sit on top of workspaces: `investment_committee` lets a Leadership user record committee decisions; `chief_compliance_officer` lets a Compliance user accept exceptions and approve policy changes (only the named CCO); `route_manager` lets a person change order routes on the Trading screen; `approver` (since 2026-11-13) lets a Portfolio Manager or Risk user record approval decisions on proposals, risk-budget changes and trade lists, so a PM or Risk user without it reviews only. Without the permission the approval form is replaced by a note saying which permission is needed; the server refuses the decision either way.

Design rules applied across every view:
- **"Why?" is always one click away.** Every proposal shows its rationale, ensemble, invalidation conditions and dissent; **Why?** buttons on proposals, compliance results and CMAs list the decision records behind them (people's decisions highlighted), with a jump to the full record for Compliance and Audit.
- **Exceptions are worked to closure.** Rule-engine WARN/FAIL results open an exception automatically; Compliance and Risk can raise one. Owner, due date, notes, remediation, CCO acceptance (always time-limited, at most 365 days) and closure (by Compliance, not by the opener alone) are each written to the hash-chained governance ledger.
- **Evidence on demand.** Compliance and Audit can search every run's ledger and the governance ledger (words, type, vintage, actor, dates), export the results as CSV for sampling, and download a run's evidence pack.
- **Approvals cannot be rubber-stamped.** The approver must tick that they read the rationale, dissent and compliance results, and must give a reason. FAILs block approval in the UI and again in code.
- **Segregation of duties.** One person can't decide the same vintage in two roles, and a requester can't approve their own risk-budget change.
- **Synthetic-data and compliance status banners** appear on every page.
- The ledger opens only in the Compliance and Audit workspaces; other roles see record IDs.

## Trading screen (`/trading`, built 2026-11-10; redesigned 2026-11-13)
A separate page in the app bar, for the implementation workflow in doc 17. Tabs: **New trade** (opens first), **Trade lists**, **Funds & securities** (incl. positions upload and strategic tables), **Cashflows**, **Glide path & bulk changes** (scope: all funds, all mutual funds, all CITs or one fund, then chosen vintages picked by clicking), **Routing & settings** (incl. **Calculation templates**: propose, approve by a second person with the Approver permission, retire), with an **All funds / Mutual funds / CITs** switch on every tab. A draft list's **Tranches** view has **Use a calculation** (preview per order, then apply). PMs and analysts prepare; PMs rebalance and approve; glide-path changes need an Investment Committee member's approval; route changes need the `route_manager` permission; Risk, Compliance, Audit, Leadership and Admin see it read-only.

**New trade** is a task-based builder with four steps on one page:
1. **What do you want to do?** Four tiles: **Invest cashflows**, **Rebalance to a target** (PM only), **Trade a security**, **Exit a position**. Below them, **Start from your goal** maps plain goals ("stay as positioned last night", "get back to the glide path", "move to a strategic view", "implement the approved proposal", "buy or sell a specific security", "sell a position completely") to the right tile and mix in one click.
2. **Set it up.** Mix tiles with plain names and one-line explanations: **Keep the current mix** (previous night close; cashflows only), **Back to the glide path** (neutral), **Strategic mix**, **Approved proposal**. *Trade a security* has a fund picker, a security search (ticker, name or asset class; 12 largest holdings by default), and per-order actions **Buy amount**, **Sell amount**, **Trade to weight** (% of NAV) or **Sell all**, with the estimated trade, weight after and a live cash check ("Not enough cash" when buys exceed uninvested cash).
3. **Impact: now vs after these trades.** **See the impact** calls the same endpoint with `dry_run: true`: nothing is saved or recorded. The panel shows totals (orders, buys, sells, uninvested cash now → after, average *Off target* now → after, compliance after), a **By fund** table with off-target bars (grey now, blue after), equity now → after against glide-path equity, then for the selected fund an **asset mix now vs after** bar chart with target and glide-path markers and a grouped table (now, after, change, target, glide path, gap now, gap after), notes, compliance detail, and expandable securities and orders.
4. **Create the draft trade list** with a reason (≥10 characters). The draft opens on **Trade lists**.

**Trade lists** opens each list on **Impact: now vs after** (the same panel, from the saved preview), with **Orders** and **Tranches** views, the approval form ("I reviewed the orders, the impact (now vs after), the compliance check and the notes"), the Charles River export and fills. A fund's page on **Funds & securities** has **Trade a security** and **Exit a position** buttons that open New trade with that fund chosen.

Step-by-step use with screenshots: doc 06 §10. Tests: `tests/e2e/test_ui_trading.py` (TRD-1 to TRD-23).

**In progress** and **Files** (2026-11-18): trades by stage with % filled, dates with open orders and an order blotter; every Charles River import and fills file, viewable in the app as a table or downloadable again. Doc 06 §10.10a and §10.10b.

## Policy screen (`/policy`, built 2026-11-18)
In the app bar for every workspace. Tabs: **Investment Policy Statement** (versions with status, read or redline against the previous version, propose a change with a preview of the redline, approve as Investment Committee or CCO), **Glide paths** (library with an equity chart against the IPS path and anchor tables, a table editor for new paths and versions with live row totals, which path each fund follows, requests waiting for the Investment Committee), **Change log**. Waiting approvals appear in **My work**. Doc 06 §13; tests `tests/e2e/test_ui_policy_files.py` (POL-1, POL-3, TRD-30/31).

## Regulations screen (`/regulations`, built 2026-11-10)
Funds (tag regulations, controls on current holdings, required people, **fiscal year end** per fund, set for ticked funds by Compliance), Obligations (owner, due date, evidence, overdue), Regulation library (US and international) and Change log, with the All / Mutual funds / CITs toggle. Compliance tags; the CCO removes tags and waives obligations; Compliance, Risk, Leadership and PMs work obligations; others read. Doc 06 §12, doc 18.

## User access screen (`/admin`)
Users, Access review (CSV) and Access log tabs. Admins edit; Audit and Compliance read. Doc 06 §11, doc 14 §5.

## Hosted app vs local console
**Hosted (built, 2026-11-09).** The FastAPI app serves the Console at https://d3maw6l4k5cc0v.cloudfront.net. People sign in with Amazon Cognito (doc 06, "Signing in"); their Cognito groups decide which workspaces they see. Approvals, weight adjustments and risk-budget requests write directly to the ledger in the app's database, and the run picker lists every run published by the `agent-run` workflow. Sessions last 8 hours. Exports for the next run: `/api/export/positions.csv`, `/api/export/risk-history.csv`, `/api/export/policy-overrides`. Hosting and operations: doc 14.

**Local (for development and offline review).** `meridian ui` generates one self-contained page per run, with a role picker to preview every workspace. Approvals made there produce a `meridian approve` command that writes the decision to the local ledger.

See doc 12 for positioning, risk budgets, metrics and adjustments, and doc 13 for the risk analytics tabs.

## Notebooks (`notebooks/`)
| Notebook | Audience | Contents |
|---|---|---|
| `01_portfolio_manager_workbench.ipynb` | PMs | Run pipeline, series summary, glide path chart, vintage drill-down, entity what-if, approval |
| `02_research_cma_lab.ipynb` | Research | Every CMA method, judge vs blend, PC-method sensitivity to CMA shocks |
| `03_compliance_audit_workbench.ipynb` | Compliance, audit | Obligations by entity type, rule matrix, ledger tamper detection, evidence extract |
| `04_risk_analytics_workbench.ipynb` | Risk, PMs, research | Every risk-analytics figure in the Console, with editable weights, scenarios and factors |

Launch: `pip install -e ".[dev]" jupyterlab && jupyter lab notebooks/`. Notebooks are committed with outputs so they read on GitHub without running.
