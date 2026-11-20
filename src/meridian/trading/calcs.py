"""Custom calculations (doc 17 item 13): named, versioned templates that turn an order into tranches.

A template is a set of parameters for one of a few fixed calculation kinds; there are no free-form formulas
(model-risk rule, doc 04: those would need change control of their own). Each version of a template needs a
second person's approval before it can be used, and every trade list records which template version made
its tranches.

Kinds
- pct_per_day   trade a fixed percentage of the order every N business days (e.g. sell 20% a day)
- even_split    split the order equally over a number of tranches, every N business days
- pattern       an explicit list of percentages, every N business days (e.g. glide down 40/30/20/10 weekly)
- liquidity_cap each tranche at most a share of the security's average daily volume and/or a dollar amount
                a day; the number of days follows from the order size
Common parameters: sides (SELL, BUY or BOTH), start_offset_days (business days after the trade date),
every_n_days, max_days.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

KINDS = {
    "pct_per_day": "Fixed % of the order per period",
    "even_split": "Equal tranches",
    "pattern": "Percentage pattern (glide down)",
    "liquidity_cap": "Liquidity-capped",
}
SIDES = ("SELL", "BUY", "BOTH")
MAX_DAYS = 60


def _f(v, what: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a number")


def clean_params(kind: str, p: dict) -> dict:
    """Validate and normalise a template's parameters. Raises ValueError with a plain message."""
    if kind not in KINDS:
        raise ValueError(f"Kind must be one of: {', '.join(KINDS)}")
    p = dict(p or {})
    out = {"sides": str(p.get("sides", "SELL")).upper(),
           "start_offset_days": int(_f(p.get("start_offset_days", 0), "Start offset")),
           "every_n_days": int(_f(p.get("every_n_days", 1), "Every N business days")),
           "max_days": int(_f(p.get("max_days", 20), "Most tranches"))}
    if out["sides"] not in SIDES:
        raise ValueError("Sides must be SELL, BUY or BOTH")
    if not 0 <= out["start_offset_days"] <= 20:
        raise ValueError("Start offset must be 0 to 20 business days")
    if not 1 <= out["every_n_days"] <= 20:
        raise ValueError("Every N business days must be 1 to 20")
    if not 2 <= out["max_days"] <= MAX_DAYS:
        raise ValueError(f"Most tranches must be 2 to {MAX_DAYS}")
    if kind == "pct_per_day":
        x = _f(p.get("pct"), "Percentage per period")
        if not 1 <= x <= 99:
            raise ValueError("Percentage per period must be between 1 and 99")
        if math.ceil(100 / x - 1e-9) > out["max_days"]:
            raise ValueError(f"{x:g}% per period needs {math.ceil(100 / x - 1e-9)} tranches, more than the limit of {out['max_days']}")
        out["pct"] = x
    elif kind == "even_split":
        n = int(_f(p.get("tranches"), "Number of tranches"))
        if not 2 <= n <= out["max_days"]:
            raise ValueError(f"Number of tranches must be 2 to {out['max_days']}")
        out["tranches"] = n
    elif kind == "pattern":
        raw = p.get("pcts")
        pcts = [_f(x, "Each percentage") for x in (raw.split(",") if isinstance(raw, str) else raw or [])]
        if not 2 <= len(pcts) <= out["max_days"]:
            raise ValueError(f"Give 2 to {out['max_days']} percentages")
        if any(x <= 0 for x in pcts) or abs(sum(pcts) - 100) > 0.01:
            raise ValueError(f"Percentages must be above zero and add up to 100% (they add up to {sum(pcts):g}%)")
        out["pcts"] = pcts
    elif kind == "liquidity_cap":
        adv = p.get("max_pct_adv")
        usd = p.get("max_usd_per_day")
        adv = None if adv in (None, "") else _f(adv, "Share of average daily volume")
        usd = None if usd in (None, "") else _f(usd, "Dollar cap per day")
        if adv is None and usd is None:
            raise ValueError("Give a share of average daily volume, a dollar cap per day, or both")
        if adv is not None and not 0 < adv <= 100:
            raise ValueError("Share of average daily volume must be above 0 and at most 100%")
        if usd is not None and usd < 1000:
            raise ValueError("Dollar cap per day must be at least $1,000")
        out["max_pct_adv"], out["max_usd_per_day"] = adv, usd
    return out


