# Compliance Review — run_tds_20261031_872785

**Prepared by:** Agentic Compliance Officer (ACO) — AI agent. **Status: DRAFT.** Not an attestation by a Chief Compliance Officer.

**Overall status:** CONDITIONAL
**Ledger integrity:** OK — verified 118 records; head ca4503dbc4fd

## Entity regimes in force

- `sec_ria`
- `registered_fund`
- `erisa_plan`
- `cftc_derivatives`

Record retention applied: **6 years** (strictest selected regime).

## Obligations mapped

| ID | Citation | Requirement | Regime |
|---|---|---|---|
| IA-FID | Advisers Act §206; SEC 2019 fiduciary interpretation | Duty of care and loyalty; best interest; full and fair disclosure of conflicts | sec_ria |
| IA-CP | Rule 206(4)-7 | Written compliance policies and procedures, annual review, designated CCO (a natural person) | sec_ria |
| IA-REC | Rule 204-2 | Books and records, including records supporting recommendations and performance | sec_ria |
| IA-MKT | Rule 206(4)-1 | Marketing rule; hypothetical performance (backtests) restricted and disclosed | sec_ria |
| IA-ADV | Form ADV Part 2A | Disclose methods of analysis incl. use of AI/agents and material risks | sec_ria |
| IA-COE | Rule 204A-1 | Code of ethics; personal trading | sec_ria |
| SP-PRIV | Regulation S-P (2024 amendments) | Safeguards, incident response, customer notification, service-provider oversight | sec_ria |
| IC-CP | Rule 38a-1 | Fund compliance program; board-approved; CCO reports to board | registered_fund |
| IC-DIV | ICA §5(b)(1) | Diversified fund 75-5-10 test (look-through not applied to funds held) | registered_fund |
| IC-FOF | ICA §12(d)(1); Rule 12d1-4 | Fund-of-funds acquisition limits / conditions | registered_fund |
| IC-DERIV | Rule 18f-4 | Derivatives program & VaR limit, or limited-derivatives-user exception (≤10% derivatives exposure) | registered_fund |
| IC-LIQ | Rule 22e-4 | Liquidity risk management program; 15% illiquid cap | registered_fund |
| IC-VAL | Rule 2a-5 | Fair value determinations | registered_fund |
| IC-NAME | Rule 35d-1 (names rule) | 80% policy if name suggests a focus | registered_fund |
| ER-PRUD | ERISA §404(a) | Prudence and loyalty; documented process | erisa_plan |
| ER-PT | ERISA §406 / PTEs | Prohibited transactions incl. affiliated-fund use | erisa_plan |
| ER-QDIA | 29 CFR 2550.404c-5 | QDIA conditions for target-date funds used as default | erisa_plan |
| ER-FEE | ERISA §408(b)(2) / 404a-5 | Fee disclosure | erisa_plan |
| CF-CPO | CEA; CFTC Rules 4.5 / 4.13(a)(3) | CPO/CTA registration or exclusion/exemption analysis | cftc_derivatives |

## Findings

- Run used SYNTHETIC data for: fundamentals.valuation (mode=merge; synthetic_rows=5/5; synthetic_assets=['emerging_eq', 'global_reits', 'intl_developed_eq', 'us_large_cap', 'us_small_mid_cap']). Outputs are for system testing only; they are not investment advice and may not be used in marketing (hypothetical performance).
- Public data sources in use carry non-commercial or series-level terms (see config/data_sources.yaml → license_review); licensed data is required before production.
- Production blocker: Required human role unfilled: chief_compliance_officer
- Production blocker: Required human role unfilled: derivatives_risk_manager
- Production blocker: Required human role unfilled: liquidity_program_administrator
- Production blocker: Required human role unfilled: fund_board
- Production blocker: Required human role unfilled: plan_fiduciary_committee
- Production blocker: Regime pack needs counsel/CCO review: sec_ria
- Production blocker: Regime pack needs counsel/CCO review: registered_fund
- Production blocker: Regime pack needs counsel/CCO review: erisa_plan
- Production blocker: Regime pack needs counsel/CCO review: cftc_derivatives
- 3 attestation(s) require a named human: CONF-AFFILIATE-DISCLOSE, ERISA-AFFILIATE-PT, FOF-12D1

## Rule results by vintage

| Vintage | PASS | WARN | FAIL | ATTEST | OFF |
|---|---|---|---|---|---|
| 2030 | 16 | 0 | 0 | 3 | 0 |
| 2035 | 16 | 0 | 0 | 3 | 0 |
| 2040 | 16 | 0 | 0 | 3 | 0 |
| 2045 | 16 | 0 | 0 | 3 | 0 |
| 2050 | 16 | 0 | 0 | 3 | 0 |
| 2055 | 16 | 0 | 0 | 3 | 0 |
| 2060 | 16 | 0 | 0 | 3 | 0 |
| 2065 | 16 | 0 | 0 | 3 | 0 |
| 2070 | 16 | 0 | 0 | 3 | 0 |

## Attestations awaiting a human

- **CONF-AFFILIATE-DISCLOSE** — Conflicts from affiliated underlying funds disclosed in Form ADV / offering documents — awaiting human attestation
- **ERISA-AFFILIATE-PT** — Use of affiliated underlying funds covered by applicable PTE or fee offset; reviewed by plan fiduciary — awaiting human attestation
- **FOF-12D1** — Underlying funds acquired in reliance on Rule 12d1-4 / affiliated-fund exemption; conditions documented — awaiting human attestation

## Sign-off

| Role | Name | Decision | Date |
|---|---|---|---|
| chief_compliance_officer | — unfilled — | pending | |
| portfolio_manager | Product owner (named in the hosted app) | pending | |
| derivatives_risk_manager | — unfilled — | pending | |
| liquidity_program_administrator | — unfilled — | pending | |
| fund_board | — unfilled — | pending | |
| plan_fiduciary_committee | — unfilled — | pending | |
