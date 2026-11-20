# 16 — User Acceptance Test (UAT) Scripts

**Version 0.8 · 2026-11-18 · Phase 3 exit criterion: each persona completes their top three tasks (doc 03).**

One script per role, built from the personas (doc 15). Each step has an expected result and the ID of the automated browser test that checks the same thing. People run the scripts to judge whether the tool is *useful*. The automated tests check, on every request, that it still *works*.

## How to run

**By hand (hosted app).** Sign in at https://d3maw6l4k5cc0v.cloudfront.net with the account for the role (doc 14 §5). Mark each step Pass / Fail / Comment. Record anything confusing, slow or missing, even when the step passes: that feedback is the main output of UAT.

| Test account | Roles | Use for |
|---|---|---|
| Alex Eaton (full access) | All eight (approving also needs the Approver permission, doc 06 §1.9) | PM, Research, Manager Selection, Leadership scripts (switch workspace in the side bar) |
| RCTest User | Risk, Compliance | Risk and Compliance scripts; second approver for segregation-of-duties steps |

Approvals made in the hosted app are permanent ledger records (it is shadow mode, so no money moves). Use reasons that start with "UAT:" so they're easy to find later. To test as the fictional people in the roster (doc 15), an admin can invite extra logins using plus-addresses of an inbox you own (e.g. `you+maya@…`), which most email providers deliver to the same inbox.

**Automated (local or GitHub, no AWS cost).** The browser tests in `tests/e2e/` start the app on the test machine with development sign-in, a throw-away database and one offline pipeline run, then drive Chromium through every script below.
- Locally: `pip install -e ".[dev,app,e2e]"`, `python -m playwright install chromium`, then `MERIDIAN_OFFLINE=1 pytest tests/e2e -v` (add `--headed --slowmo 300` to watch).
- On GitHub: Actions → **uat** → Run workflow. The run summary lists every test; screenshots and traces of failures are kept 30 days as the `uat-evidence` artifact. Manual only, to keep Actions minutes low.

**Why not run the automated tests against the hosted app yet?** They would need stored passwords for dedicated test users and would write UAT records into the real ledger. That is possible later (a separate test user pool, or a staging copy of the app), but both add setup and AWS cost, so they are deferred.

---

## PM — Portfolio Manager (Maya Chen)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| PM-1 | Sign in with only the PM role | Workspace selector shows Portfolio Manager only; tabs: Home, Funds & vintages, Positioning, Proposals, Fund risk, Risk budget, Metrics, Look-through & search, Glide path, Approvals, Agent votes, grouped under Overview, Portfolio, Risk and Governance; your name in the app bar | `test_pm_01` |
| PM-2 | Proposals → 2040 → Approve without ticking the box, then with a 9-character reason | Blocked each time with a clear message (tick the box; reason ≥ 10 characters) | `test_pm_02` |
| PM-3 | Proposals → 2050: read *Why this proposal?*, *What would make this wrong*, *Dissent*, *Compliance*; tick, give a reason, Approve | "Decision recorded in the ledger"; Approvals tab shows 2050 / portfolio_manager / approve | `test_pm_03` |
| PM-4 | Positioning → 2045 → Adjust: Fixed Income short-dated +1pp funded from long-dated; reason; submit | Toast shows new TE, % of budget and compliance status; adjustment recorded | `test_pm_04` |
| PM-5 | Explain the largest change for 2050 using the active-weights chart and the ensemble rationale | You can state the biggest over/underweight and the reason in one sentence | `test_pm_05` (content present) |
| PM-6 | Sign in as a PM **without** the Approver permission; open **Proposals** → 2050, then **Approvals** | Proposal readable; note "Your account doesn't have the Approver permission" in place of the buttons; nothing waiting in Approvals | `test_pm_06`, `test_approvals_need_the_approver_permission` |

**Usefulness questions:** Could you approve with confidence from this screen alone? What did you have to look for elsewhere?

## RISK — Risk Analytics (Daniel Okafor)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| RISK-1 | Sign in with the Risk role | Tabs: Home, Fund risk, Factor risk, Stress tests, Risk history, Look-through & search, Risk budget, Metrics, Candidate risk, Positioning, Proposals, Approvals | `test_risk_01` |
| RISK-2 | Fund risk: scan all vintages | Every vintage 2030–2070 with total risk, effective duration, credit spread duration, VaR, diversification | `test_risk_02` |
| RISK-3 | Risk budget: find the vintage closest to its tracking-error budget | Percent of budget used shown for every vintage; you can name the closest and why (Fund risk drill-down) | `test_risk_03` |
| RISK-4 | Stress tests → Build a scenario: equities −20%, Treasury yields +100bp | Loss per vintage updates instantly; historical replays (e.g., global financial crisis) listed above | `test_risk_04` |
| RISK-5 | Look-through & search: "Treasury" | Every vintage's exposure and the underlying funds it comes through | `test_risk_05` |
| RISK-6 | After a PM approves 2055, co-approve it as Risk | "Decision recorded"; positions for 2055 become *approved* | `test_risk_06` |
| RISK-7 | Segregation of duties: one person with PM and Risk approves 2060 as PM, then tries again as Risk | Second decision refused: "Segregation of duties" | `test_risk_07` |
| RISK-8 | After a data refresh with SEC data: Look-through & search → **Largest ownership of market cap**; pick a company; **Download financials (CSV)** | Meridian $, market cap and % of market cap for US equities; the company's SEC financials (revenue, net income, EPS, cash flow, balance sheet, ratios) with CIK and periods; foreign listings never matched; before the refresh the card says the financials aren't loaded | `test_lookthrough_market_cap_us_equities_only`, `test_frames_to_frame_maps_ciks_to_tickers` |

**Usefulness questions:** Do the numbers reconcile with what the PM sees? What would you export for a risk committee pack?

