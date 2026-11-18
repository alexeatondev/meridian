"""Build the Meridian Console: one role-adaptive web page for a pipeline run.

Used two ways: `meridian ui` writes a self-contained file for a run directory (offline/evidence form), and
the hosted app renders the same page from the database with LIVE mode on (signed-in user, roles limited
to the user's own, actions saved through the API).
"""
from __future__ import annotations

import json
from pathlib import Path

from ..entities import resolve
from ..ledger import Ledger, verify
from ..policy import load_policy, load_universe

TEMPLATE = Path(__file__).with_name("console_template.html")


def _example_products(policy) -> dict | None:
    """Product lines and funds from config/trading.yaml with example positions (offline console)."""
    try:
        from ..trading.model import load_model
        from ..trading.overview import product_overview
        return product_overview(load_model(policy=policy))
    except Exception:  # the console still works without product-line detail
        return None


def console_html(results: dict, ledger: list[dict], ledger_verification: dict, board_memo_md: str,
                 compliance_report_md: str, change_requests: list[dict] | None = None,
                 policy=None, live: dict | None = None, products: dict | None = None) -> str:
    policy = policy or load_policy()
    universe, reg = load_universe(), resolve()
    pre = next((r for r in ledger if r["step"] == "preflight.entity_regime"), None)
    data = {
        "results": results, "ledger": ledger, "ledger_verification": ledger_verification,
        "policy": {"id": policy.id, "rules": policy.rules, "assets": policy.assets, "groups": policy.groups,
                   "anchors": policy.raw["glide_path"]["anchors"], "approvals": policy.raw["approvals"]},
        "universe": universe,
        "regime": {"selected": reg.selected, "obligations": reg.obligations, "retention_years": reg.retention_years,
                   "required_roles": reg.required_roles, "human_roles": {r: reg.holder_label(r) for r in reg.required_roles}, "unfilled_roles": reg.unfilled_roles,
                   "production_blockers": reg.production_blockers, "autonomy": reg.autonomy_level,
                   "mode": reg.operating_mode, "recorded_in_run": pre["output"] if pre else None},
        "board_memo_md": board_memo_md, "compliance_report_md": compliance_report_md,
        "risk_budget_policy": policy.raw.get("risk_budgets", {}),
        "change_requests": change_requests or [],
        "products": products if products is not None else _example_products(policy),
    }
    html = TEMPLATE.read_text().replace("/*__MERIDIAN_DATA__*/null", json.dumps(data, default=str).replace("</", "<\\/"))
    html = html.replace("/*__MERIDIAN_LIVE__*/null", json.dumps(live).replace("</", "<\\/") if live else "null")
    from ..branding import theme_css          # the active brand theme (config/brand.yaml)
    return html.replace("</head>", theme_css() + "</head>", 1)


def build(run_dir: Path, out: Path | None = None) -> Path:
    from ..governance import list_requests
    run_dir = Path(run_dir)
    ok, msg = verify(run_dir / "ledger.jsonl")
    html = console_html(json.loads((run_dir / "results.json").read_text()), Ledger(run_dir / "ledger.jsonl").records(),
                        {"ok": ok, "message": msg}, (run_dir / "board_memo.md").read_text(),
                        (run_dir / "compliance_report.md").read_text(), list_requests())
    out = Path(out or run_dir / "console.html")
    out.write_text(html)
    return out


if __name__ == "__main__":  # pragma: no cover
    import sys
    print(build(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None))
