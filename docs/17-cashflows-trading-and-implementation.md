# 17 — Cashflows, Trading & Implementation

**Version 0.4 · 2026-11-10 · Status: decisions recorded (§0); cashflow trading, tilts, single-security tickets, full exits, tranches and the route permission are built and live in the **Trading** screen (`/trading`); remaining items as phased in §5; held items in the backlog (§9).**

## 0. Decisions and what is built (2026-11-10)
**Product-owner decisions**
- **Allocation strategies:** *Previous night close* follows actual holdings at last close; *Neutral* follows the strategic glide-path weights with no tilts; *Strategic* is a **separate table** for a given trading day that may or may not follow the glide path.
- **Cashflows are split pro rata** across the chosen table. Gaps to target are closed only by a rebalance or an explicit decision, never by a cashflow.
- **Charles River:** an import file today (mocked for now); an API connection later.
- **Fund structure:** mostly fund of funds, but a fund can mix underlying funds, ETFs and individual securities. There are **target-date mutual funds and target-date CITs**; Meridian now separates them, with a toggle to see all, mutual funds only or CITs only.
- **Cashflow sources:** transfer agents and custodians. Intake stays flexible: Excel or CSV files, or an API connection.
- **Routes:** CIT trades → **State Street**; mutual fund trades → **SS&C (formerly DST)**; individual securities → the **internal trading desk**.
- **Routing goes by the type of security traded** (confirmed): a CIT fund buying an ETF sends that order to the internal desk, not State Street.
- **ETF cash buffer** (confirmed): each ETF buy is cut by the buffer (50 bp) and that amount stays in cash.
- **Route changes:** controlled by a new per-person permission, **Trade route manager** (`route_manager`), with an audit trail of every change and of who holds the permission. Who should hold it, whether a second approver is needed, and the Charles River version and setup are held for later (§9).

**Built and live (Trading screen, shadow mode)**
| Item | What works now |
|---|---|
| Product lines | Meridian Target Retirement Funds (mutual funds, `MTRS-2030`…`2070`) and Meridian Target Retirement Trust (CITs, `MTRT-2030`…`2070`); example NAVs, positions and prices. All / Mutual funds / CITs toggle on every tab |
| 15 Universe view | Per fund: held securities, a held security with no target (legacy fund), and not-held candidates (e.g. IEFA) and available securities |
| 16 Roll-down per fund | Monthly, quarterly, semiannual or annual per fund (`config/trading.yaml`); neutral targets step on that schedule. Examples: mutual funds monthly (2065 and 2070 annual), CITs semiannual |
| 3 Allocation tables | Previous close, Neutral and Strategic per fund. The Strategic table follows the glide path or holds custom weights (must total 100%); PM-only changes, with a reason, versioned and recorded |
| 1 Cashflow intake | Excel/CSV upload (all rows validated; any bad row stops the load), templates, hand entry, and an API endpoint for transfer-agent or custodian connections (token) |
| 1 Trade generation | Net cashflow per fund, pro rata over the chosen table; outflows never sell more than is held; units, whole ETF shares and $1,000 bond face |
| 4 No target | Never part of cash allocation; shown in the preview |
| 6 Exclusions | Per security, for one fund or all, optional end date; the excluded share is spread over the other holdings or left in cash (a setting) |
| 10 ETF cash buffer | Series-level setting (default 50 bp) applied to every fund, with stricter fund overrides. Each ETF buy is cut by the buffer and the difference stays in cash so a price move can't overdraw the account (confirmed 2026-11-10) |
| 8 Preview | Current vs post-trade per security (value, weight, target, post-trade vs target), cash before and after, buffer held, rounding left in cash, and the IPS rules run on post-trade asset-class weights against the fund's own glide path |
| 2 Routing | By the type of security traded: mutual fund → SS&C, CIT → State Street, ETF, stock, bond → internal desk. Changing a route needs the **Trade route manager** permission (switched on or off per person in User access) and a reason. Audit: each change is a `routes.change` record in the hash-chained ledger with before and after; the Routing tab shows who holds the permission now; the User access log shows who granted or removed it and when; the access review lists it per person |
| Approval | PM approves with a checkbox and reason; blocked by an error or IPS FAIL; approval by the preparer is allowed but flagged |
| 1 Charles River file | Approved list → CSV import file (mock layout, one row per order or per tranche, with destination, parent order ID and tranche number). Each download recorded with a SHA-256 fingerprint |
| 5 Tilts | Per security, for one fund or all, ± basis points (up to 500), optional end date. Applied to whichever allocation table is used; funded pro rata from the other holdings so the table still totals 100%. PM only, with a reason; shown on the fund page and in each trade list's notes |
| 12 Single-security tickets | From a fund's page: hand-entered buys and sells (including a first purchase of a not-yet-held candidate). Buys are paid from the fund's cash; refused if cash would go negative, if more is sold than held, or if the security is excluded or being exited. The ticket becomes a draft trade list (`TK-…`) with the same preview, IPS check, approval, tranching and export |
| 11 Full exits | PM flags a security for exit (one fund or all): no cashflow trades, no new buys, and its share of each cashflow goes to the other holdings. "Create exit trade list" (`EX-…`) sells each whole position, in one go or in tranches. Proceeds stay in cash until a rebalance |
| 9 Tranches | On any draft trade list (the bucket): series of dates and percentages, equal ("Split equally") or unequal, applied to the whole list, a fund or a single security; the most specific wins, so several series can run in one bucket; a security can be left out of tranching. Data checks on save: each series totals 100%, dates are weekdays, in order and not before the trade date, quantities respect lot sizes and add back to the order exactly, no empty tranche. Bucket view: totals by date, then fund → security → tranche |
| Records | Cashflow loads and cancellations, table and setting changes, generate, approve, cancel and export are hash-chained governance records (`dr_type` "trading"), searchable in the console's Decision ledger |