## RES — Research / Strategist (Priya Raman)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| RES-1 | Sign in with the Analyst role | Tabs: Home, Positioning, Metrics, Factor risk, Look-through & search, Capital market assumptions, Agent votes, Glide path | `test_res_01` |
| RES-2 | Capital market assumptions → click US Large Cap | Every method's estimate, judge vs blend, and the judge's reasoning with method weights | `test_res_02` |
| RES-3 | Agent votes | Ranking of construction methods with votes and dissent | `test_res_03` |

**Usefulness questions:** Is the reason for each CMA clear enough to defend at committee? What history would you want next to it?

## MGR — Manager Selection (Marcus Webb)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| MGR-1 | Sign in with the Manager Selection role | Tabs: Home, Funds & vintages, Underlying funds, Look-through & search, Positioning | `test_mgr_01` |
| MGR-2 | Look-through & search: "Apple" | Securities/issuer count, holdings date, and every vintage's exposure with the funds it comes through | `test_mgr_02` |
| MGR-3 | Underlying funds | The building blocks behind each vintage, with their details | `test_mgr_03` |

**Usefulness questions:** What would you need to recommend replacing a building block? (Due diligence workflow is Phase 5.)

## LEAD — Leadership / Investment Committee (Elena Rossi)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| LEAD-1 | Sign in with the Leadership role | Tabs: Home, Funds & vintages, Board memo, Fund risk, Stress tests, Risk budget, Metrics, Glide path, Approvals | `test_lead_01` |
| LEAD-2 | Board memo: state the recommendation, top risk and any dissent | Memo shows run, policy, judgment engine, compliance review status and the synthetic-data warning | `test_lead_02` |
| LEAD-3 | Stress tests: worst historical loss for 2030 and 2070 | Historical replays per vintage | `test_lead_03` |
| LEAD-4 | Without the Investment Committee permission, try to record a committee decision; then with it | Refused without the permission; accepted by the permission check with it (the approval matrix still decides whether IC approval is needed) | `test_perm_01`, `test_perm_02` |
| LEAD-5 | Home: production blockers | CCO listed as unfilled, naming the placeholder (Robert Hayes) | `test_perm_05` |

**Usefulness questions:** Could you run a committee meeting from the memo? What is missing for a fiduciary review (fees, peer comparison)?

## COMP — Compliance (Robert Hayes)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| COMP-1 | Sign in with the Compliance role | Tabs: Home, Compliance, Risk budget, Look-through & search, Compliance report, Decision ledger | `test_comp_01` |
| COMP-2 | Compliance: find any WARN or FAIL | Rule, IPS section, severity and result per vintage from the deterministic engine | `test_comp_02` |
| COMP-3 | Compliance report | Marked DRAFT by the Agentic Compliance Officer, "not an attestation"; shows retention applied and production blockers | `test_comp_03` |
| COMP-4 | Decision ledger: filter "approval" and trace one approval | `approval.decision` records with approver, role and reason | `test_comp_04` |

**Usefulness questions:** Could you answer an examiner's "show me how AI output is supervised" from these screens? What would the exception workflow need?

## AUDIT — Audit (Grace Liu)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| AUD-1 | Sign in with the Audit role | Tabs: Home, Decision ledger, Compliance, Compliance report; no approve buttons anywhere | `test_audit_01` |
| AUD-2 | Side bar and Decision ledger | "Ledger: ✓ verified (n records)"; hash-chained ledger | `test_audit_02` |
| AUD-3 | Export the evidence pack for the run (today via `/api/runs/<run>/evidence`; no button yet) | Evidence JSON with integrity OK | `test_audit_03` |
| AUD-4 | Confirm a PM can't export evidence | Refused (403) | `test_audit_04` |

## ADM / ACCESS — Admin and access controls (Sam Patel)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| ADM-1 | Sign in with only the Admin role | Read-only Audit workspace only | `test_admin_01` |
| ACC-1 | Open the app signed out | Sent to sign-in | `test_access_01` |
| ACC-2 | Sign in with no role | "Your account has no Meridian role yet" | `test_access_02` |
| ACC-3 | As Audit, change the address to `…/runs/latest#pm` | Still only the Audit workspace | `test_access_03` |
| ADM-2 | Add a user with the manage-users workflow; confirm their tabs; disable them; confirm sign-in is blocked | As described in doc 14 §5 | Manual only (needs AWS) |
| ADM-3 | manage-users → `grant` `investment_committee` to a Leadership user, then `revoke` it | Run summary shows the user's groups after each change; takes effect at next sign-in | Manual only (needs AWS) |
| ADM-10 | Sign in with only the Admin role | Lands on **User access** (`/admin`) | `test_adm_10` |
| ADM-11 | Add user → tick Investment Committee without Leadership, then add Leadership; reason; send invitation. Edit → switch the permission off | Warning shown until Leadership is ticked; user listed as *Invited* with the permission; after switching off, the permission is gone; Access log shows create and set_access with reasons | `test_adm_11` |
| ADM-12 | Edit yourself: untick Admin; then save with a 5-character reason | Refused: can't remove your own admin role; reason too short | `test_adm_12` |
| ADM-13 | Access review → Download CSV | Matrix of users × workspaces/permissions; CSV downloads | `test_adm_13` |
| ADM-14 | As Audit, open User access | Read-only: no Add or Edit buttons | `test_adm_14` |
| ADM-15 | As a PM, look for User access | No link; the page is refused | `test_adm_15` |
| ADM-16 | Change someone's access while they're signed in | They're signed out and must sign in again; new access applies | API test `test_access_change_signs_the_person_out` |
| ADM-4 | Sign in with only a permission (e.g. `investment_committee`) and no workspace role | "No Meridian role" page | `test_perm_04` |
| COMP-5 | Compliance analyst without the CCO permission vs the CCO | Analyst refused (403); CCO passes the permission check | `test_perm_03` |

