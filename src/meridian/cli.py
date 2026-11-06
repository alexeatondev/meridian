"""Meridian command line."""
from __future__ import annotations

import argparse
import json
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
    elif a.cmd == "verify":
        ok, msg = verify(a.ledger)
        print(("OK " if ok else "FAILED ") + msg)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