| Approved-proposal table | Fourth allocation table: the latest proposal both PM and Risk approved in the console, split to securities |
| Rebalance | Explicit decision (PM, reason) to close gaps to the approved, neutral or strategic table; minimum drift; cash invested; no-target, excluded and exiting holdings untouched; list `RB-…` |
| Positions upload | Excel/CSV of holdings at last close replaces example data per fund; any bad row stops the load |
| Fills and booking | Fills file keyed by the Charles River order or tranche ID (or "mark all filled" in shadow mode); positions and cash update; cashflows settle; list becomes *Filled and booked* |
| Holidays | Tranche dates may not fall on US market holidays (2026–2028 calendar in `config/trading.yaml`) |
| Regulation controls | Controls of any regulation tagged on the fund run on every trade list (doc 18) |

**Still to build:** 7 derivatives, 13 custom calculations, 14 in-kind, 17 mandates, 18 margin and leverage, 19 capital calls; rebalance trades (closing gaps to target); position files from custodians and TAs; Charles River results coming back; the API connection. Known limits: until files arrive from custodians and transfer agents, positions are example data or what you upload; later tranches use today's prices as estimates.

Requested by the product owner for the system as a whole, Portfolio Managers and Target Date analysts. This brings most of roadmap **Phase 6 (Implementation)** forward and adds items that were not on the roadmap (mandates, margin, capital calls, redemptions in kind).

## 1. Where Meridian stands today
Meridian decides **strategic and tactical weights by asset class** (13 asset classes per vintage), checks them against the IPS, records approvals and shows risk and look-through. It has **no** fund cash, no security-level positions it owns, no orders, no routing and no connection to Charles River. Look-through holdings come from public iShares files and are for analysis only. Derivatives appear only as a flag (`uses_derivatives`) and an exposure limit (DERIV-LDU, 10%). The glide path steps monthly for the whole series.

So every item below is new build. The good news: the parts that make it safe already exist and are reused: the hash-chained ledger, the deterministic compliance engine, approvals with segregation of duties, the governance ledger for settings changes, and the role-based Console.

