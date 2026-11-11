"""Fund-level regulations (doc 18): library, controls on holdings, and obligation schedules.

Pure functions; the web app (meridian.app.regulations) stores tags and tasks and records every step.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import yaml

from . import REPO_ROOT

LIBRARY_PATH = REPO_ROOT / "regimes" / "fund_regulations.yaml"
FREQS = ("once", "daily", "monthly", "quarterly", "semiannual", "annual")
FUND_TYPES = ("mutual_fund", "cit", "etf")
DERIV_TYPES = ("future", "option", "swap", "fx_forward")


@lru_cache(maxsize=1)
def library(path: str = str(LIBRARY_PATH)) -> dict:
    raw = yaml.safe_load(Path(path).read_text())
    regs = raw["regulations"]
    for rid, r in regs.items():
        r["id"] = rid
        for o in r.get("obligations", []):
            if o["frequency"] not in FREQS:
                raise ValueError(f"{rid}/{o['id']}: frequency must be one of {FREQS}")
        for c in r.get("controls", []):
            if c["severity"] not in ("FAIL", "WARN"):
                raise ValueError(f"{rid}/{c['id']}: severity must be FAIL or WARN")
    return {"regulations": regs, "suggestions": raw.get("suggestions", {})}


# ------------------------------------------------------------------------------------------ attributes
def attrs(inst: dict) -> dict:
    iid = inst.get("id", "")
    return {"affiliated": inst.get("affiliated", iid.startswith("MER-")), "ucits": bool(inst.get("ucits", False)),
            "government": bool(inst.get("government", False)), "liquidity": inst.get("liquidity", "liquid"),
            "issuer": inst.get("issuer", iid), "type": inst.get("type", "")}


def holdings_rows(positions: dict, instruments: dict) -> list[dict]:
    """Current holdings as weights, in the same shape as a trade preview's rows (post_w = current weight)."""
    nav = positions["cash"] + sum(positions["values"].values())
    rows = [{"instrument": k, "type": instruments.get(k, {}).get("type", ""), "post_w": v / nav}
            for k, v in positions["values"].items() if v]
    rows.append({"instrument": "CASH", "type": "cash", "post_w": positions["cash"] / nav})
    return rows


# ------------------------------------------------------------------------------------------ controls
def _res(reg: dict, c: dict, measured: float, limit: float, ok: bool, detail: str) -> dict:
    return {"rule_id": c["id"], "regulation": reg["id"], "regulation_name": reg.get("short", reg["name"]),
            "status": "PASS" if ok else c["severity"], "measured": round(measured, 6), "limit": limit,
            "detail": detail, "cite": c.get("cite", ""), "text": c.get("text", "")}