## OVS — Shared oversight features (built 2026-11-10)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| OVS-1 | PM → Proposals → 2050 → **Why?** | Panel lists the records behind the proposal (CIO ensemble, risk report, votes, approvals, adjustments) and the inputs shared by the run; Esc closes it | `test_ovs_01` |
| OVS-2 | Compliance → Compliance → **why** under a vintage → open a record | Panel for that vintage; "open in ledger" jumps to the full record with hashes | `test_ovs_02` |
| OVS-3 | Research → Capital market assumptions → US Large Cap → **All records** | The CMA judge record and its method records | `test_ovs_03` |
| OVS-4 | Leadership → **Changes since last run** | Previous run named; regime change; per vintage equity, E[r], vol, TE, ensemble, largest weight moves, compliance; CMAs that moved most. With only one run: "No earlier run to compare with yet" | `test_ovs_04` |
| OVS-5 | Compliance raises an exception with owner and due date → owner (PM) marks it remediated → Risk can't close → a different Compliance user closes | Each step recorded with a reason; the opener can't close their own case alone | `test_ovs_05` |
| OVS-6 | Risk tries to accept an exception; CCO accepts for 400 days, then 90 days | Risk refused; 400 days refused (max 365); 90 days accepted; ledger search shows `exception.open` and `exception.accept` in the governance ledger | `test_ovs_06` |
| OVS-7 | Audit → Decision ledger → **Download evidence pack**; **Search all runs** → Download CSV; PM tries search | Evidence downloads; search returns matches with CSV; PM refused | `test_ovs_07` |
| OVS-8 | Round 1 fixes: workspace label, Underlying funds proxies, report note, ledger header | "Leadership"; Returns proxy and Holdings proxy columns; note explaining record counts; no "verified verified" | `test_ovs_08` |

## TRD — Trading (Maya Chen as PM, Priya Raman as analyst) · built 2026-11-10 (doc 17)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| TRD-1 | App bar → **Trading**; switch All funds / Mutual funds / CITs | 18 funds, then 9 `MTRS-…` mutual funds, then 9 `MTRT-…` CITs | `test_trd_01` |
| TRD-2 | Open MTRS-2040 | Held securities; "Held · no target" (legacy fund); "Not held · candidate" (IEFA); three target columns | `test_trd_01` |
| TRD-3 | Cashflows → download the Excel template, fill two rows, upload; then add one by hand | Rows loaded and listed as New; a bad fund id stops the whole file with the row number | `test_end_to_end_cashflows_to_charles_river_file` |
| TRD-4 | CITs only → **New trade** → **Invest cashflows** → **Keep the current mix** → **See the impact** → reason → **Create draft trade list** | Impact lists only CIT funds; the draft opens on Trade lists; CIT orders routed to State Street, ETFs and bonds to the internal desk; IPS PASS | `test_trd_02` |
| TRD-5 | On the saved list: **Impact: now vs after**, then **Orders** | Asset-mix bars (now, after, target, glide path), Off target now → after, cash before/after, buffer held; Orders view by destination | `test_trd_02` |
| TRD-6 | Approve without the box, then with box and reason; download the Charles River file | Refused, then approved; CSV with one row per order and its destination; list shows *Exported* | `test_trd_02` |
| TRD-7 | Routing & settings without the Trade route manager permission; then with it: change a route with a 5-character reason, then a proper reason | Route boxes locked and "You do not hold the route permission"; with it: refused, then saved; the trading change log shows `routes.change`; the tab names who holds the permission | `test_trd_03` |
| TRD-8 | As an analyst | Can load cashflows and prepare cashflow, security and exit trades; **Rebalance to a target** is disabled; can't approve, change settings or target tables | `test_trd_03`, `test_settings_and_strategic_table_are_controlled_and_logged` |
| TRD-9 | PM: MTRS-2050 → Set custom weights (total ≠ 100%, then = 100%) with a reason; generate with Strategic | Refused until 100%; version 1 saved; trade list uses the custom table | `test_settings_and_strategic_table_are_controlled_and_logged` |
| TRD-10 | PM: Routing & settings → add a +50 bp tilt on a security for one fund and flag a legacy holding for exit; save with a reason | Saved and recorded; the fund page shows "Tilt +50 bp" and "Exiting"; the next cashflow trade list notes the tilt and skips the exiting security | `test_trd_04`, `test_tickets_exits_tilts_and_tranches_api` |
| TRD-11 | Fund page → **Trade a security**: search IEFA → **Add** → **Buy amount** $2,000,000 → **See the impact** → reason → create; then try a buy larger than the fund's cash | Draft ticket `TK-…` routed to the internal desk; the oversize buy shows **Not enough cash** in the ticket and is refused at preview ("Cash would go negative") | `test_trd_04`, API test |
| TRD-12 | Fund page → **Exit a position** → **See the impact** → reason → create | Draft `EX-…` selling the whole flagged position; post-trade position is zero | `test_trd_04`, API test |
| TRD-13 | On a draft list → Tranches: two dates at 25% and 70%, apply; then 25% and 75%; save. Try a fund-level and a security-level series in one cashflow list | Refused at 95%; saved at 100%; bucket by date, "1 of 2", quantities add back; the Charles River file has one row per tranche with its date | `test_trd_04`, `test_tranche_checks_and_split`, API test |
| ADM-17 | User access → edit a person → switch **Trade route manager** on, then off | Listed on the person, in the access review and in the access log with who changed it and when | Manual (same switch as ADM-11) |
| ADM-18 | User access → edit a PM → switch **Approver** on with a reason, then off with a reason; check the Access log and Access review | Warning "No Approver permission" while off; each change logged with who, when, before, after and reason; listed per person in the access review | `test_approver_permission_is_switched_on_and_off_and_logged` |
| TRD-25 | PM without the Approver permission opens a draft trade list; then with it | Note about the Approver permission instead of the Approve form, list not in My work; with it, approval works | `test_trade_list_approval_needs_the_approver_permission` |

**Usefulness questions:** Does pro rata by each table match how the desk allocates today? Does the impact view (now vs after, off target, gaps) answer "what will this do to the fund?" before you save? Do the goal shortcuts match how you think about a trade? Is the Charles River file missing any field your import needs? Is the ETF buffer applied the way you meant (§0 of doc 17)?