## 2. Boundaries (proposed)
- **Meridian proposes orders. It never executes.** Orders go to Charles River (CRD) for its own pre-trade compliance and execution, or to the transfer agent, custodian or internal desk, depending on the route.
- **Two compliance checks.** Meridian's engine runs before an order leaves (IPS, mandate, buffer, include/exclude). CRD runs its own rule set again. A CRD compliance failure comes back to Meridian as an exception (doc 11, Exceptions).
- **Human approval before release.** A trade list is approved like a proposal (PM, plus Risk when material). Release to a route is a separate, recorded step.
- **Shadow first.** Until production (doc 03 Phase 8), orders are generated, checked and exported as files, not sent. Live connectivity is a production item.
- **Every number is a decision record.** Cashflow, allocation strategy used, targets, tilts, exclusions, buffer, tranches, route and release are all written to the ledger, so audit can rebuild any trade from its inputs.

## 3. New building blocks
| Block | What it holds |
|---|---|
| **Security master** | Every instrument: ETF, mutual fund / CIT, stock, bond, future, option, swap, FX forward, cash. Identifiers (ticker, CUSIP, ISIN, CRD ID), asset class, currency, multiplier, settlement cycle, tradeable flag |
| **Fund and account model** | Fund (vintage) → accounts (custody, futures/margin, FX) → positions by security, with cash by account and currency |
| **Target tables** | Security-level targets per fund, one table per allocation strategy (item 3), versioned and change-controlled |
| **Cashflow book** | Subscriptions, redemptions, in-kind flows, capital calls, distributions: date, fund, amount, type, source, status |
| **Order book** | Orders and child tranches: side, quantity or amount, security, fund, route, status from draft through filled |
| **Routes** | Charles River, transfer agent / custodian, internal desk: settings per fund or security type, with a change log |
| **Mandates** | Rules attached to one or more funds, compiled into the compliance engine |
| **Trading controls** | Include/exclude lists, tilts, cash buffer, full-exit flags, roll-down schedules, custom calculations |

## 4. Requirement by requirement
Size: **S** about a week, **M** two to three weeks, **L** a month or more (Claude-built, shadow mode, excluding vendor connectivity).