def describe(kind: str, p: dict) -> str:
    every = "a day" if p["every_n_days"] == 1 else f"every {p['every_n_days']} business days"
    side = {"SELL": "Sells", "BUY": "Buys", "BOTH": "Buys and sells"}[p["sides"]]
    start = "" if not p["start_offset_days"] else f", starting {p['start_offset_days']} business days after the trade date"
    if kind == "pct_per_day":
        what = f"{p['pct']:g}% of the order {every}"
    elif kind == "even_split":
        what = f"{p['tranches']} equal tranches, {every}"
    elif kind == "pattern":
        what = " / ".join(f"{x:g}%" for x in p["pcts"]) + f", {every}"
    else:
        caps = ([f"{p['max_pct_adv']:g}% of average daily volume"] if p.get("max_pct_adv") else []) + \
               ([f"${p['max_usd_per_day']:,.0f} a day"] if p.get("max_usd_per_day") else [])
        what = "at most " + " and ".join(caps) + f" per tranche, {every}, up to {p['max_days']} tranches"
    return f"{side}: {what}{start}"


def business_days(trade_date: str, n: int, holidays: set[str], every: int = 1, offset: int = 0) -> list[str]:
    """n dates: the first business day on or after the trade date, moved `offset` business days on, then every
    `every` business days. Weekends and market holidays are skipped."""
    d = date.fromisoformat(trade_date)

    def ok(x: date) -> bool:
        return x.weekday() < 5 and x.isoformat() not in holidays

    def step(x: date, k: int) -> date:
        while k:
            x += timedelta(days=1)
            if ok(x):
                k -= 1
        return x

    while not ok(d):
        d += timedelta(days=1)
    d = step(d, offset)
    out = [d]
    while len(out) < n:
        out.append(step(out[-1], every))
    return [x.isoformat() for x in out]


def _lot(order: dict) -> float:
    return 1000.0 if order["quantity_type"] == "FACE" else 1.0 if order["quantity_type"] == "SHARES" else 0.001


def _pcts_from_cap(qty: float, cap_qty: float, step: float) -> list[float]:
    cap_qty = math.floor(cap_qty / step + 1e-9) * step
    if cap_qty <= 0:
        raise ValueError("cap is smaller than one trading lot")
    n = max(1, math.ceil(qty / cap_qty - 1e-9))
    return [math.ceil(cap_qty / qty * 100 * 1e6) / 1e6] * (n - 1) + [None]   # last tranche takes the rest


def schedule(kind: str, p: dict, order: dict, trade_date: str, holidays: set[str], inst: dict) -> tuple[list | None, str]:
    """Tranche schedule [{date, pct}] for one order, or (None, why not)."""
    if p["sides"] != "BOTH" and order["side"] != p["sides"]:
        return None, f"{order['side'].lower()} order: the template only applies to {p['sides'].lower()}s"
    if kind == "pct_per_day":
        n = math.ceil(100 / p["pct"] - 1e-9)
        pcts = [p["pct"]] * (n - 1) + [None]
    elif kind == "even_split":
        n = p["tranches"]
        pcts = [round(100 / n, 6)] * (n - 1) + [None]
    elif kind == "pattern":
        pcts = list(p["pcts"][:-1]) + [None]
    else:
        caps, why = [], []
        if p.get("max_pct_adv"):
            if inst.get("adv"):
                caps.append(inst["adv"] * p["max_pct_adv"] / 100)
                why.append(f"{p['max_pct_adv']:g}% of ADV {inst['adv']:,.0f}")
            elif not p.get("max_usd_per_day"):
                return None, "no average daily volume for this security (it trades at NAV); one order"
        if p.get("max_usd_per_day"):
            unit = order["price"] / (100 if order["quantity_type"] == "FACE" else 1)
            caps.append(p["max_usd_per_day"] / unit)
            why.append(f"${p['max_usd_per_day']:,.0f} a day")
        try:
            pcts = _pcts_from_cap(order["quantity"], min(caps), _lot(order))
        except ValueError:
            return None, "the cap is smaller than one trading lot: trades in one order"
        if len(pcts) == 1:
            return None, "within the cap: trades in one order"
        if len(pcts) > p["max_days"]:
            return None, (f"needs {len(pcts)} tranches at {' and '.join(why)}, more than the limit of {p['max_days']}; "
                          "raise the limit or the cap")
    if len(pcts) > p["max_days"]:
        return None, f"needs {len(pcts)} tranches, more than the limit of {p['max_days']}"
    pcts[-1] = round(100 - sum(pcts[:-1]), 6)
    dates = business_days(trade_date, len(pcts), holidays, p["every_n_days"], p["start_offset_days"])
    return [{"date": d, "pct": x} for d, x in zip(dates, pcts)], ""
