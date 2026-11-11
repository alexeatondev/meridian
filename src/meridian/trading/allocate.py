"""Cashflow allocation engine (doc 17 items 1, 3, 4, 6, 8, 10).

A fund's net cashflow is split **pro rata** across the chosen strategy's target table (gaps to target are only
closed by a rebalance, never by a cashflow). Securities without a target are left out. Excluded securities
are not traded; their share is spread over the rest (default) or left in cash. ETF buys are reduced by the cash
buffer so a price move can't overdraw the account; the amount held back stays in cash. Sells never exceed the
position; any shortfall moves to the other holdings.
"""
from __future__ import annotations

import math

from .model import EXCHANGE_TRADED, TradingModel


def _qty(inst: dict, amount: float, side: str) -> float:
    price = float(inst["price"])
    if inst["type"] == "bond":                 # price per 100 face; trade in $1,000 face
        face = abs(amount) / price * 100
        face = math.floor(face / 1000) * 1000 if side == "BUY" else round(face / 1000) * 1000
        return float(face)
    if inst["type"] in ("etf", "stock"):       # whole shares; round buys down so cash can't go negative
        sh = abs(amount) / price
        return float(math.floor(sh) if side == "BUY" else round(sh))
    return round(abs(amount) / price, 3)       # fund units (mutual funds, CITs) to 3 decimals


def _amount(inst: dict, qty: float) -> float:
    p = float(inst["price"])
    return round(qty * p / 100 if inst["type"] == "bond" else qty * p, 2)


def allocate_fund(model: TradingModel, fund_id: str, flow: float, positions: dict, table: dict[str, float], *,
                  routes: dict, excluded: set[str] | None = None, excluded_share: str = "redistribute",
                  buffer_bps: float = 0.0) -> dict:
    """Return orders, notes and a current vs post-trade preview for one fund and one net cashflow."""
    excluded = set(excluded or ())
    inst = model.instruments
    values = dict(positions["values"])
    cash = float(positions["cash"])
    nav = cash + sum(values.values())
    notes: list[str] = []

    no_target = sorted(k for k, v in values.items() if v > 0 and not (k in inst and model.has_target(inst[k], fund_id)))
    for k in no_target:
        notes.append(f"{k} is held but has no target: left out of the cash allocation")
    w = {k: v for k, v in table.items() if v > 0 and k in inst and model.has_target(inst[k], fund_id)}
    total_w = sum(w.values())
    hit = sorted(k for k in w if k in excluded)
    for k in hit:
        notes.append(f"{k} is excluded from trading: its share is "
                     + ("spread over the other holdings" if excluded_share == "redistribute" else "left in cash"))
    w = {k: v for k, v in w.items() if k not in excluded}
    denom = sum(w.values()) if excluded_share == "redistribute" else total_w
    if flow and denom <= 0:
        return {"fund_id": fund_id, "flow": flow, "orders": [], "notes": notes + ["Nothing eligible to trade"],
                "errors": ["No eligible securities with a target"], "preview": [], "cash_before": cash,
                "cash_after": cash + flow, "nav_before": nav, "nav_after": nav + flow, "buffer_held": 0.0}
    amounts = {k: flow * v / denom for k, v in w.items()} if flow else {}

    if flow < 0:                                # sells: cap at the position, move any shortfall to the rest
        for _ in range(len(amounts) + 1):
            over = {k: -a - values.get(k, 0.0) for k, a in amounts.items() if -a > values.get(k, 0.0) + 0.005}
            if not over:
                break
            spill = sum(over.values())
            for k in over:
                amounts[k] = -values.get(k, 0.0)
            room = {k: values.get(k, 0.0) + a for k, a in amounts.items() if k not in over and values.get(k, 0.0) + a > 0}
            rt = sum(room.values())
            if rt <= 0:
                notes.append(f"Holdings are short of the redemption by ${spill:,.0f}")
                break
            for k, r in room.items():
                amounts[k] -= spill * r / rt

    buffer_held = 0.0
    if buffer_bps and flow > 0:                 # cash buffer on ETF buys (doc 17 item 10)
        for k, a in amounts.items():
            if inst[k]["type"] == "etf" and a > 0:
                cut = a * buffer_bps / 10000
                amounts[k] = a - cut
                buffer_held += cut
        if buffer_held:
            notes.append(f"Cash buffer {buffer_bps:g} bp held back ${buffer_held:,.0f} from ETF buys")

    orders, traded = [], {}
    for k, a in sorted(amounts.items(), key=lambda kv: -abs(kv[1])):
        side = "BUY" if a > 0 else "SELL"
        q = _qty(inst[k], a, side)
        if side == "SELL" and inst[k]["type"] in EXCHANGE_TRADED:
            q = min(q, math.floor(values.get(k, 0.0) / (float(inst[k]["price"]) / (100 if inst[k]["type"] == "bond" else 1))))
        if q <= 0:
            continue
        o = _order(model, k, side, q, routes)
        traded[k] = o["est_amount"] if side == "BUY" else -o["est_amount"]
        orders.append(o)

    return _result(model, fund_id, flow, values, cash, traded, orders, table, excluded, notes, buffer_held)


