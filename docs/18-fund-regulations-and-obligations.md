# 18 — Fund Regulations & Obligations

**Version 0.1 · 2026-11-10 · Status: built and live (Regulations screen, `/regulations`). Citations, limits and due dates are a design aid: the CCO and counsel must confirm them before production.**

## 1. What it does
Any fund or portfolio can be tagged with the regulations it is subject to, such as **ACT 40** (Investment Company Act of 1940), ERISA or UCITS. Domestic (US) and international (ex-US) regulations can be combined on the same fund. Tagging a fund switches on, for that fund only:

| Effect | How it works |
|---|---|
| **Controls** | Deterministic checks on the fund's holdings, shown on current holdings and run again on the post-trade holdings of every trade list, rebalance and ticket. A FAIL blocks approval; a WARN is shown |
| **Obligations** | Tasks with an owner role, period, due date, required evidence and citation (filings, board reports, reviews, calculations). Completing a recurring task creates the next one. Overdue tasks open an exception case once |
| **People required** | Roles the regulation needs (e.g. fund board, liquidity program administrator), shown as unfilled until named in `config/entity_profile.yaml` |
| **Record retention** | The fund's retention is the longest of its regulations' periods |

Firm-level operating-entity packs (doc 08) stay as they are; fund-level tags sit on top of them.

## 2. Regulation library (`regimes/fund_regulations.yaml`)
| Tag | Regulation | Scope | Controls | Obligations (examples) |
|---|---|---|---|---|
| ACT 40 | Investment Company Act of 1940, registered open-end fund | US | 12(d)(1)(A) unaffiliated funds 5% each / 10% total (or Rule 12d1-4 with fund-of-funds agreements); 22e-4 illiquid ≤15%; 18f-4 limited-user ≤10% derivatives; §5(b)(1) diversification | 38a-1 annual CCO report; N-PORT; N-CEN; shareholder report and N-CSR; monthly liquidity classification; annual liquidity report; 2a-5 valuation report; 15(c) contract approval; RIC diversification test; one-time board adoption |
| ERISA | ERISA plan assets (e.g. a CIT) | US | — | Form 5500 (DFE); 408(b)(2) disclosures; prohibited-transaction review; fiduciary review of the series; one-time exemption memo for affiliated funds |
| CIT (OCC 9.18) | Bank collective investment fund | US | — | Annual audit; quarterly valuation; annual report to participants; plan review |
| CFTC 4.5 | CFTC Rule 4.5 exclusion | US | Commodity-interest proxy ≤5% | Annual affirmation with NFA |
| UCITS | EU UCITS Directive | International | 20% in any one fund; 30% in non-UCITS funds; 5/10/40 issuer rule; derivatives global exposure | KID; annual and half-yearly reports; risk management process; daily global exposure |
| AIFMD | EU AIFMD | International | Leverage monitoring | Annex IV; annual report; liquidity stress test |
| UK COLL | UK UCITS / authorised fund (FCA) | International | 20% one scheme; 30% non-UCITS; issuer limits | Assessment of Value; Consumer Duty fair value; long reports |
| NI 81-102 | Canada investment fund | International | 10% single issuer; illiquid ≤10% | Fund Facts; MRFP; IRC report |
| SFC UT Code | Hong Kong SFC-authorised fund | International | 10% single issuer; non-eligible schemes | KFS review; annual and interim reports |

New regulations, controls and obligations are added in the YAML file and go through change control (pull request, tests). Every entry carries `counsel_review: required`.

**Suggestions:** mutual funds are suggested ACT 40; CITs are suggested ERISA and CIT (OCC 9.18). Suggestions are shown, never applied automatically.

**Notes on current rules (checked 2026-11-10):** the 2024 Form N-PORT amendments (monthly filing within 30 days) were deferred to 2027-11-17 for large fund groups, and a February 2026 SEC proposal would move the deadline to 45 days and restore quarterly publication. The library therefore keeps today's schedule with a note for counsel. UCITS fund-of-funds limits used are 20% per fund and 30% in non-UCITS funds.

## 3. Who can do what
| Action | Who |
|---|---|
| See the Regulations screen | Compliance, Audit, Admin, Leadership, PM, Risk, Analyst |
| Add a regulation to funds (adds controls) | Compliance, with a reason |
| Remove a regulation (lowers controls) | **Chief Compliance Officer permission** only, with a reason; open obligations are cancelled |
| Assign, start, note and complete obligations | Compliance, Risk, Leadership, PM; completion needs evidence (≥ 10 characters) |
| Waive an obligation | Chief Compliance Officer permission only |

Every step is a governance ledger record (`dr_type` "regulation": `regulation.tag`, `regulation.remove`, `obligation.assign|start|note|complete|waive`). Escalations appear in the console's Exceptions tab with source "obligation".

## 4. How controls reach trading
`_compliance` in the Trading API runs the IPS rules and then every control of every regulation tagged on the fund against post-trade weights. Each trade list shows the IPS result and the regulation result separately, and lists each failing control with its measured value and limit. Instrument attributes used: `affiliated` (Meridian funds), `ucits` (none today), `government`, `liquidity`, `issuer` (defaults in `config/trading.yaml`).

## 5. Open points for the CCO and counsel
1. Confirm each regulation's controls, citations, due dates and owners before production.
2. Fiscal year ends: annual and semiannual obligations use calendar periods today; per-fund fiscal year ends can be added.
3. Whether the target-date CITs need ERISA, the OCC rule, or both (and whether `bank_cit` applies at firm level).
4. Whether any fund will rely on Rule 12d1-4 (set per fund when tagging ACT 40).