def evaluate_controls(rows: list[dict], instruments: dict, tags: list[dict]) -> list[dict]:
    """Run every control of every regulation tagged on a fund against its (post-trade) holdings.
    rows: [{instrument, type, post_w}]; tags: [{reg_id, params}]."""
    lib = library()["regulations"]
    w = {r["instrument"]: float(r["post_w"]) for r in rows if r["instrument"] != "CASH"}
    a = {k: attrs(dict(instruments.get(k, {}), id=k)) for k in w}
    funds = {k: v for k, v in w.items() if a[k]["type"] in FUND_TYPES}
    direct = {k: v for k, v in w.items() if a[k]["type"] in ("stock", "bond") and not a[k]["government"]}
    issuers: dict[str, float] = {}
    for k, v in direct.items():
        issuers[a[k]["issuer"]] = issuers.get(a[k]["issuer"], 0.0) + v
    out = []
    for tag in tags:
        reg = lib.get(tag["reg_id"])
        if not reg:
            continue
        params = tag.get("params") or {}
        for c in reg.get("controls", []):
            k = c["kind"]
            if k == "max_single_fund":
                top = max(funds.items(), key=lambda kv: kv[1], default=("—", 0.0))
                out.append(_res(reg, c, top[1], c["limit"], top[1] <= c["limit"] + 1e-9,
                                f"Largest underlying fund {top[0]} {top[1]:.2%} (limit {c['limit']:.0%})"))
            elif k == "max_fund_group":
                f = c["filter"]
                sel = {i: v for i, v in funds.items() if (f == "non_ucits" and not a[i]["ucits"]) or
                       (f == "affiliated" and a[i]["affiliated"])}
                tot = sum(sel.values())
                out.append(_res(reg, c, tot, c["limit"], tot <= c["limit"] + 1e-9,
                                f"{len(sel)} funds, {tot:.2%} in total (limit {c['limit']:.0%})"))
            elif k == "max_unaffiliated_fund":
                un = {i: v for i, v in funds.items() if not a[i]["affiliated"]}
                tot, top = sum(un.values()), max(un.items(), key=lambda kv: kv[1], default=("—", 0.0))
                if params.get(c.get("param_flag", "")):
                    out.append(_res(reg, c, tot, c["limit_total"], True,
                                    f"Relying on Rule 12d1-4 (fund-of-funds agreements): unaffiliated funds {tot:.2%}"))
                else:
                    ok = top[1] <= c["limit_each"] + 1e-9 and tot <= c["limit_total"] + 1e-9
                    out.append(_res(reg, c, max(top[1], tot), c["limit_total"], ok,
                                    f"Largest unaffiliated fund {top[0]} {top[1]:.2%} (limit {c['limit_each']:.0%}); "
                                    f"all unaffiliated funds {tot:.2%} (limit {c['limit_total']:.0%})"))
            elif k == "issuer_5_10_40":
                top = max(issuers.items(), key=lambda kv: kv[1], default=("—", 0.0))
                big = sum(v for v in issuers.values() if v > c["threshold"])
                ok = top[1] <= c["limit_each"] + 1e-9 and big <= c["limit_sum"] + 1e-9
                out.append(_res(reg, c, top[1], c["limit_each"], ok,
                                f"Largest issuer {top[0]} {top[1]:.2%}; issuers above {c['threshold']:.0%}: {big:.2%}"
                                " (government and fund holdings excepted)"))
            elif k == "diversified_75_5_10":
                big = sum(v for v in issuers.values() if v > 0.05)
                out.append(_res(reg, c, big, 0.25, big <= 0.25 + 1e-9,
                                f"Issuers above 5%: {big:.2%} of assets (limit 25%); government and fund holdings excepted"))
            elif k == "max_illiquid":
                ill = sum(v for i, v in w.items() if a[i]["liquidity"] == "illiquid")
                out.append(_res(reg, c, ill, c["limit"], ill <= c["limit"] + 1e-9,
                                f"Illiquid holdings {ill:.2%} (limit {c['limit']:.0%})"))
            elif k == "max_derivatives":
                d = sum(abs(v) for i, v in w.items() if a[i]["type"] in DERIV_TYPES)
                out.append(_res(reg, c, d, c["limit"], d <= c["limit"] + 1e-9,
                                f"Derivatives exposure {d:.2%} (limit {c['limit']:.0%})"))
            elif k in ("min_cash", "max_cash"):
                cash = next((float(r["post_w"]) for r in rows if r["instrument"] == "CASH"), 0.0)
                ok = cash >= c["limit"] if k == "min_cash" else cash <= c["limit"]
                out.append(_res(reg, c, cash, c["limit"], ok, f"Cash {cash:.2%}"))
            else:
                raise ValueError(f"Unknown control kind {k}")
    return out


def overall(results: list[dict]) -> str:
    st = {r["status"] for r in results}
    return "FAIL" if "FAIL" in st else "WARN" if "WARN" in st else "PASS"


# ------------------------------------------------------------------------------------------ schedules
def _month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def period_end(freq: str, d: date) -> date:
    """End of the period containing d."""
    if freq == "daily":
        return d
    if freq == "monthly":
        return _month_end(d.year, d.month)
    if freq == "quarterly":
        return _month_end(d.year, 3 * ((d.month - 1) // 3) + 3)
    if freq == "semiannual":
        return _month_end(d.year, 6 if d.month <= 6 else 12)
    if freq == "annual":
        return date(d.year, 12, 31)
    raise ValueError(freq)


def first_task(ob: dict, start: date) -> dict:
    """The first occurrence of an obligation for a fund tagged on `start`."""
    if ob["frequency"] == "once":
        return {"period": "one-time", "period_end": start.isoformat(),
                "due": (start + timedelta(days=int(ob.get("due_days", 0)))).isoformat()}
    pe = period_end(ob["frequency"], start)
    return {"period": label(ob["frequency"], pe), "period_end": pe.isoformat(),
            "due": (pe + timedelta(days=int(ob.get("due_days", 0)))).isoformat()}


def next_task(ob: dict, prev_period_end: str) -> dict | None:
    if ob["frequency"] == "once":
        return None
    pe = period_end(ob["frequency"], date.fromisoformat(prev_period_end) + timedelta(days=1))
    return {"period": label(ob["frequency"], pe), "period_end": pe.isoformat(),
            "due": (pe + timedelta(days=int(ob.get("due_days", 0)))).isoformat()}


def label(freq: str, pe: date) -> str:
    if freq == "daily":
        return pe.isoformat()
    if freq == "monthly":
        return pe.strftime("%b %Y")
    if freq == "quarterly":
        return f"Q{(pe.month - 1) // 3 + 1} {pe.year}"
    if freq == "semiannual":
        return f"H{1 if pe.month <= 6 else 2} {pe.year}"
    return f"FY {pe.year}"
