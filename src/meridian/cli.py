"""Meridian command line."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import entities
from .data import DataRegistry
from .ledger import verify


def main(argv=None):
    p = argparse.ArgumentParser(prog="meridian")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("entities", help="show or select operating-entity types")
    e.add_argument("action", choices=["show", "set", "list"])
    e.add_argument("names", nargs="*")

    d = sub.add_parser("data", help="list, plug in/out, route, test and refresh data sources")
    d.add_argument("action", nargs="?", default="list", choices=["list", "enable", "disable", "route", "test", "refresh"])
    d.add_argument("args", nargs="*")
    d.add_argument("--mode", default="merge", choices=["merge", "first"])
    d.add_argument("--fallback", nargs="*", default=None)
    d.add_argument("--as-of")

    r = sub.add_parser("run", help="run a pipeline")
    r.add_argument("pipeline", choices=["target-date"])
    r.add_argument("--as-of", default="2026-10-31")
    r.add_argument("--entities", nargs="*")

    u = sub.add_parser("ui", help="build the role-based Meridian Console for a run")
    u.add_argument("run_dir", type=Path, nargs="?")
    u.add_argument("--out", type=Path)

    ap = sub.add_parser("approve", help="record a human approval decision in a run's ledger")
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--vintage", type=int, required=True)
    ap.add_argument("--role", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--decision", choices=["approve", "reject", "request_changes"], required=True)
    ap.add_argument("--reason", required=True)

    ad = sub.add_parser("adjust", help="adjust a vintage's weights (absolute or relative) and re-check")
    ad.add_argument("run_dir", type=Path)
    ad.add_argument("--vintage", type=int, required=True)
    ad.add_argument("--set", dest="specs", action="append", required=True,
                    help="'Equity=78%%' | 'Equity=+1pp' | 'Fixed Income/Short-dated=+2pp from Fixed Income/Long-dated' | 'asset:us_tips_short=+1pp'")
    ad.add_argument("--name", required=True)
    ad.add_argument("--role", default="portfolio_manager")
    ad.add_argument("--reason", required=True)

    rbp = sub.add_parser("risk-budget", help="show, request and approve risk-budget changes")
    rbp.add_argument("action", choices=["show", "set", "approve", "list"])
    rbp.add_argument("--vintage")
    rbp.add_argument("--te", help="new budget, e.g. 1.0%% or 0.010")
    rbp.add_argument("--id")
    rbp.add_argument("--name")
    rbp.add_argument("--role")
    rbp.add_argument("--decision", choices=["approve", "reject"], default="approve")
    rbp.add_argument("--reason", default="")

    br = sub.add_parser("brand", help="list or check brand themes (config/brand.yaml)")
    br.add_argument("action", choices=["list", "check"], nargs="?", default="list")

    px = sub.add_parser("prices", help="fetch daily closing prices for the home-screen performance table")
    px.add_argument("action", choices=["fetch", "tickers"], nargs="?", default="fetch")
    px.add_argument("--out", type=Path, default=Path("prices.json"))
    px.add_argument("--days", type=int, default=400)

    v = sub.add_parser("verify", help="verify a run's ledger integrity")
    v.add_argument("ledger", type=Path)

    a = p.parse_args(argv)
    if a.cmd == "entities":
        if a.action == "list":
            for k, pk in entities.load_packs().items():
                print(f"{k:24s} {pk['name']}")
        elif a.action == "set":
            entities.save_selection(a.names)
            print("selected:", a.names)
        else:
            reg = entities.resolve()
            print(json.dumps({"selected": reg.selected, "retention_years": reg.retention_years,
                              "obligations": [f"{o['id']}: {o['cite']}" for o in reg.obligations],
                              "rule_patterns": reg.rule_patterns, "reports": reg.reports,
                              "production_blockers": reg.production_blockers}, indent=2))
    elif a.cmd == "data":
        from .data import manage
        from .data.registry import route_spec
        if a.action == "enable":
            for n in a.args:
                manage.set_enabled(n, True)
            print("enabled:", a.args)
        elif a.action == "disable":
            for n in a.args:
                manage.set_enabled(n, False)
            print("disabled:", a.args)
        elif a.action == "route":
            manage.set_route(a.args[0], a.args[1:], a.mode, a.fallback)
            print(f"routing {a.args[0]}: {a.mode} {a.args[1:]} fallback={a.fallback}")
        elif a.action == "test":
            print(json.dumps(manage.test_source(a.args[0], a.as_of), indent=2, default=str))
        elif a.action == "refresh":
            print(json.dumps(manage.refresh(a.as_of), indent=2, default=str)[:6000])
        else:
            reg = DataRegistry.from_config()
            print(f"{'source':22s} {'provider':10s} {'transport':10s} {'on':5s} datasets")
            for s in reg.status():
                print(f"{s['source']:22s} {s['provider']:10s} {s['transport']:10s} {('yes' if s['enabled'] else 'no'):5s} {', '.join(s['datasets'])}")
            print("\nrouting (earlier source wins; fallback only fills what nobody covered):")
            for ds in reg.cfg["routing"]:
                mode, src, fb = route_spec(reg.cfg, ds)
                on = {k for k, v in reg.cfg["sources"].items() if v.get("enabled")}
                fmt = lambda xs: " > ".join(x if x in on else f"({x})" for x in xs)
                print(f"  {ds:24s} [{mode}] {fmt(src)}" + (f"  | fallback: {fmt(fb)}" if fb else ""))
            print("\n(source) = configured but unplugged")
    elif a.cmd == "run":
        from .pipelines.target_date import run
        res = run(as_of=a.as_of, selected_entities=a.entities or None)
        print(f"run {res.run_id}\n  memo: {res.memo_path}\n  compliance: {res.compliance_report_path}\n  ledger: {res.ledger_ok}")
    elif a.cmd == "ui":
        from .ui.build import build
        run_dir = a.run_dir or max((p for p in (Path("runs")).glob("run_*")), key=lambda p: p.stat().st_mtime)
        print(build(run_dir, a.out))
    elif a.cmd == "approve":
        from .approvals import record_decision
        print(record_decision(a.run_dir, a.vintage, a.role, a.name, a.decision, a.reason))
    elif a.cmd == "adjust":
        from .adjustments import adjust
        out = adjust(a.run_dir, a.vintage, a.specs, a.name, a.role, a.reason)
        print(f"recorded {out['dr_id']}: TE {out['te']:.2%} ({out['risk_budget_used']:.0%} of budget); "
              f"compliance {out['compliance_summary']['overall']}; approvals needed: {out['approvers']}")
        for r in out["tree"]:
            if r["depth"] <= 1:
                print(f"  {'  ' * r['depth']}{r['node'].split('/')[-1]:24s} {r['before_adjustment']:7.2%} -> {r['current']:7.2%}")
    elif a.cmd == "risk-budget":
        from . import governance as gv
        from .policy import load_policy
        if a.action == "show":
            pol = load_policy()
            print(f"IPS hard limit {pol.raw['risk_budgets']['hard_max']:.2%}; default {pol.raw['risk_budgets']['default']:.2%}")
            for vv in pol.vintages:
                print(f"  {vv}: {pol.risk_budget(vv):.2%}")
        elif a.action == "set":
            te = float(a.te.rstrip("%")) / (100 if a.te.endswith("%") else 1)
            cr = gv.request_risk_budget_change(a.vintage, te, a.name, a.role, a.reason)
            print(f"{cr['id']} pending: {cr['current']:.2%} -> {cr['proposed']:.2%}; approvals needed: {cr['required_approvals']}")
        elif a.action == "approve":
            cr = gv.approve_change(a.id, a.name, a.role, a.decision, a.reason)
            print(f"{cr['id']}: {cr['status']}")
        else:
            for cr in gv.list_requests():
                print(f"{cr['id']} {cr['status']:9s} {cr['kind']} {cr['target']} {cr['current']:.2%}->{cr['proposed']:.2%} by {cr['requested_by']['name']}")
    elif a.cmd == "prices":
        import json as _json

        import yaml as _yaml

        from . import REPO_ROOT, prices
        insts = _yaml.safe_load((REPO_ROOT / "config" / "trading.yaml").read_text())["instruments"]
        syms = prices.tickers(insts)
        if a.action == "tickers":
            print(" ".join(syms))
        else:
            out = prices.fetch(syms, days=a.days)
            a.out.write_text(_json.dumps(out))
            print(_json.dumps({"as_of": out["as_of"], "tickers": len(out["series"]), "errors": out["errors"]}))
            if not out["series"]:
                return 1
    elif a.cmd == "brand":
        from . import branding
        bad = 0
        for k, t in branding.themes().items():
            probs = branding.check(t)
            bad += bool(probs)
            mark = "*" if k == branding.active_name() else " "
            print(f"{mark} {k:16s} {t.get('label', '')}" + ("" if a.action == "list" else
                  ("  OK" if not probs else "\n    - " + "\n    - ".join(probs))))
        if a.action == "check" and bad:
            sys.exit(1)
    elif a.cmd == "verify":
        ok, msg = verify(a.ledger)
        print(("OK " if ok else "FAILED ") + msg)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