| # | Requirement | Proposed design | Depends on | Size |
|---|---|---|---|---|
| 1 | Cashflows in and out → trades → Charles River for compliance and execution | Cashflow book feeds an allocation engine (net flow × target weights, rounded to tradeable lots), producing a trade list per fund. After approval, the list exports in CRD's order-import format (file now; FIX or API in production). CRD's compliance results and fills come back and update order status | 3, 4, 10; CRD import format from your CRD admins | L |
| 2 | Route to transfer agents / custodians or the internal desk; switchable, with changes logged | Route is a setting per fund and security type (e.g. mutual funds and CITs → TA, ETFs and futures → desk or CRD). Changes need a reason and are written to the governance ledger, like user access changes today | 1 | M |
| 3 | Toggle allocation strategy: previous night close, neutral, strategic, each with a configurable table | One target table per strategy per fund; the strategy is chosen per cashflow run (default per fund), and the choice is recorded. **Needs your definitions (Q1)** | Security master | M |
| 4 | Securities with no target are left out of cash allocation | A rule in the allocation engine: target missing or zero → no trade, and the security is listed as "held, no target" in the preview so it is visible, not silent | 3 | S |
| 5 | Tilt toward or away from specific holdings | Security-level tilts (± bp or % of target), funded pro rata from the rest of the asset class or from a named holding. This reuses today's asset-class adjustment logic one level down; risk and compliance recalculate | 3, security master | M |
| 6 | Include or exclude specific holdings or funds from trading | Do-not-trade lists at series, fund and security level, with reason and expiry. Excluded positions keep their weight; their share of the flow is redistributed or left in cash (your choice, Q4) | 1 | S |
| 7 | ETFs and derivatives traded and held | Security master and positions support ETFs, futures (notional, margin), options (delta), swaps and FX forwards. Exposure uses notional or delta-adjusted values, so risk, look-through and DERIV-LDU see derivatives properly | Security master | L |
| 8 | Post-trade exposures before trading, current vs future | **Trade preview**: current, post-trade and target for each security, asset class and vintage, plus TE, risk budget, compliance, cash and buffer, side by side. Reuses the Positioning and Fund risk views | 1, 7 | M |
| 9 | Tranches: dates and percentages, equal or unequal, fund and security level, include/exclude, bucket view, data checks | A trade bucket holds parent orders; each parent has a tranche schedule (dates + % or amount). Equal split or hand-entered. Checks: total = 100% per parent, dates are business days and in order, no tranche below lot size, each tranche respects buffer and exclusions. Bucket view: tree from bucket → fund → security → tranche, with status | 1 | L |
| 10 | Cash buffer for ETF trades, set once at the top and cascading | Series-level buffer (e.g. 50 bp) with optional fund-level overrides (only stricter). Buys are cut so post-trade cash ≥ buffer after settlement timing (T+1 vs flows); the preview shows buffer used per fund | 1, 8 | S |
| 11 | Full redemptions: stop trading, fully exit | "Exit" flag on a security or fund: no new buys, its target goes to zero, sells the whole position (optionally in tranches), then it is closed and blocked. Each step recorded | 6, 9 | M |
| 12 | Trade individual securities within funds | Manual security-level order ticket inside a fund, run through the same preview, compliance, approval and routing | 1, 8 | S |
| 13 | Custom calculations (e.g. slowly sell down before a redemption in kind) | Named, versioned calculation templates (glide-down schedules, sell-down %-per-day, liquidity-capped sells) that produce tranches. Starts as a set of parameterized templates; free-form formulas only behind change control (model-risk rule, doc 04) | 9 | M |
| 14 | Redemptions in kind | In-kind cashflow type: build the basket (pro rata slice or custom basket with cash for odd lots), check it against the fund's in-kind policy and liquidity program, and produce delivery instructions to the custodian or TA instead of market orders | 1, 2, 7 | L |
| 15 | See securities held and securities not held but possible in future | **Security universe** view per fund: held (with target, weight, status) and approved-not-held (watch or candidate list, with why and owner). Ties into Manager Selection's watch list (Phase 5) | Security master | S |
| 16 | Glide path roll-down frequency per fund (monthly, yearly, twice-yearly) | Roll-down schedule per fund (frequency and date rule), so targets step on that schedule instead of the series-wide monthly step. Each roll generates a proposed rebalance | 3 | S |
| 17 | Domestic and international mandates, assigned to one or many funds | Mandate library: each mandate is a set of rules (eligible markets, issuers, ratings, ESG or country restrictions, concentration). Assign many-to-many to funds; the compliance engine evaluates all of a fund's mandates before an order leaves | Security master | M–L |
| 18 | Margin and leverage | Track initial and variation margin for futures and cleared swaps, collateral and gross/net leverage per fund; limits in the compliance engine. Cash needed for margin counts against the buffer | 7 | M |
| 19 | Capital calls | Commitment ledger per fund and vehicle: committed, called, unfunded, expected call schedule. Calls appear as forecast outflows; the allocation engine raises cash ahead of the due date | 1 | M |

**Rough total:** about 6–8 months of build in shadow mode for all 19, done in the phases below. Each phase ends with UAT scripts (doc 16) and automated tests, as now.

## 5. Proposed phases
| Phase | Items | Why first |
|---|---|---|
| **A. Foundations** | Security master, fund and account model, positions, target tables; 15 (universe view), 16 (roll-down schedule), 4 | Everything else needs security-level positions and targets |
| **B. Cashflow allocation** | 1 (generate trades), 3, 5, 6, 10, 12 | Daily core workflow for PMs and analysts |
| **C. Preview and approval** | 8, plus trade-list approvals in the existing approval flow | Safety check before anything leaves |
| **D. Routing and Charles River (file-based)** | 1 (CRD export and return), 2 | Can run in parallel with the current process with no live risk |
| **E. Advanced trading** | 9, 11, 13 | Builds on orders and routes |
| **F. Fund events and instruments** | 7 (derivatives), 14, 17, 18, 19 | Each needs data or policy input from you, your CCO or vendors |

