"""Agentic Compliance Officer (ACO).

Plays the compliance-analyst role for a solo builder: reviews every run against the selected entity
regimes, checks the deterministic rule results, verifies ledger integrity, lists open attestations and
production blockers, and drafts the compliance attestation.

It CANNOT be the Chief Compliance Officer. Advisers Act Rule 206(4)-7 and ICA Rule 38a-1 require a
designated person; FINRA requires registered principals. The ACO therefore never signs, never clears a
FAIL, and marks every attestation DRAFT until a human role-holder signs it.
"""
from __future__ import annotations

from ..agents import LLMBackend, actor, load_agent
from ..ledger import Ledger, verify


def review(run_id: str, regime, vintages: dict, synthetic: bool, ledger: Ledger, policy) -> dict:
    spec = load_agent("compliance-officer", ["compliance-review"])
    llm = LLMBackend()
    fails, warns, attest = [], [], set()
    for v, d in vintages.items():
        for r in d["compliance"]:
            if r["status"] == "FAIL":
                fails.append({"vintage": v, **r})
            elif r["status"] == "WARN":
                warns.append({"vintage": v, **r})
            elif r["status"] == "ATTEST":
                attest.add((r["rule_id"], r["detail"]))
    ok, chain_msg = verify(ledger.path)
    findings = []
    if synthetic:
        findings.append("Run used SYNTHETIC data. Outputs are for system testing only; they are not investment "
                        "advice and may not be used in marketing (hypothetical performance).")
    findings += [f"Production blocker: {b}" for b in regime.production_blockers]
    if fails:
        findings.append(f"{len(fails)} hard-limit FAIL(s) — proposals blocked from approval.")
    if warns:
        findings.append(f"{len(warns)} warning(s) to be acknowledged by approvers.")
    if attest:
        findings.append(f"{len(attest)} attestation(s) require a named human: " + ", ".join(sorted(a for a, _ in attest)))
    if not ok:
        findings.append("LEDGER INTEGRITY FAILURE: " + chain_msg)

    narrative = None
    j = llm.judge(spec, "Write a concise compliance review narrative for this run. Do not change any rule result.",
                  {"findings": findings, "fails": fails, "warns": warns, "obligations": regime.obligations},
                  '{"narrative": str, "recommended_actions": [str]}')
    if j:
        narrative = j.get("narrative")
    status = "BLOCKED" if (fails or not ok) else ("CONDITIONAL" if (attest or warns or regime.production_blockers) else "CLEAR")

    lines = [f"# Compliance Review — {run_id}", "",
             "**Prepared by:** Agentic Compliance Officer (ACO) — AI agent. **Status: DRAFT.** "
             "Not an attestation by a Chief Compliance Officer.", "",
             f"**Overall status:** {status}", f"**Ledger integrity:** {'OK' if ok else 'FAILED'} — {chain_msg}", "",
             "## Entity regimes in force", ""]
    lines += [f"- `{s}`" for s in regime.selected]
    lines += ["", f"Record retention applied: **{regime.retention_years} years** (strictest selected regime).", "",
              "## Obligations mapped", "", "| ID | Citation | Requirement | Regime |", "|---|---|---|---|"]
    lines += [f"| {o['id']} | {o['cite']} | {o['summary']} | {o['regime']} |" for o in regime.obligations]
    lines += ["", "## Findings", ""] + [f"- {f}" for f in findings or ["None."]]
    if narrative:
        lines += ["", "## ACO narrative (LLM)", "", narrative]
    lines += ["", "## Rule results by vintage", "", "| Vintage | PASS | WARN | FAIL | ATTEST | OFF |", "|---|---|---|---|---|---|"]
    for v, d in vintages.items():
        s = d["compliance_summary"]
        lines.append(f"| {v} | {s['PASS']} | {s['WARN']} | {s['FAIL']} | {s['ATTEST']} | {s['OFF']} |")
    lines += ["", "## Attestations awaiting a human", ""] + [f"- **{a}** — {t}" for a, t in sorted(attest)] + ["",
              "## Sign-off", "", "| Role | Name | Decision | Date |", "|---|---|---|---|"]
    for role in regime.required_roles:
        lines.append(f"| {role} | {regime.human_roles.get(role) or '— unfilled —'} | pending | |")
    report = "\n".join(lines) + "\n"

    ledger.record(dr_type="decision", run_id=run_id, step="compliance-officer.review", actor=actor(spec, llm),
                  policy_version=policy.id, summary=f"ACO review: {status}; {len(fails)} FAIL, {len(warns)} WARN, {len(attest)} attestations",
                  output={"status": status, "findings": findings}, rationale=narrative or "Deterministic review.")
    return {"status": status, "findings": findings, "fails": fails, "warns": warns,
            "attestations_pending": sorted(a for a, _ in attest), "ledger_ok": ok, "report_md": report}
