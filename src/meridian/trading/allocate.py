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
        amt = _amount(inst[k], q)
        signed = amt if side == "BUY" else -amt
        traded[k] = signed
        orders.append({"instrument": k, "name": inst[k]["name"], "type": inst[k]["type"],
                       "asset_class": inst[k]["asset_class"], "side": side, "quantity": q,
                       "quantity_type": "FACE" if inst[k]["type"] == "bond" else "SHARES" if inst[k]["type"] in ("etf", "stock") else "UNITS",
                       "price": float(inst[k]["price"]), "est_amount": amt, "route": model.route_for(inst[k], routes)})

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


def asset_class_weights(model: TradingModel, rows: list[dict], key: str = "post_w") -> dict[str, float]:
    out = {a: 0.0 for a in model.policy.assets}
    for r in rows:
        out[r["asset_class"] or "cash"] = out.get(r["asset_class"] or "cash", 0.0) + r[key]
    return out