def _order(model: TradingModel, k: str, side: str, q: float, routes: dict) -> dict:
    i = model.instruments[k]
    return {"instrument": k, "name": i["name"], "type": i["type"], "asset_class": i["asset_class"], "side": side,
            "quantity": q, "quantity_type": _qtype(i), "price": float(i["price"]), "est_amount": _amount(i, q),
            "route": model.route_for(i, routes)}


def _qtype(i: dict) -> str:
    return "FACE" if i["type"] == "bond" else "SHARES" if i["type"] in ("etf", "stock") else "UNITS"


def _result(model, fund_id, flow, values, cash, traded, orders, table, excluded, notes, buffer_held=0.0) -> dict:
    inst = model.instruments
    nav = cash + sum(values.values())
    cash_after = round(cash + flow - sum(traded.values()), 2)
    nav_after = nav + flow
    rows = []
    for k in sorted(set(values) | set(traded) | set(table), key=lambda x: (inst.get(x, {}).get("asset_class", ""), x)):
        cur, t = values.get(k, 0.0), traded.get(k, 0.0)
        if not cur and not t and not table.get(k):
            continue
        i = inst.get(k, {})
        rows.append({"instrument": k, "name": i.get("name", k), "type": i.get("type", ""),
                     "asset_class": i.get("asset_class", ""), "current": round(cur, 2),
                     "current_w": cur / nav if nav else 0, "trade": round(t, 2), "post": round(cur + t, 2),
                     "post_w": (cur + t) / nav_after if nav_after else 0, "target_w": table.get(k, 0.0),
                     "has_target": bool(i) and model.has_target(i, fund_id), "excluded": k in excluded})
    rows.append({"instrument": "CASH", "name": "Uninvested cash (custody account)", "type": "cash",
                 "asset_class": "cash", "current": round(cash, 2), "current_w": cash / nav if nav else 0,
                 "trade": round(cash_after - cash, 2), "post": cash_after,
                 "post_w": cash_after / nav_after if nav_after else 0, "target_w": 0.0, "has_target": False,
                 "excluded": False})
    errors = []
    if cash_after < -0.005:
        errors.append(f"Cash would go negative (${cash_after:,.0f})")
    if any(r["post"] < -0.005 for r in rows):
        errors.append("A position would go negative")
    return {"fund_id": fund_id, "flow": flow, "orders": orders, "notes": notes, "errors": errors, "preview": rows,
            "cash_before": round(cash, 2), "cash_after": cash_after, "nav_before": round(nav, 2),
            "nav_after": round(nav_after, 2), "buffer_held": round(buffer_held, 2),
            "rounding_residual": round(flow - sum(traded.values()) - buffer_held, 2) if flow else 0.0}


def apply_tilts(table: dict[str, float], tilts: dict[str, float]) -> tuple[dict[str, float], list[str]]:
    """Tilt toward (+bp) or away from (-bp) specific holdings in an allocation table (doc 17 item 5).
    The tilt is funded pro rata from (or returned pro rata to) the other holdings; weights still total 100%."""
    notes, out = [], dict(table)
    live = {k: bp for k, bp in tilts.items() if bp}
    for k in sorted(set(live) - set(table)):
        notes.append(f"Tilt on {k} ignored: it is not in this allocation table")
    live = {k: bp for k, bp in live.items() if k in table}
    if not live:
        return out, notes
    for k, bp in live.items():
        new = max(0.0, table[k] + bp / 10000)
        if new == 0.0 and table[k] + bp / 10000 < 0:
            notes.append(f"Tilt on {k} capped: its weight can't go below zero")
        out[k] = new
    rest = sum(v for k, v in table.items() if k not in live)
    left = 1 - sum(out[k] for k in live)
    if rest <= 0 or left < 0:
        return dict(table), [*notes, "Tilts ignored: nothing left to fund them from"]
    for k in table:
        if k not in live:
            out[k] = table[k] * left / rest
    for k, bp in sorted(live.items()):
        notes.append(f"Tilt {bp:+g} bp on {k}: {table[k] * 100:.2f}% → {out[k] * 100:.2f}% of the allocation, "
                     "funded pro rata from the other holdings")
    return {k: v for k, v in out.items() if v > 0}, notes


