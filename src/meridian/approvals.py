"""Human approval decisions -> immutable ledger records.

Rules enforced in code: a reason is mandatory; the role must be one the proposal requires; a proposal
with any hard-limit FAIL cannot be approved; each role decides once per vintage per run.
"""
from __future__ import annotations

import json
from pathlib import Path

from .ledger import Ledger


def record_decision(run_dir: Path, vintage: int, role: str, name: str, decision: str, reason: str) -> str:
    run_dir = Path(run_dir)
    res = json.loads((run_dir / "results.json").read_text())
    v = res["vintages"].get(str(vintage))
    if v is None:
        raise SystemExit(f"Vintage {vintage} not in run")
    adj = v.get("adjusted")
    if adj:  # an adjusted proposal supersedes the agents' proposal
        v = {**v, "approvers": sorted(set(v["approvers"]) | set(adj["approvers"])), "compliance_summary": adj["compliance_summary"]}
    if role not in v["approvers"]:
        raise SystemExit(f"Role '{role}' is not an approver for {vintage}; required: {v['approvers']}")
    if len(reason.strip()) < 10:
        raise SystemExit("A reason of at least 10 characters is required (SUP-2).")
    if decision == "approve" and v["compliance_summary"]["FAIL"]:
        raise SystemExit("Blocked: proposal has hard-limit FAILs and cannot be approved.")
    L = Ledger(run_dir / "ledger.jsonl")
    from .policy import load_policy
    sod = load_policy().raw.get("controls", {}).get("segregation_of_duties", True)
    for r in L.records():
        if sod and r["dr_type"] == "approval" and r["step"] == "approval.decision" \
                and f"MTRS-{vintage}" in r["portfolio_scope"] and r["actor"].get("id") == name and r["approvals"][0]["role"] != role:
            raise SystemExit(f"Segregation of duties: {name} already decided on {vintage} as {r['approvals'][0]['role']}; "
                             f"a different person must approve as {role}.")
        if r["dr_type"] == "approval" and r["step"] == "approval.decision" and f"MTRS-{vintage}" in r["portfolio_scope"] \
                and r["approvals"] and r["approvals"][0]["role"] == role:
            raise SystemExit(f"{role} already decided on {vintage} ({r['dr_id']}).")
    cio = next(r for r in L.records() if r["step"] == "cio.ensemble" and f"MTRS-{vintage}" in r["portfolio_scope"])
    if adj:
        cio = next(r for r in L.records() if r["dr_id"] == adj["dr_id"])
    return L.record(dr_type="approval", run_id=res["run_id"], step="approval.decision",
                    actor={"kind": "human", "id": name, "role": role}, inputs=[cio["dr_id"]],
                    portfolio_scope=[f"MTRS-{vintage}"], policy_version=cio["policy_version"],
                    summary=f"{vintage}: {decision} by {name} ({role})", rationale=reason,
                    approvals=[{"role": role, "name": name, "decision": decision}])
