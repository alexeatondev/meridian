# 09 — Agentic Compliance Officer (ACO)

**Version 0.1 · 2026-11-06**

## Why it exists
Meridian is being built by a solo product owner with no compliance staff. The ACO plays the compliance-analyst role on every run so the compliance function exists in the product from day one.

## What it can never be
The ACO **cannot be the Chief Compliance Officer**. The Advisers Act compliance rule (206(4)-7) and the fund compliance rule (38a-1) require a designated CCO, and FINRA supervision requires registered principals. Those are accountable people. So the ACO:
- marks everything it writes **DRAFT**;
- never clears, waives or overrides a FAIL from the deterministic rule engine;
- never edits policy, rules or the ledger;
- lists every required human role as a **production blocker** until a named person fills it (`config/entity_profile.yaml → human_roles`).

## What it does on every run
1. Resolves the selected entity regimes and maps the obligations.
2. Reads every rule result by vintage (PASS / WARN / FAIL / ATTEST / OFF).
3. Verifies the ledger hash chain.
4. Flags synthetic data, pending attestations, warnings and unfilled roles.
5. Writes `compliance_report.md`, with a sign-off table for the human role-holders, and records its review in the ledger.

When an LLM is configured, it also writes a narrative. The rule results stay deterministic either way.

## Path to production
Before real money: appoint a human CCO (an outsourced/fractional CCO is common for small advisers). The CCO reviews regimes, the IPS and the controls in doc 04, and then signs the attestations.
