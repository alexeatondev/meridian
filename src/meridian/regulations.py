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
            if o.get("basis") not in (None, "fiscal", "calendar"):
                raise ValueError(f"{rid}/{o['id']}: basis must be fiscal or calendar")
            o["basis"] = basis(o) if o["frequency"] != "once" else "once"
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
# Fiscal year ends (doc 18 §5): annual and semiannual obligations run on each fund's fiscal year, and so do
# quarterly obligations marked `basis: fiscal` (e.g. the RIC diversification test). Anything marked
# `basis: calendar` (e.g. the CFTC 4.5 annual affirmation) stays on the calendar year. A fiscal year end is
# written "MM-DD" and is always a month end; the default is "12-31" (calendar year).
DEFAULT_FYE = "12-31"
FISCAL_BY_DEFAULT = ("annual", "semiannual")


def _month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def parse_fye(fye: str | None) -> int:
    """Month (1-12) of a fiscal year end "MM-DD" (the day must be that month's last day; Feb accepts 28 or 29)."""
    fye = (fye or DEFAULT_FYE).strip()
    try:
        mm, dd = (int(x) for x in fye.split("-"))
        ok = 1 <= mm <= 12 and dd == calendar.monthrange(2026, mm)[1] or (mm == 2 and dd in (28, 29))
    except ValueError:
        ok = False
    if not ok:
        raise ValueError(f"Fiscal year end must be a month end written MM-DD, e.g. 03-31 or 09-30 (got {fye!r})")
    return mm


def fye_label(fye: str | None) -> str:
    return date(2026, parse_fye(fye), 1).strftime("%B") + " " + str(calendar.monthrange(2026, parse_fye(fye))[1]) \
        if parse_fye(fye) != 2 else "February 28/29"


def basis(ob: dict) -> str:
    """'fiscal' or 'calendar' for an obligation."""
    return ob.get("basis") or ("fiscal" if ob["frequency"] in FISCAL_BY_DEFAULT else "calendar")


def _anchored_end(months: int, d: date, end_month: int) -> date:
    """End of the period of `months` months that contains d, with periods ending in end_month."""
    ends = sorted({(end_month - 1 - k * months) % 12 + 1 for k in range(12 // months)})
    for y in (d.year, d.year + 1):
        for m in ends:
            e = _month_end(y, m)
            if e >= d:
                return e
    raise AssertionError("unreachable")


def period_end(freq: str, d: date, fye: str | None = None) -> date:
    """End of the period containing d. Quarters, halves and years end on the fiscal year end's month when a
    fiscal year end is given (None = calendar)."""
    end_month = parse_fye(fye) if fye else 12
    if freq == "daily":
        return d
    if freq == "monthly":
        return _month_end(d.year, d.month)
    if freq == "quarterly":
        return _anchored_end(3, d, end_month)
    if freq == "semiannual":
        return _anchored_end(6, d, end_month)
    if freq == "annual":
        return _anchored_end(12, d, end_month)
    raise ValueError(freq)


def _fye_for(ob: dict, fye: str | None) -> str | None:
    return (fye or DEFAULT_FYE) if basis(ob) == "fiscal" else None


def _occ(ob: dict, pe: date, fye: str | None) -> dict:
    return {"period": label(ob["frequency"], pe, _fye_for(ob, fye)), "period_end": pe.isoformat(),
            "due": (pe + timedelta(days=int(ob.get("due_days", 0)))).isoformat(), "basis": basis(ob),
            **({"fiscal_year_end": fye or DEFAULT_FYE} if basis(ob) == "fiscal" else {})}


def first_task(ob: dict, start: date, fye: str | None = None) -> dict:
    """The first occurrence of an obligation for a fund tagged on `start`."""
    if ob["frequency"] == "once":
        return {"period": "one-time", "period_end": start.isoformat(),
                "due": (start + timedelta(days=int(ob.get("due_days", 0)))).isoformat(), "basis": "once"}
    return _occ(ob, period_end(ob["frequency"], start, _fye_for(ob, fye)), fye)


def next_task(ob: dict, prev_period_end: str, fye: str | None = None) -> dict | None:
    if ob["frequency"] == "once":
        return None
    pe = period_end(ob["frequency"], date.fromisoformat(prev_period_end) + timedelta(days=1), _fye_for(ob, fye))
    return _occ(ob, pe, fye)


def reschedule(ob: dict, today: date, fye: str) -> dict | None:
    """The occurrence an open obligation should become when a fund's fiscal year end changes: the period that
    has just ended if its due date is still ahead, otherwise the period running now. None for obligations that
    don't follow the fiscal year."""
    if ob["frequency"] == "once" or basis(ob) != "fiscal":
        return None
    f = _fye_for(ob, fye)
    cur = period_end(ob["frequency"], today, f)
    months = {"quarterly": 3, "semiannual": 6, "annual": 12, "monthly": 1}.get(ob["frequency"], 12)
    y, m = cur.year, cur.month - months
    while m < 1:
        m, y = m + 12, y - 1
    prev = _month_end(y, m)
    if prev + timedelta(days=int(ob.get("due_days", 0))) >= today:
        return _occ(ob, prev, fye)
    return _occ(ob, cur, fye)


def label(freq: str, pe: date, fye: str | None = None) -> str:
    fiscal = fye is not None and parse_fye(fye) != 12
    if freq == "daily":
        return pe.isoformat()
    if freq == "monthly":
        return pe.strftime("%b %Y")
    if freq == "quarterly":
        return f"Fiscal quarter to {pe:%b %Y}" if fiscal else f"Q{(pe.month - 1) // 3 + 1} {pe.year}"
    if freq == "semiannual":
        return f"Half-year to {pe:%b %Y}" if fiscal else f"H{1 if pe.month <= 6 else 2} {pe.year}"
    return f"FY to {pe:%b %Y}" if fiscal else f"FY {pe.year}"
