"""Build the Meridian Console: one self-contained, role-adaptive web page for a pipeline run.

The page embeds the run's results, decision ledger, entity regime, policy rules and universe.
It adapts to the signed-in role (portfolio manager, risk, research, manager selection, leadership,
compliance, audit). In production the role comes from SSO and the page is served by the API; the
static build is the prototype and the offline/exam-evidence form.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import REPO_ROOT
from ..entities import resolve
from ..ledger import Ledger, verify
from ..policy import load_policy, load_universe

TEMPLATE = Path(__file__).with_name("console_template.html")


def build(run_dir: Path, out: Path | None = None) -> Path:
    run_dir = Path(run_dir)
    results = json.loads((run_dir / "results.json").read_text())
    ledger = Ledger(run_dir / "ledger.jsonl").records()
    ok, msg = verify(run_dir / "ledger.jsonl")
    policy, universe = load_policy(), load_universe()
    reg = resolve()
    pre = next((r for r in ledger if r["step"] == "preflight.entity_regime"), None)
    data = {
        "results": results,
        "ledger": ledger,
        "ledger_verification": {"ok": ok, "message": msg},
        "policy": {"id": policy.id, "rules": policy.rules, "assets": policy.assets, "groups": policy.groups,
                   "anchors": policy.raw["glide_path"]["anchors"], "approvals": policy.raw["approvals"]},
        "universe": universe,
        "regime": {"selected": reg.selected, "obligations": reg.obligations, "retention_years": reg.retention_years,
                   "required_roles": reg.required_roles, "human_roles": reg.human_roles,
                   "production_blockers": reg.production_blockers, "autonomy": reg.autonomy_level,
                   "mode": reg.operating_mode, "recorded_in_run": pre["output"] if pre else None},
        "board_memo_md": (run_dir / "board_memo.md").read_text(),
        "compliance_report_md": (run_dir / "compliance_report.md").read_text(),
    }
    html = TEMPLATE.read_text().replace("/*__MERIDIAN_DATA__*/null", json.dumps(data, default=str))
    out = Path(out or run_dir / "console.html")
    out.write_text(html)
    return out


if __name__ == "__main__":  # pragma: no cover
    import sys
    print(build(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None))