**AWS cost:** phases A–C and E run on the current app and database at no added cost (more data in Postgres, still small). File exchange with CRD, custodians and TAs during development is download/upload in the Console. Automated file transfer (SFTP or S3) and live FIX connectivity add cost and security work, so they go with production readiness.

## 6. Questions for the product owner
*Answered 2026-11-10: 1, 2 (import file), 3 (routes, by security type), 5 (structure and sources), buffer reading; see §0. Held by the product owner (§9): 2 (version, hosting, IBOR), 3 (who holds the route permission; second approver). Still open: 4 (excluded share: default spread, can be set to cash), 6–9.*
1. **Allocation strategies (item 3).** My reading, please correct: *Previous night close* allocates the flow in proportion to the fund's actual holdings at last close (keeps current drift and tilts). *Neutral* allocates to the strategic glide-path weights with no tactical tilts. *Strategic* allocates to the approved targets including tactical tilts. Also: is the flow allocated as a pro-rata slice, or used to close the gap to target first?
2. **Charles River.** Which CRD version and hosting (on-premises or Charles River SaaS)? How do orders get in today: order import file, FIX, or API? Who are your CRD admins? Does CRD hold the official positions (IBOR) Meridian should read back?
3. **Routes (item 2).** Which security types go to which route today (e.g. mutual funds and CITs to the transfer agent, ETFs and futures to the desk)? Who may change a route, and does a change need a second approver?
4. **Exclusions (item 6).** When a holding is excluded, should its share of a flow be spread over the other holdings or stay in cash?
5. **Fund structure.** Are the target-date building blocks mutual funds, CITs, separate accounts, ETFs, or a mix? Where do daily cashflows come from (TA file, custodian, recordkeeper)?
6. **Derivatives and leverage (items 7, 18).** Which instruments are in scope first: index futures, Treasury futures, FX forwards, swaps, options? Is any fund a limited derivatives user under Rule 18f-4?
7. **Capital calls (item 19).** Which vehicles make capital calls: private markets sleeves, CITs holding private funds? How do call notices arrive?
8. **Mandates (item 17).** Do mandates exist as documents today (client IMAs, sub-advisory agreements)? Can you share one domestic and one international example?
9. **Who approves trade lists?** PM alone for flow-driven trades under a size threshold, PM + Risk above it? What threshold?

## 7. Regulatory points to confirm with the CCO
- **Derivatives (Rule 18f-4):** a derivatives risk management program and VaR limits, unless the fund qualifies as a limited derivatives user (≤10% derivatives exposure, which the DERIV-LDU rule already encodes).
- **Liquidity (Rule 22e-4):** in-kind redemption policies, the 15% illiquid limit and liquidity classification of anything delivered or held.
- **Cross trades (Rule 17a-7):** if the internal desk crosses between funds, the crossing conditions must be met and recorded.
- **Borrowing and leverage (Investment Company Act §18):** asset coverage limits for any borrowing or margin.
- **Best execution and trade allocation:** fair allocation across funds when one order is split, with the allocation recorded; this becomes part of the trade bucket design (item 9).
- **ERISA plans and CITs:** prohibited-transaction checks for crossing and in-kind flows involving plan assets.

## 8. Open UAT findings carried forward (not lost)
These stay open and are tracked in doc 16 (findings log) and doc 03 (backlog):
- **F-3** run data is not filtered by entitlement (informational, for the entitlements design).
- **F-4** issuer names not normalized in look-through. The security master in Phase A fixes this as a side effect.
- **F-11** Risk budget doesn't show pending adjustments. The trade preview (item 8) is the natural place to resolve it.

## 9. Backlog (held by the product owner, 2026-11-10)
| Item | Note |
|---|---|
| Who may change a route | The permission exists; deciding which people or roles hold it is held. Nobody holds it until an admin switches it on |
| Second approver for route changes | Not built; today one permission holder with a reason |
| Charles River version, hosting and set-up | Needed before mapping the mock file to the real import specification |
| Charles River as source of official positions (IBOR) | Decides where Meridian reads positions from |
| Charles River API connection; compliance results and fills coming back | Production item |

