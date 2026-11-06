"""Change requests for standing settings (risk budgets) and the positions history store.

Change requests: a requester proposes, the roles in policy approvals.<kind> approve (requester cannot approve
their own request), and only then is the change applied to the policy file. Every step is written to the
hash-chained governance ledger (data/governance/ledger.jsonl).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from ruamel.yaml import YAML

from . import REPO_ROOT
from .ledger import Ledger
from .policy import POLICY_PATH, load_policy

GOV_DIR = REPO_ROOT / "data" / "governance"
POSITIONS_PATH = REPO_ROOT / "data" / "positions" / "history.csv"
SYSTEM = {"kind": "system", "id": "governance", "version": "0.1.0"}


def _ledger(gov_dir: Path) -> Ledger:
    return Ledger(gov_dir / "ledger.jsonl")


def _requests(gov_dir: Path) -> dict:
    p = gov_dir / "change_requests.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _save_requests(gov_dir: Path, reqs: dict) -> None:
    gov_dir.mkdir(parents=True, exist_ok=True)
    (gov_dir / "change_requests.json").write_text(json.dumps(reqs, indent=2))


def list_requests(gov_dir: Path = GOV_DIR, status: str | None = None) -> list[dict]:
    return [r for r in _requests(gov_dir).values() if status in (None, r["status"])]


def request_risk_budget_change(vintage: int | str, new_budget: float, name: str, role: str, reason: str,
                               gov_dir: Path = GOV_DIR, policy_path: Path = POLICY_PATH) -> dict:
    pol = load_policy(policy_path)
    hard = float(pol.raw["risk_budgets"]["hard_max"])
    if new_budget <= 0 or new_budget > hard + 1e-12:
        raise SystemExit(f"Budget must be > 0 and ≤ the IPS hard limit {hard:.2%}; raising it needs an IPS amendment.")
    if len(reason.strip()) < 10:
        raise SystemExit("A reason of at least 10 characters is required.")
    key = "default" if str(vintage) == "default" else int(vintage)
    current = pol.raw["risk_budgets"]["default"] if key == "default" else pol.risk_budget(key)
    cr = {"id": "cr_" + uuid.uuid4().hex[:10], "kind": "risk_budget_change", "status": "pending",
          "target": {"vintage": key}, "current": current, "proposed": new_budget,
          "requested_by": {"name": name, "role": role}, "reason": reason,
          "required_approvals": pol.raw["approvals"]["risk_budget_change"], "approvals": [],
          "created_at": datetime.now(timezone.utc).isoformat(), "policy_version": pol.id}
    reqs = _requests(gov_dir)
    reqs[cr["id"]] = cr
    _save_requests(gov_dir, reqs)
    _ledger(gov_dir).record(dr_type="policy_change", run_id="governance", step="change_request.created",
                            actor={"kind": "human", "id": name, "role": role}, policy_version=pol.id,
                            summary=f"{cr['id']}: risk budget {key} {current:.2%} → {new_budget:.2%} (pending)",
                            rationale=reason, output=cr)
    return cr


def approve_change(cr_id: str, name: str, role: str, decision: str, reason: str,
                   gov_dir: Path = GOV_DIR, policy_path: Path = POLICY_PATH) -> dict:
    reqs = _requests(gov_dir)
    cr = reqs.get(cr_id)
    if not cr:
        raise SystemExit(f"No change request {cr_id}")
    if cr["status"] != "pending":
        raise SystemExit(f"{cr_id} is already {cr['status']}")
    if name == cr["requested_by"]["name"]:
        raise SystemExit("Segregation of duties: the requester cannot approve their own change request.")
    if role not in cr["required_approvals"]:
        raise SystemExit(f"Role '{role}' is not an approver; required: {cr['required_approvals']}")
    if any(a["role"] == role for a in cr["approvals"]):
        raise SystemExit(f"{role} already decided on {cr_id}")
    if len(reason.strip()) < 10:
        raise SystemExit("A reason of at least 10 characters is required.")
    cr["approvals"].append({"role": role, "name": name, "decision": decision, "reason": reason,
                            "at": datetime.now(timezone.utc).isoformat()})
    L = _ledger(gov_dir)
    L.record(dr_type="approval", run_id="governance", step="change_request.decision",
             actor={"kind": "human", "id": name, "role": role}, summary=f"{cr_id}: {decision} by {name} ({role})",
             rationale=reason, approvals=[cr["approvals"][-1]])
    if decision == "reject":
        cr["status"] = "rejected"
    elif {a["role"] for a in cr["approvals"] if a["decision"] == "approve"} >= set(cr["required_approvals"]):
        _apply(cr, policy_path)
        cr["status"] = "applied"
        L.record(dr_type="policy_change", run_id="governance", step="change_request.applied", actor=SYSTEM,
                 summary=f"{cr_id} applied: risk budget {cr['target']['vintage']} = {cr['proposed']:.2%}", output=cr)
    reqs[cr_id] = cr
    _save_requests(gov_dir, reqs)
    return cr


def _apply(cr: dict, policy_path: Path) -> None:
    y = YAML()
    y.preserve_quotes = True
    doc = y.load(policy_path.read_text())
    v = cr["target"]["vintage"]
    if v == "default":
        doc["risk_budgets"]["default"] = cr["proposed"]
    else:
        if doc["risk_budgets"].get("vintages") is None:
            doc["risk_budgets"]["vintages"] = {}
        doc["risk_budgets"]["vintages"][int(v)] = cr["proposed"]
    with open(policy_path, "w") as f:
        y.dump(doc, f)


# ------------------------------------------------------------------------------------- positions history
def record_positions(as_of: str, run_id: str, vintages: dict, status: str = "proposed",
                     path: Path = POSITIONS_PATH) -> None:
    rows = [{"as_of": as_of, "vintage": int(v), "asset": a, "weight": w, "run_id": run_id, "status": status}
            for v, d in vintages.items() for a, w in d["final"].items()]
    new = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = pd.read_csv(path)
        old = old[~((old["as_of"] == as_of) & (old["run_id"] != run_id) & (old["status"] == status))]
        new = pd.concat([old, new], ignore_index=True)
    new.to_csv(path, index=False)


def positions_as_of(date: str, vintage: int, assets: list[str], path: Path = POSITIONS_PATH,
                    before_run: str | None = None) -> tuple[dict | None, str | None]:
    """Latest recorded positions on or before `date` (excluding the current run). Approved beats proposed."""
    if not path.exists():
        return None, None
    df = pd.read_csv(path)
    df = df[(df["vintage"] == vintage) & (pd.to_datetime(df["as_of"]) <= pd.Timestamp(date))]
    if before_run:
        df = df[df["run_id"] != before_run]
    if df.empty:
        return None, None
    df = df.assign(_rank=df["status"].map({"approved": 0}).fillna(1))
    last = df.sort_values(["as_of", "_rank"]).groupby("as_of").head(13)
    as_of = last["as_of"].max()
    snap = last[last["as_of"] == as_of]
    snap = snap[snap["run_id"] == snap.sort_values("_rank")["run_id"].iloc[0]]
    w = dict(zip(snap["asset"], snap["weight"]))
    return {a: float(w.get(a, 0.0)) for a in assets}, f"{as_of} ({snap['status'].iloc[0]}, {snap['run_id'].iloc[0]})"
