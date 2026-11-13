# 16 — User Acceptance Test (UAT) Scripts

**Version 0.6 · 2026-11-13 · Phase 3 exit criterion: each persona completes their top three tasks (doc 03).**

One script per role, built from the personas (doc 15). Each step has an expected result and the ID of the automated browser test that checks the same thing. People run the scripts to judge whether the tool is *useful*. The automated tests check, on every request, that it still *works*.

## How to run

**By hand (hosted app).** Sign in at https://d3maw6l4k5cc0v.cloudfront.net with the account for the role (doc 14 §5). Mark each step Pass / Fail / Comment. Record anything confusing, slow or missing, even when the step passes: that feedback is the main output of UAT.

| Test account | Roles | Use for |
|---|---|---|
| Alex Eaton (full access) | All eight | PM, Research, Manager Selection, Leadership scripts (switch workspace in the side bar) |
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
| PM-1 | Sign in with only the PM role | Workspace selector shows Portfolio Manager only; tabs: Home, Funds & vintages, Positioning, Portfolios & proposals, Fund risk, Risk budget, Metrics, Look-through & search, Glide path, Approvals, Agent votes, grouped under Overview, Portfolio, Risk and Governance; your name in the app bar | `test_pm_01` |
| PM-2 | Portfolios & proposals → 2040 → Approve without ticking the box, then with a 9-character reason | Blocked each time with a clear message (tick the box; reason ≥ 10 characters) | `test_pm_02` |
| PM-3 | Portfolios & proposals → 2050: read *Why this proposal?*, *What would make this wrong*, *Dissent*, *Compliance*; tick, give a reason, Approve | "Decision recorded in the ledger"; Approvals tab shows 2050 / portfolio_manager / approve | `test_pm_03` |
| PM-4 | Positioning → 2045 → Adjust: Fixed Income short-dated +1pp funded from long-dated; reason; submit | Toast shows new TE, % of budget and compliance status; adjustment recorded | `test_pm_04` |
| PM-5 | Explain the largest change for 2050 using the active-weights chart and the ensemble rationale | You can state the biggest over/underweight and the reason in one sentence | `test_pm_05` (content present) |

**Usefulness questions:** Could you approve with confidence from this screen alone? What did you have to look for elsewhere?

## RISK — Risk Analytics (Daniel Okafor)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| RISK-1 | Sign in with the Risk role | Tabs: Home, Fund risk, Factor risk, Stress tests, Risk history, Look-through & search, Risk budget, Metrics, Candidate risk, Positioning, Portfolios & proposals, Approvals | `test_risk_01` |
| RISK-2 | Fund risk: scan all vintages | Every vintage 2030–2070 with total risk, effective duration, credit spread duration, VaR, diversification | `test_risk_02` |
| RISK-3 | Risk budget: find the vintage closest to its tracking-error budget | Percent of budget used shown for every vintage; you can name the closest and why (Fund risk drill-down) | `test_risk_03` |
| RISK-4 | Stress tests → Build a scenario: equities −20%, Treasury yields +100bp | Loss per vintage updates instantly; historical replays (e.g., global financial crisis) listed above | `test_risk_04` |
| RISK-5 | Look-through & search: "Treasury" | Every vintage's exposure and the underlying funds it comes through | `test_risk_05` |
| RISK-6 | After a PM approves 2055, co-approve it as Risk | "Decision recorded"; positions for 2055 become *approved* | `test_risk_06` |
| RISK-7 | Segregation of duties: one person with PM and Risk approves 2060 as PM, then tries again as Risk | Second decision refused: "Segregation of duties" | `test_risk_07` |

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
| OVS-1 | PM → Portfolios & proposals → 2050 → **Why?** | Panel lists the records behind the proposal (CIO ensemble, risk report, votes, approvals, adjustments) and the inputs shared by the run; Esc closes it | `test_ovs_01` |
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

**Usefulness questions:** Does pro rata by each table match how the desk allocates today? Does the impact view (now vs after, off target, gaps) answer "what will this do to the fund?" before you save? Do the goal shortcuts match how you think about a trade? Is the Charles River file missing any field your import needs? Is the ETF buffer applied the way you meant (§0 of doc 17)?

| TRD-14 | PM: **New trade** → **Rebalance to a target** → **Back to the glide path**, one fund → **See the impact** → reason → create → approve → export → **Mark all open orders filled** | `RB-…` list; fills booked; list *Filled and booked*; fund's Positions column shows "Booked from …" | `test_trd_14` |
| TRD-15 | PM: Funds & securities → upload a positions CSV (one bad security, then a good file) | Refused naming the row; then loaded and shown as "Uploaded file" | `test_approved_table_rebalance_positions_and_fills` |
| TRD-17 | PM: Glide path & bulk changes → All CITs → shift US large cap +1pp from core bond → Preview → Submit; then as an IC member approve | Preview within IPS bands for 9 funds; request pending; requester can't approve; IC approval puts it in force and the funds show *Glide path adjusted* | `test_trd_17`, `test_bulk_scopes_glide_path_and_strategic` |
| TRD-18 | PM: All mutual funds → asset-class tilt EM +25 bp; then a 4pp glide-path shift | Tilt applied to 9 funds; 4pp refused ("needs an IPS amendment") | `test_trd_17`, API test |
| TRD-16 | Rebalance to **Approved proposal** before and after PM + Risk approve a vintage | Refused ("no approved proposal"), then the list follows the approved weights | API test |
| TRD-19 | Any New trade task → **See the impact**, then leave without creating | Impact shown; no trade list, no ledger record, cashflows still New | `test_dry_run_previews_impact_without_saving` |
| TRD-20 | As an analyst open Trading | Opens on **New trade** with four task tiles; **Rebalance to a target** disabled ("Portfolio managers only"); a security preview saves nothing | `test_trd_20` |
| TRD-21 | PM: **Trade a security** in MTRS-2040: largest holding → **Trade to weight** +5pp, then −1pp → **See the impact** | +5pp shows **Not enough cash**; −1pp gives a SELL with the asset mix now vs after, target, glide path, Off target and compliance | `test_trd_21` |
| TRD-22 | PM: **Rebalance to a target** → **Back to the glide path** → MTRS-2070 → **See the impact** | Off target after ≤ before for the fund | `test_trd_22` |
| TRD-23 | **Start from your goal** → "Get back to the glide path", then "…stay as positioned last night" | Sets up Rebalance → Back to the glide path, then Invest cashflows → Keep the current mix | `test_trd_23` |

## REG — Regulations & obligations (Nina Alvarez, analyst; Robert Hayes, CCO) · built 2026-11-10 (doc 18)

| # | Step | Expected result | Auto test |
|---|---|---|---|
| REG-1 | Regulations → Mutual funds → tick MTRS-2045 → ACT 40 → reason → Add | Tag shown; obligations created; fund detail lists ACT 40 controls (PASS) and unfilled required people | `test_reg_01` |
| REG-2 | As analyst, look for Remove; as CCO, remove a tag | No remove button for the analyst; CCO removes it and its open obligations are cancelled | `test_reg_01`, API test |
| REG-3 | Obligations → open Form N-CEN → Complete with evidence | Done; next year's obligation created; logged | `test_reg_01` |
| REG-4 | Tag a CIT with UCITS, then rebalance it | Trade list shows UCITS-55-SINGLE FAIL and approval is blocked | `test_reg_02` |
| REG-5 | Let an obligation pass its due date | Shown overdue; one exception case opened (console → Exceptions) | API test |
| REG-6 | Regulation library | US and international regulations with controls, obligations, roles, retention | `test_reg_01` |

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