| TRD-14 | PM: **New trade** → **Rebalance to a target** → **Back to the glide path**, one fund → **See the impact** → reason → create → approve → export → **Mark all open orders filled** | `RB-…` list; fills booked; list *Filled and booked*; fund's Positions column shows "Booked from …" | `test_trd_14` |
| TRD-15 | PM: Funds & securities → upload a positions CSV (one bad security, then a good file) | Refused naming the row; then loaded and shown as "Uploaded file" | `test_approved_table_rebalance_positions_and_fills` |
| TRD-17 | A glide-path table request for two CITs is waiting; PM opens Glide path & bulk changes; then as an IC member approve it there | **Open the glide-path table** link shown; the request lists each fund's changes; requester can't approve; IC approval puts it in force | `test_trd_17`, `test_bulk_scopes_glide_path_and_strategic` |
| TRD-18 | PM: All mutual funds → asset-class tilt EM +25 bp; then a 4pp glide-path shift | Tilt applied to 9 funds; 4pp refused ("needs an IPS amendment") | `test_trd_17`, API test |
| TRD-16 | Rebalance to **Approved proposal** before and after PM + Risk approve a vintage | Refused ("no approved proposal"), then the list follows the approved weights | API test |
| TRD-19 | Any New trade task → **See the impact**, then leave without creating | Impact shown; no trade list, no ledger record, cashflows still New | `test_dry_run_previews_impact_without_saving` |
| TRD-20 | As an analyst open Trading | Opens on **New trade** with four task tiles; **Rebalance to a target** disabled ("Portfolio managers only"); a security preview saves nothing | `test_trd_20` |
| TRD-21 | PM: **Trade a security** in MTRS-2040: largest holding → **Trade to weight** +5pp, then −1pp → **See the impact** | +5pp shows **Not enough cash**; −1pp gives a SELL with the asset mix now vs after, target, glide path, Off target and compliance | `test_trd_21` |
| TRD-22 | PM: **Rebalance to a target** → **Back to the glide path** → MTRS-2070 → **See the impact** | Off target after ≤ before for the fund | `test_trd_22` |
| TRD-23 | **Start from your goal** → "Get back to the glide path", then "…stay as positioned last night" | Sets up Rebalance → Back to the glide path, then Invest cashflows → Keep the current mix | `test_trd_23` |
| TRD-26 | PM: redemption of $25m for MTRS-2060 → New trade → Invest cashflows → create the draft → **Tranches** → **Use a calculation** → *Sell 20% a day* → Apply to Fund MTRS-2060 → **Preview**, then **Apply and save** | Preview lists each order with 5 tranches and says nothing is saved; after applying: "Calculations used: Sell 20% a day v1", orders show "1 of 5"; a `trades.tranche_calc` record | `test_trd_26`, `test_calc_templates_governance_and_use_on_trade_list` |
| TRD-27 | Analyst: Routing & settings → **Calculation templates** → propose "Sell a third a day" (Equal tranches, 3) with a reason; then as Risk with the Approver permission approve it; then try approving your own new version | Proposed: "Not yet approved" and no Approve button for the analyst; Risk approves → "v1 · Sells: 3 equal tranches"; approving your own version is refused (segregation of duties); a retired template can't be used | `test_trd_27`, `test_calc_templates_governance_and_use_on_trade_list` |
| TRD-28 | Calculation results: liquidity cap of $25,000 a day on a $100,000 sell; a 10%-of-volume cap that would need more days than allowed; Thanksgiving week | 4 tranches none above the cap; the over-limit order stays whole with the reason; dates skip the holiday and weekends | `test_calc_templates_produce_schedules` |
| TRD-32 | PM: Trading → **Tilts** → Mutual funds → MTRS-2040: +0.5 on the first holding, −0.25 on the second; MTRS-2060: +0.3 → **Preview** → **Save** with a reason; then as an analyst | Counter "3 security tilts changed"; preview table of the 2 funds with tilt 0.00→+0.50 and the others funded pro rata (totals 100%); "Tilts saved: 3 set, 0 cleared across 2 funds"; values stay in the table; fund page shows the tilt; a tilt above 5%, or on a security outside the fund's universe, is refused; clearing a cell removes only that fund's own tilt; analyst sees it read-only | `test_trd_32_tilts_table`, `test_tilts_table_preview_save_and_clear`, `test_tilts_table_rules` |
| TRD-29 | Sell $1,050 of an ETF priced $100 (10.5 shares); buy $1,050 of it; sell exactly $1,000; then on Trade a security ask to sell more than the fund holds | The sell is 11 shares (rounded up, raising at least $1,050), the buy 10 shares (rounded down); exact amounts don't move; a sell is never more than is held, and an oversized amount is refused with "only … is held"; mutual funds and CITs keep fractional units | `test_etf_rounding_sells_up_buys_down` |
| TRD-33 | PM: Trading → **Tilts** → **Change (pp of fund)**: MTRS-2040 US equity `1`; Balance **Off**; back to within level; **Change (% of weight)**: MTRS-2050 emerging markets `10` → **Preview** | Rows are levels 1-5 (securities at L5); the Check cell shows ✓ 100%, then "net +1.00" with Balance Off; switching mode clears the table; preview shows MER-EM-MF up and developed down; **Save 2 tilt changes** | `test_trd_33_tilts_by_level` |
| ST-1 | PM: Trading → Funds & securities → **Management style**: MTRS-2040 Active, MTRT-2040 Hybrid, reason → Save; as an analyst; then Console → Home | "Management style saved for 2 funds"; the funds list shows the styles and who set them; analysts can't change them (403); Home's **Positioning: active funds** lists MTRS-2040 and not MTRT-2040; unset funds are flagged *not set* in the passive/hybrid table | `test_st_01_management_style_and_home_tables`, `test_fund_styles` |
| HP-1 | PM Home: **Positioning** tables and **By asset class** with **Show levels 1-3** | Per fund: Δ vs target for each asset group, tracking error, risk budget used in total and by asset group; by asset class: target, portfolio, difference, risk budget used, share of parent vs market (MSCI ACWI IMI, S&P DJI) with ratio; hover shows the source | `test_st_01_management_style_and_home_tables` |
| HP-2 | Prices workflow posts daily closes; PM Home → **Cumulative returns** | 1W, MTD, QTD, YTD, 1Y for each fund (labelled hypothetical) and each security held; proxies marked (e.g. *proxy VOO*); posting without the token is refused (401) | `test_st_01_management_style_and_home_tables`, `test_ingest_and_performance`, `test_parse_daily_and_period_returns` |
| TRD-34 | PM: Trading → **Security line-up** → IEFA → All mutual funds, 2050–2070 → 25% → **Preview** → **Save**; take out the only US large cap security; add a new security and pilot it in one CIT, take it out, include it again; exclude VNQ everywhere, then include it | Preview for 5 funds with International Developed Equity 100.0→75.0 for the index fund and IEFA 0→25; saved and shaded in the matrix; vintages not chosen and CITs unchanged; taking out an asset class's only security is refused; a taken-out security is target 0 and flagged for exit, and including it again restores its share; exclusions apply to every fund in scope; analysts are refused; the Glide path table links here | `test_trd_34_security_lineup`, `test_add_security_to_funds_and_vintages`, `test_take_out_exclude_include_and_new_security` |
| TRD-30 | Approve a CIT trade list and download its Charles River file; on the list click **View file**; then **Files** | The file opens in the app with the same rows as the download (header "External Order ID"); Files lists it as **Charles River import** with its fingerprint; after loading fills, a **Fills** file is listed too | `test_trd_30_31_files_and_in_progress`, `test_end_to_end_cashflows_to_charles_river_file` |
| TRD-31 | **In progress** before approving, after exporting and after a partial fill | The list moves from **Waiting for approval** to **Sent to Charles River** to **Partly filled** with its % filled; its orders are on the blotter and its date under **Coming up** | `test_trd_30_31_files_and_in_progress`, `test_end_to_end_cashflows_to_charles_river_file` |
| TRD-24 | Glide path & bulk changes → All mutual funds → **2050–2070**, then click 2060 off; then **Clear**; then pick one fund | 5 funds, then 4 funds; Clear shows "Pick at least one vintage"; one fund hides the vintage buttons | `test_trd_24`, `test_glide_path_scope_by_picked_vintages` |
| GP-1 | Console → **Glide path** → table (rows = asset levels 1-4, columns = vintages): 2030 cash `1` only (read the change under each cell and the **Net change** row, then switch **Under each cell**); then **Share of parent**: 2060 international equity `45`; **Preview**; then Balance **Off**, 2030 cash `1` alone → Preview, then core bond `-1`; then **New weight (%)**, **Each fund**, Balance within level: MTRS-2045 cash +4pp → Preview | 23 rows (header, 20 asset rows, Net change, Check), 7 when **Show levels 1**; one cell is enough: the Check row shows ✓ 100% (the rest of the level balances), cash shows +1.00, equity a negative change and **Net change ✓ 0.00** in each view; switching **Enter** clears the table; preview of 2 funds (MF and CIT 2060); with Balance Off the single entry shows "net +1.00" and Preview is refused ("Fix these first") until the other side is entered; the 4pp change shows FAIL and no Submit button | `test_gp_01_glide_path_table` |
| GP-7 | Glide path → **Glide path** picklist → a named path, then back to the IPS path | The chart redraws from the named path's anchors with the IPS equity as a dashed line, its description, largest gap to the IPS path and funds on it; the anchors table follows the selection | manual |

