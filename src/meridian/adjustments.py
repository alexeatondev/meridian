"""PM/analyst weight adjustments on a run's proposal (absolute or relative; any taxonomy node or fund).

The adjusted portfolio is re-checked by the deterministic compliance engine and the risk budget, recorded
as an `override` decision record (before/after, reason, who), and requires approval again.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .analytics.core import tracking_error
from .analytics.positioning import Taxonomy, apply_adjustment, parse_adjustment, positioning_table
from .compliance import evaluate, summarize
from .entities import resolve
from .ledger import Ledger
from .policy import load_policy, load_universe


def adjust(run_dir: Path, vintage: int, specs: list[str], name: str, role: str, reason: str) -> dict:
    run_dir = Path(run_dir)
    res = json.loads((run_dir / "results.json").read_text())
    if role not in ("portfolio_manager", "analyst", "research"):
        raise SystemExit("Only portfolio managers and analysts can adjust weights.")
    if len(reason.strip()) < 10:
        raise SystemExit("A reason of at least 10 characters is required.")
    d = res["vintages"][str(vintage)]
    model = res["model"]
    assets = model["assets"]
    cov = np.array(model["cov"])
    policy, universe, regime = load_policy(), load_universe(), resolve()
    tax = Taxonomy.load(assets)
    base = d.get("adjusted", {}).get("final") or d["final"]
    w0 = np.array([base[a] for a in assets])
    n = np.array([d["neutral"][a] for a in assets])
    w, steps = w0.copy(), []
    for s in specs:
        adj = parse_adjustment(s)
        w = apply_adjustment(w, tax, adj["node"], adj["mode"], adj["value"], adj["funded_from"])
        steps.append(adj)
    rb = d.get("risk_budget") or policy.risk_budget(vintage)
    comp = evaluate(w, n, cov, policy, regime, universe, risk_budget=rb)
    summ = summarize(comp)
    te = tracking_error(w, n, cov)
    cols = {"current": w, "before_adjustment": w0, "glide_path": n,
            "market": np.array([model["market"][a] for a in assets])}
    tree = positioning_table(tax, cols, cov, n, rb, "asset_class_tree")
    L = Ledger(run_dir / "ledger.jsonl")
    prev = d.get("adjusted", {}).get("dr_id") or next(r["dr_id"] for r in L.records()
                                                         if r["step"] == "cio.ensemble" and f"MTRS-{vintage}" in r["portfolio_scope"])
    dr = L.record(dr_type="override", run_id=res["run_id"], step="pm.adjustment", policy_version=policy.id,
                  actor={"kind": "human", "id": name, "role": role}, inputs=[prev], portfolio_scope=[f"MTRS-{vintage}"],
                  summary=f"{vintage}: {len(steps)} adjustment(s) by {name}; TE {te:.2%} = {te / rb:.0%} of budget; compliance {summ['overall']}",
                  rationale=reason, output={"adjustments": steps, "before": dict(zip(assets, np.round(w0, 6))),
                                            "after": dict(zip(assets, np.round(w, 6)))},
                  constraints_checked=[r.to_dict() for r in comp])
    d["adjusted"] = {"dr_id": dr, "by": name, "role": role, "reason": reason, "adjustments": steps,
                     "final": dict(zip(assets, np.round(w, 6))), "compliance": [r.to_dict() for r in comp],
                     "compliance_summary": summ, "te": te, "risk_budget_used": te / rb, "tree": tree,
                     "approvers": policy.raw["approvals"]["weight_adjustment"]}
    (run_dir / "results.json").write_text(json.dumps(res, indent=2, default=str))
    return d["adjusted"]
