"""Product-line overview for the console: every fund (mutual fund and CIT) with its size, current holdings by
asset class, and its own glide path.

A run's proposal is per vintage and applies to both product lines. What differs between a vintage's mutual fund
and its CIT is the fund's size, its actual holdings at last close and its glide path (each product line rolls
down on its own schedule, and approved glide-path adjustments can apply to one line only).

The console builds this from example data when it runs offline. The hosted app passes positions and glide paths
from its database (uploaded or booked positions, approved glide-path adjustments).
"""
from __future__ import annotations

from typing import Callable

from .model import VEHICLES, TradingModel, load_model


def _holdings_by_asset(m: TradingModel, p: dict) -> tuple[dict[str, float], float, float]:
    """Asset-class weights of a fund's holdings over NAV. Uninvested cash counts toward the cash asset class
    and is also returned on its own. Returns (weights, nav, uninvested share)."""
    nav = float(p.get("cash", 0.0)) + sum(float(v) for v in p.get("values", {}).values())
    out: dict[str, float] = {}
    if nav <= 0:
        return out, 0.0, 0.0
    for iid, val in p.get("values", {}).items():
        inst = m.instruments.get(iid)
        if inst and val:
            out[inst["asset_class"]] = out.get(inst["asset_class"], 0.0) + float(val) / nav
    unc = float(p.get("cash", 0.0)) / nav
    if "cash" in m.policy.assets:
        out["cash"] = out.get("cash", 0.0) + unc
    return out, nav, unc


def product_overview(m: TradingModel | None = None, positions_fn: Callable[[str], dict] | None = None,
                     glide_fn: Callable[[str], dict] | None = None, glide_state: dict | None = None,
                     example: bool = True) -> dict:
    m = m or load_model()
    positions_fn = positions_fn or m.example_positions
    products = [{"id": p["id"], "name": p["name"], "vehicle": p["vehicle"], "vehicle_name": VEHICLES[p["vehicle"]],
                 "fund_prefix": p["fund_prefix"], "roll_down": p.get("roll_down", "")} for p in m.raw.get("products", [])]
    funds = []
    for fid, f in m.funds.items():
        p = positions_fn(fid)
        current, nav, unc = _holdings_by_asset(m, p)
        ips = m.neutral_asset_weights(fid)
        glide = glide_fn(fid) if glide_fn else ips
        funds.append({"id": fid, "product": f.product, "product_name": f.product_name, "vehicle": f.vehicle,
                      "vintage": f.vintage, "roll_down": f.roll_down, "nav": nav, "uninvested_cash": unc,
                      "current": current, "glide": glide, "ips_glide": ips,
                      "glide_adjusted": any(abs(glide.get(a, 0.0) - ips.get(a, 0.0)) > 1e-9 for a in m.policy.assets),
                      "positions_source": p.get("source", ""), "positions_as_of": p.get("as_of", "")})
    return {"as_of": m.as_of.isoformat(), "products": products, "funds": funds, "example_data": example,
            "glide": glide_state or {"adjustments": [], "requests": []}}