## REG — Regulations & obligations (Nina Alvarez, analyst; Robert Hayes, CCO) · built 2026-11-10 (doc 18)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| REG-1 | Regulations → Mutual funds → tick MTRS-2045 → ACT 40 → reason → Add | Tag shown; obligations created; fund detail lists ACT 40 controls (PASS) and unfilled required people | `test_reg_01` |
| REG-2 | As analyst, look for Remove; as CCO, remove a tag | No remove button for the analyst; CCO removes it and its open obligations are cancelled | `test_reg_01`, API test |
| REG-3 | Obligations → open Form N-CEN → Complete with evidence | Done; next year's obligation created; logged | `test_reg_01` |
| REG-4 | Tag a CIT with UCITS, then rebalance it | Trade list shows UCITS-55-SINGLE FAIL and approval is blocked | `test_reg_02` |
| REG-5 | Let an obligation pass its due date | Shown overdue; one exception case opened (console → Exceptions) | API test |
| REG-6 | Regulation library | US and international regulations with controls, obligations, roles, retention | `test_reg_01` |
| REG-7 | Compliance: tag MTRS-2065 with ACT 40; tick it; **Fiscal year end** → September 30 → reason → **Set for ticked funds** | "Fiscal year end updated for 1 funds"; the Fiscal year end column and fund detail show September 30; Form N-CEN becomes "FY to Sep 2026" due 2026-12-14 (or the current year if that report's due date has passed); the change log shows `fund.fiscal_year_end` | `test_reg_07`, `test_fiscal_year_end_moves_open_obligations` |
| REG-8 | After REG-7: complete Form N-CEN; tag the fund with UCITS; try the same fiscal year end again; try a PM | Next N-CEN is "FY to Sep 2027"; UCITS annual report on the September year; repeating says "Nothing changed"; a PM is refused; monthly and calendar-based obligations (N-PORT, CFTC 4.5) never move | `test_fiscal_year_end_moves_open_obligations`, `test_fiscal_year_schedules` |

## GP — Glide-path adjustments reach the agents (Elena Rossi, IC; agent run) · built 2026-11-18 (doc 02 §4b)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| GP-2 | IC approves a +1pp US large cap / −1pp core bond shift for All CITs 2050 and 2055; the agent-run workflow pulls `/api/export/policy-overrides` | The export carries `glide_adjustments` for 2050 and 2055 (CIT line only) | `test_export_carries_approved_adjustments_per_line` |
| GP-3 | Run the agents with an approved 2pp adjustment on 2050 | 2050's glide path moves 2pp; its proposal stays within 3pp of the IPS glide path for every asset class and passes compliance; one `glide-path.adjustments` record; Proposals → 2050 shows **Glide path adjusted**; the board memo lists the adjustment | `test_pipeline_builds_on_adjusted_glide_path` |
| GP-4 | Mutual fund and CIT adjustments differ for a vintage; PM + Risk approve that vintage's proposal | Run uses the average; Trading → MTRT fund page says the CIT line's own difference was added to the Approved proposal table, and the MTRS fund the opposite | `test_approved_table_adds_each_lines_own_difference` |
| GP-5 | IPS bands with an adjusted glide path | A 3.5pp tilt passes against the adjusted path but FAILs against the IPS glide path; the engine checks the IPS path | `test_policy_adjusted_neutral_and_band_check` |
| GP-6 | Submit a table changing two funds in different asset classes; IC approves once | One request ("Table of changes: 2 funds"); one approval; one adjustment per fund in force, each fund's glide path moves by its own row only; untouched funds unchanged | `test_glide_table_request_one_decision_many_funds`, `test_ux_07` |

## SIM — Simulations, exits across funds, management style, net changes (Priya Raman, analyst; Maya Chen, PM) · built 2026-11-20

| # | Step | Expected result | Auto test |
|---|---|---|---|
| SIM-1 | Analyst: **Simulations** → $100m, By assets → **Simulate**; then **Per vintage**, 100 in 2030 only → **Simulate**; open Trading → Trade lists | $100.0m in across every fund, each fund's share in proportion to its NAV, buys only; then 2 funds (MTRS-2030, MTRT-2030) split by assets; no trade list or cashflow saved; a redemption larger than a fund is refused | `test_sim_1_cashflow_simulation`, `test_simulate_by_assets_per_vintage_and_per_fund` |
| SIM-1a | PM: simulate $50m into MTRS-2040; exclude one security it bought; simulate again | The excluded security isn't bought the second time (tilts, exits and line-up apply the same way) | `test_simulation_applies_exits_and_exclusions` |
| SIM-2 | PM: New trade → **Exit a position** → All CITs, 2050–2070 → MER-EM-CIT → **See the impact** → create the draft | One row per CIT 2050-2070, none for mutual funds; "Flagged for exit when you save"; one `EX-` draft; the funds now show it as exiting; an analyst can then exit it for chosen vintages, but not a security nobody flagged | `test_sim_2_exit_across_funds`, `test_exit_across_funds` |
| SIM-3 | PM: Funds & vintages → **Set management styles** → MTRS-2040 Active, reason; Trading → MTRS-2045 page → style chip → Hybrid | Each saves from the dialog with a message and a ledger record; chips update in place | `test_sim_3_style_from_console_and_trading` |
| SIM-4 | PM: Glide path table, cash +1 in 2030 (pp); switch **Under each cell**; Balance off with one side; Tilts → +1 on one MTRS-2040 security → Preview | Cash shows +1.00, equity a negative change, **Net change ✓ 0.00** in every view; Balance off shows **⚠ +1.00**; the tilts preview shows **Change by asset class** with **✓ 0.00** | `test_gp_01_glide_path_table`, `test_sim_4_tilt_preview_nets_to_zero` |

## POL — Policy: IPS versions and named glide paths (Maya Chen, PM; Elena Rossi, IC; Robert Hayes, CCO) · built 2026-11-18 (doc 07)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| POL-1 | PM: Policy → **Propose a change**; change "At least annually" to "At least twice a year"; summary; "No" to engine rules; **Preview changes**; **Submit for approval** | Preview shows 1 changed line; version 2 **Waiting for approval** with the redline (green "twice a year"); version 1 stays **Current**; a second draft is refused while one waits | `test_pol_01`, `test_ips_versions_need_ic_and_cco` |
| POL-2 | The drafter (even with the IC permission) tries to approve; IC approves; the same person with both permissions tries the CCO approval; the CCO approves | Drafter refused; after IC "1 of 2 approvals"; same person refused; after the CCO, version 2 **Current** and version 1 **Superseded**; ledger `ips.propose`, `ips.approve` ×2, `ips.effective` | `test_pol_01`, `test_ips_versions_need_ic_and_cco` |
| POL-3 | Reject a draft as CCO; withdraw another as the drafter; try to withdraw someone else's | Rejected and withdrawn versions stay listed; only the drafter can withdraw; version 1 still current | `test_ips_reject_and_withdraw` |
| POL-4 | PM: Glide paths → **New glide path** "Higher equity at retirement" (+2pp US large cap, −2pp core bond at 0 years); a row that doesn't total 100; submit; IC approves | Total turns red until 100; the request shows the largest gap to the IPS path; the PM has no Approve button; after approval the path is **Active**, version 1 | `test_pol_03`, `test_clean_anchors_validation` |
| POL-5 | PM: tick MTRS-2030, choose the new path, **Request change**; IC approves; open Trading for that fund | MTRS-2030 follows the new path; its Neutral table, glide-path preview and IPS check use it; a new version of the path takes effect only when approved | `test_pol_03`, `test_named_path_flows_to_trading_bands_and_export` |
| POL-7 | PM: Console → **Glide path** → **+ New glide path**; Next with no name; the name "IPS glide path"; then "Through retirement 55" → From scratch → start reducing at 50 (more than the first row), then 25; equity 55% at the target and 35% at −7 → build; break a row; Check; fix; submit | Refused without a name and for an existing name; the shape is refused until "start reducing" is below the first row; 8 anchor rows (40, 25, 20, 15, 10, 5, 0, −7), each 100.0; a broken row shows "Fix these first" and can't be submitted; after the fix the summary shows equity 90% at 40 years; the request reaches the Investment Committee and the path shows **Waiting for approval** | `test_pol_07_guided_glide_path_builder` |
| POL-6 | Run the agents with a vintage on a named path 4pp above the IPS path | The run builds around the path; the IPS bands are checked around it (no FAIL); every asset within 3pp of the path; Proposals shows **Glide path changed** | `test_pipeline_centres_bands_on_named_path` |

## UX — App bar, My work, Help, messages and confirmations (any persona) · built 2026-11-11 (doc 11)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| UX-1 | Open the console, Trading, Regulations and (as admin) User access | The same app bar on every screen; only the screens your access allows; the current one underlined; no "Back to console" links; a **Read-only** label for view-only access | `test_ux_01`, `test_every_page_carries_the_shell_without_duplicate_links` |
| UX-2 | As a PM, create a draft on **New trade**, go to the console, open **My work** and click the trade list | Item "Approve TL-…" listed; Esc closes the list; clicking opens Trading → **Trade lists** with that list selected | `test_ux_02`, `test_my_work_lists_drafts_committee_requests_and_obligations` |
| UX-3 | Cancel that trade list: try a 5-character reason, then **Go back**, then cancel with a proper reason | In-page confirmation names the list; **Cancel trade list** stays disabled until the reason has 10 characters; Go back changes nothing; then "Trade list cancelled" | `test_ux_02` |
| UX-4 | Type in any reason field; click **Create draft trade list** with no reason | Counter shows "n/10 characters minimum"; the red error stays until you close it | `test_ux_03` |
| UX-5 | Keyboard only: Tab from the top of Trading, then use ← →, Home and End on the tab row | First Tab offers "Skip to main content"; arrows move between tabs; Home/End go to New trade / Routing & settings | `test_ux_03` |
| UX-6 | On Regulations click **? Help**, search "obligation", go back | Guide opens at §12; headings filter; back returns to Regulations | `test_ux_04`, `test_help_anchors_exist` |
| UX-7 | Let the session expire (or sign out in another tab), then act | "Your session has expired" with Sign in / Stay on page; Sign in goes to the sign-in page | `test_ux_04` |
| UX-8 | As a Compliance user with obligations due soon, open My work | Obligations due within 14 days or overdue for your role, red when overdue; click opens that obligation | API test |
| UX-10 | Signed out, open the app URL; click **Sign in**; sign in; then sign out | **Sign in to Meridian** page with the navy app bar and the brand's colours; the Cognito sign-in page has a navy banner, navy button and the app's grey background; signed-out page in the same style | `test_app_signin_pages_are_branded`, `test_cognito_css_for_every_theme_fits_cognitos_rules`; Cognito page by hand |
| UX-9 | PM Home: click the **i** next to **Tracking error**; Esc; the **i** on **Highest risk-budget use**; click elsewhere; Glide path → the **i** next to **Balance**; Trading → Funds & securities → **i** next to **Management** | Each opens a box with a plain explanation, and a "How it's calculated" formula where there is one (e.g. tracking error ÷ risk budget); Esc returns focus to the **i**; a click elsewhere closes it; header text unchanged | `test_ux_09_info_bubbles`, `test_glossary_entries_are_complete_and_labels_unique` |

---

## Findings log

| ID | Found | Severity | Finding | Status |
|---|---|---|---|---|
| F-1 | 2026-11-09, writing UAT-LEAD | Medium (latent) | Leadership and Compliance approve as `investment_committee` and `chief_compliance_officer`, but sign-in groups are `leadership` and `compliance`, so the hosted app refuses those approvals. Routine proposals only need PM + Risk, so it shows up only when a glide-path change or exception needs IC or CCO approval. | **Fixed** 2026-11-09: new per-user permissions `investment_committee` and `chief_compliance_officer` (switch on/off with manage-users `grant`/`revoke`); the approve form only appears for people who hold the authority |
| F-2 | 2026-11-09, automated ACC-3 | Medium | Changing the address to another workspace (`#pm`) switched an Audit-only user into that workspace's screens. The server already refused actions for roles the user doesn't hold. | **Fixed** 2026-11-09 (workspace switch now limited to the user's roles); covered by `test_access_03` |
| F-4 | 2026-11-10, round 1 (RISK-5) | Low | Look-through lists the same issuer under several names ("TREASURY NOTE", "(OLD)", "(2OLD)", "TBILL TREASURY BILL"), so exposure to one issuer is split across rows | **Fixed** 2026-11-10: one issuer, UNITED STATES TREASURY |
| F-5 | 2026-11-10, round 1 (MGR-3) | Medium | Underlying funds showed only the returns proxy (Vanguard ETFs) while look-through uses iShares holdings, with no explanation | **Fixed** 2026-11-10: both proxies shown and explained (`test_ovs_08`) |
| F-6 | 2026-11-10, round 1 (ADM-11) | Low | Workspace label "Leadership / IC" misleading now that Investment Committee is a separate permission | **Fixed**: label is "Leadership" |
| F-7 | 2026-11-10, round 1 (AUD-2) | Low | Ledger header read "verified verified" | **Fixed** |
| F-8 | 2026-11-10, round 1 (COMP-3) | Low | Compliance report quotes the ledger size at run time (118) while the live ledger has more (123), unexplained | **Fixed**: note above the report |
| F-9 | 2026-11-10, round 1 (COMP-4) | Medium | Human decisions are hard to find among system records; search limited to one run | **Fixed**: Search all runs with type, vintage, actor and date filters, CSV export |
| F-10 | 2026-11-10, automated OVS-5 | Medium | With 13 PM tabs, the bottom tabs fell off short screens with no way to scroll | **Fixed**: side bar scrolls |
| F-11 | 2026-11-10, round 1 (PM-4) | Low | Risk budget shows the proposal's tracking error, not the effect of a pending adjustment | **Fixed** 2026-11-10: "With adjustment" column on Risk budget |
| F-3 | 2026-11-09, design review | Low (informational) | Each run's page carries the full run data for every workspace; roles limit screens and actions, not data. Fine while every user may see the whole pilot; portfolio-level entitlements (doc 05 §7) would need server-side filtering. | Open — for the entitlements design |

## Results log (fill in per UAT round)

| Round | Date | Tester | Scripts | Pass / fail | Key feedback |
|---|---|---|---|---|---|
| 0 (automated) | 2026-11-09 | Browser tests | All | 34 pass, F-1 expected fail | Found F-1, F-2 |
| 0b (automated) | 2026-11-09 | Browser tests | All + permissions | 38 pass | F-1 fixed; placeholder CCO verified as still a blocker |
| 1 (manual, hosted) | 2026-11-10 | Claude, in Alex Eaton's signed-in session | PM-1–5, RISK-1–5 and 7, RES-1–3, MGR-1–3, LEAD-1–3 and 5, COMP-1–4, AUD-1–3, ADM-2, ADM-10–13 | All run steps passed. Not run: RISK-6 (needs a second person), ACC-1–3 and ADM-14–15 (need other logins; covered by automated tests) | Found F-4 to F-9, F-11. Approvals, one adjustment and a disabled test login (aeaton3252+uat@gmail.com) are in the live ledger and access log, all marked "UAT (run by Claude for Alex)" |
| 2 (automated) | 2026-11-10 | Browser + API tests | All + OVS | 99 pass | Found F-10; F-5 to F-10 fixed |
| 4 (automated) | 2026-11-10 | Browser + API tests | All + REG + TRD-14 to 16 | 125 pass | Regulations, rebalance, positions, fills; F-4 and F-11 fixed |
| 3 (automated) | 2026-11-10 | Browser + API tests | All + TRD-1 to TRD-13 | 115 pass (all) | Trading slice 1 and 2; route permission; no new findings. Guide screenshots generated from the same local app (`tests/e2e/guide_screenshots.py`) |
| 5 (automated) | 2026-11-11 | Browser + API tests | All + TRD + REG + UX | 135 pass (65 browser) | UX update: app bar, My work, Help, dialogs, messages, keyboard; tests updated for the grouped console tabs |
| 6 (automated) | 2026-11-13 | Browser + API tests | All + TRD-19 to TRD-23 | 154 pass (78 unit/API, 76 browser) | Trading redesign: New trade builder, goal shortcuts, dry-run impact, cash check; earlier trading and UX scripts moved to the new flow. Guide screenshots regenerated (75) from the same local app |
| 7 (automated) | 2026-11-13 | Browser + API tests | All + PM-6, ADM-18, TRD-24, TRD-25, GP-1 | 161 pass (82 unit/API, 79 browser) | Approver permission; vintage picker for glide-path and bulk changes; "Portfolios & proposals" renamed "Proposals"; screenshots regenerated |
| 8 (automated) | 2026-11-18 | Browser + API tests | All + TRD-26 to 28, REG-7, REG-8, GP-2 to GP-5 | 172 pass (90 unit/API, 82 browser) | Calculation templates; glide-path adjustments feed the agents; fiscal year ends. One fix found while testing: changing the calculation kind cleared the name typed so far (fixed). 5 new screenshots |
| 9 (automated) | 2026-11-18 | Browser + API tests | All + TRD-29 to 31, RISK-8, POL-1 to POL-6 | 188 pass (103 unit/API, 85 browser) | ETF rounding; trade files and trades in progress; SEC EDGAR financials and % of market cap; Policy screen. Fixes found while testing: the file viewer showed the row list in place of the row count; a slow first load of Glide paths could replace the page after a fund was ticked (stale renders are now dropped). 8 new screenshots |
| 10 (automated) | 2026-11-18 | Browser + API tests | All, in the Principal brand theme | 194 pass (109 unit/API, 85 browser) | Brand themes (`test_branding.py`: every theme passes the contrast check, every page carries the theme once); EDGAR gap filling across concepts and periods. All 89 screenshots regenerated |
| 11 (automated) | 2026-11-19 | Browser + API tests | All, revised Principal theme | 194 pass (109 unit/API, 85 browser) | Product-owner review: too much blue, readability. Theme revised (white and grey surfaces, navy actions, light only); contrast check widened to 28 text/background pairs. Screenshots regenerated |
| 12 (automated) | 2026-11-19 | Browser + API tests | All + GP-1 (rewritten), GP-6 | 195 pass (110 unit/API, 85 browser) | Glide-path changes typed into a table and previewed as a table (product-owner request); Trading's glide-path card links to it. Screenshots regenerated (pm-15 new; trd-18 retired) |
| 13 (automated) | 2026-11-19 | Browser + API tests | All + TRD-32 | 198 pass (112 unit/API, 86 browser) | Tilts table (product-owner request). 2 new screenshots |
| 14 (automated) | 2026-11-20 | Browser + API tests | All + GP-1 (rewritten), TRD-33, ST-1, HP-1, HP-2 | 207 pass (119 unit/API, 88 browser) | Product-owner feedback: glide-path and tilts tables on hierarchy levels 1-5 with absolute/relative entry and auto-balance; glide-path picklist; management style per fund; PM Home positioning and returns tables; daily prices workflow. Screenshots regenerated (pm-16 to pm-19, trd-37, trd-38 new) |
| 15 (automated) | 2026-11-20 | Browser + API tests | All + UX-9 | 211 pass (122 unit/API, 89 browser) | Info bubbles across the app (product-owner request): 87 glossary entries with simplified formulas. 1 new screenshot |
| 16 (automated) | 2026-11-20 | Browser + API tests | All + POL-7 | 212 pass (122 unit/API, 90 browser) | Guided glide-path builder (product-owner request) and a **+ New glide path** button on Console → Glide path. 5 new screenshots |
| 17 (automated) | 2026-11-20 | Browser + API tests | All + TRD-34 | 215 pass (124 unit/API, 91 browser) | Security line-up (level 5) across funds and vintages (product-owner request). 2 new screenshots |
| 18 (automated) | 2026-11-20 | Browser + API tests | All + UX-10 | 217 pass (126 unit/API, 91 browser) | Branded sign-in pages, including the Cognito sign-in page (product-owner request) |
| 19 (automated) | 2026-11-20 | Browser + API tests | All + SIM-1 to SIM-4, GP-1 (net change) | 224 pass (129 unit/API, 95 browser) | Product-owner feedback: Simulations page with cashflow simulation; exit a position across funds; management style from a dialog anywhere; changes in pp that net to zero on the glide-path and tilts tables. Fixes found while testing: two inputs on the simulation page shared an attribute with the vintage buttons (renamed); exit flags saved in a different shape from Routing & settings made a later settings save report exits as changed (same shape now). 5 new screenshots |
