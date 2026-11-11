# 08 — Operating-Entity Profiles (select one or many)

**Version 0.2 · 2026-11-10**

Meridian can be run by an SEC-registered adviser, a broker-dealer, an adviser to 1940 Act funds, a private fund adviser, an ERISA fiduciary, a bank sponsoring a CIT, an asset owner/OCIO, or several at once. You don't need different builds. You choose one or more **entity types** and the system reconfigures itself.

## How to select
```bash
meridian entities list                        # show available packs
meridian entities set sec_ria registered_fund erisa_plan cftc_derivatives
meridian entities show                        # see the merged result
```
Or edit `config/entity_profile.yaml` → `selected_entities`. A per-run override is also possible: `meridian run target-date --entities bank_cit erisa_plan`.

## What changes automatically
| Dimension | Merge rule | Example |
|---|---|---|
| Regulatory obligations | Union | Registered fund adds 38a-1, 12(d)(1), 18f-4, 22e-4, 2a-5 |
| Compliance rules switched on | Union of patterns + rule-level `applies_to_regimes` | `DERIV-LDU` only when registered_fund or cftc_derivatives |
| Record retention | Maximum | RIA 5y + BD 6y → 6y |
| Required human roles | Union; production blocked while any is unfilled | Registered fund needs a derivatives risk manager and a liquidity program administrator |
| Approval chain | Strictest | Broker-dealer adds a registered principal to material rebalances |
| Required reports | Union | Board CCO report, Form PF inputs, plan committee report |
| Board memo / compliance report | Lists the regimes in force and obligations mapped | |

## Packs (v0.1)
`sec_ria` · `broker_dealer` · `registered_fund` · `private_fund` · `erisa_plan` · `bank_cit` · `pension_endowment_ocio` · `cftc_derivatives` (add-on). Definitions: `regimes/regimes.yaml`.

Every pack carries `counsel_review: required`. The citations are a design aid. A qualified human compliance officer or counsel must confirm them before production use.

## Pilot selection and the CIT product line (2026-11-10)
Selected today: `sec_ria`, `registered_fund`, `erisa_plan`, `cftc_derivatives`. Since the pilot now has target-date **CITs** next to the mutual funds (doc 17), the `bank_cit` pack (trustee bank, OCC/state bank rules, ERISA plan-asset rules for the trust) is likely needed too. Selecting it is a compliance decision for the CCO and counsel; it is not switched on.