def ticket_fund(model: TradingModel, fund_id: str, tickets: list[dict], positions: dict, *, routes: dict,
                table: dict[str, float] | None = None, excluded: set[str] | None = None,
                blocked_buys: set[str] | None = None) -> dict:
    """Hand-entered orders for individual securities in one fund (doc 17 items 11, 12). Buys are paid from the
    fund's cash and sells add to it. tickets: [{instrument, side, amount | quantity | all}]."""
    inst, values, cash = model.instruments, dict(positions["values"]), float(positions["cash"])
    allowed = {i["id"] for i in model.fund_instruments(fund_id)}
    excluded, blocked_buys = set(excluded or ()), set(blocked_buys or ())
    orders, traded, errors, notes = [], {}, [], []
    for t in tickets:
        k, side = t.get("instrument"), str(t.get("side", "")).upper()
        if k not in allowed:
            errors.append(f"{k} is not available to {fund_id}")
            continue
        if side not in ("BUY", "SELL"):
            errors.append(f"{k}: side must be BUY or SELL")
            continue
        if k in traded:
            errors.append(f"{k}: one order per security")
            continue
        i, held = inst[k], values.get(k, 0.0)
        unit = float(i["price"]) / (100 if i["type"] == "bond" else 1)
        if t.get("all"):
            if side != "SELL":
                errors.append(f"{k}: only a sell can be for the whole position")
                continue
            q = math.floor(held / unit) if i["type"] in EXCHANGE_TRADED else round(held / unit, 3)
            if i["type"] == "bond":
                q = math.floor(q / 1000) * 1000
        elif t.get("quantity"):
            q = float(t["quantity"])
        else:
            q = _qty(i, float(t.get("amount") or 0), side)
        if q <= 0:
            errors.append(f"{k}: nothing to trade")
            continue
        o = _order(model, k, side, float(q), routes)
        if side == "SELL" and o["est_amount"] > held + 0.01:
            errors.append(f"{k}: selling ${o['est_amount']:,.0f} but only ${held:,.0f} is held")
        if side == "BUY" and k in blocked_buys:
            errors.append(f"{k} is being exited: no new buys")
        if k in excluded:
            errors.append(f"{k} is excluded from trading")
        if side == "BUY" and i.get("status") == "candidate":
            notes.append(f"{k} is a candidate not yet held: this would be a first purchase")
        traded[k] = o["est_amount"] if side == "BUY" else -o["est_amount"]
        orders.append(o)
    r = _result(model, fund_id, 0.0, values, cash, traded, orders, table or {}, excluded, notes)
    r["errors"] = errors + r["errors"]
    r["rounding_residual"] = 0.0
    return r


# ------------------------------------------------------------------------------------------------ tranches
def validate_schedule(schedule: list[dict], trade_date: str, max_n: int = 24) -> list[str]:
    """Data checks for one tranche schedule [{date, pct}] (doc 17 item 9)."""
    from datetime import date as _d
    errs = []
    if not schedule:
        return ["Schedule is empty"]
    if len(schedule) > max_n:
        errs.append(f"At most {max_n} tranches")
    dates = []
    for n, t in enumerate(schedule, 1):
        try:
            d = _d.fromisoformat(str(t.get("date", ""))[:10])
        except ValueError:
            errs.append(f"Tranche {n}: date must look like 2026-11-12")
            continue
        if d.weekday() >= 5:
            errs.append(f"Tranche {n}: {d.isoformat()} is a weekend")
        if d.isoformat() < trade_date:
            errs.append(f"Tranche {n}: {d.isoformat()} is before the trade date {trade_date}")
        dates.append(d.isoformat())
        try:
            if float(t.get("pct")) <= 0:
                errs.append(f"Tranche {n}: percentage must be above zero")
        except (TypeError, ValueError):
            errs.append(f"Tranche {n}: percentage is not a number")
    if len(set(dates)) != len(dates):
        errs.append("Two tranches share a date")
    if dates != sorted(dates):
        errs.append("Dates must be in order")
    if not errs:
        tot = sum(float(t["pct"]) for t in schedule)
        if abs(tot - 100) > 0.01:
            errs.append(f"Percentages add up to {tot:.2f}%, not 100%")
    return errs


def split_order(order: dict, schedule: list[dict]) -> tuple[list[dict], list[str]]:
    """Split one parent order across a validated schedule. Quantities respect the security's lot size and the
    last tranche takes the remainder, so the tranches always add back to the parent exactly."""
    step = 1000.0 if order["quantity_type"] == "FACE" else 1.0 if order["quantity_type"] == "SHARES" else 0.001
    unit = order["price"] / (100 if order["quantity_type"] == "FACE" else 1)
    out, used, errs = [], 0.0, []
    for n, t in enumerate(schedule, 1):
        if n == len(schedule):
            q = round(order["quantity"] - used, 3)
        else:
            q = round(math.floor(order["quantity"] * float(t["pct"]) / 100 / step + 1e-9) * step, 3)
        used = round(used + q, 3)
        if q <= 0:
            errs.append(f"{order['instrument']}: tranche {n} would be empty (order too small to split this way)")
        out.append({"n": n, "date": str(t["date"])[:10], "pct": float(t["pct"]), "quantity": q,
                    "est_amount": round(q * unit, 2)})
    if abs(sum(x["quantity"] for x in out) - order["quantity"]) > 1e-6:
        errs.append(f"{order['instrument']}: tranches don't add back to the order")
    return out, errs


def asset_class_weights(model: TradingModel, rows: list[dict], key: str = "post_w") -> dict[str, float]:
    out = {a: 0.0 for a in model.policy.assets}
    for r in rows:
        out[r["asset_class"] or "cash"] = out.get(r["asset_class"] or "cash", 0.0) + r[key]
    return out
