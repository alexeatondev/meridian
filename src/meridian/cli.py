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

    sub.add_parser("data", help="show data source status and routing")

    r = sub.add_parser("run", help="run a pipeline")
    r.add_argument("pipeline", choices=["target-date"])
    r.add_argument("--as-of", default="2026-10-31")
    r.add_argument("--entities", nargs="*")

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
        reg = DataRegistry.from_config()
        for s in reg.status():
            print(f"{s['source']:22s} {s['provider']:10s} {s['transport']:10s} enabled={s['enabled']!s:5s} license={s['license_review']}")
        print("\nrouting:")
        for ds, route in reg.cfg["routing"].items():
            print(f"  {ds:24s} -> {' > '.join(route)}")
    elif a.cmd == "run":
        from .pipelines.target_date import run
        res = run(as_of=a.as_of, selected_entities=a.entities or None)
        print(f"run {res.run_id}\n  memo: {res.memo_path}\n  compliance: {res.compliance_report_path}\n  ledger: {res.ledger_ok}")
    elif a.cmd == "verify":
        ok, msg = verify(a.ledger)
        print(("OK " if ok else "FAILED ") + msg)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
