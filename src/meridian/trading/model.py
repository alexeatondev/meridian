"""Product lines, funds, security master, example positions and target tables.

Three allocation strategies (product owner, 2026-11-10):
- previous_close: allocate in proportion to the fund's actual holdings at last close (keeps drift and tilts).
- neutral: allocate to the strategic glide-path weights, no tactical tilts.
- strategic: a separate, configurable table for a given trading day; it may follow the glide path or not.
Securities without a target are never part of cash allocation (doc 17 item 4).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import yaml

from .. import REPO_ROOT
from ..policy import Policy, load_policy

TRADING_PATH = REPO_ROOT / "config" / "trading.yaml"
STRATEGIES = {"previous_close": "Previous night close", "neutral": "Neutral (glide path)", "strategic": "Strategic"}
VEHICLES = {"mutual_fund": "Mutual funds", "cit": "CITs"}
ROLL_FREQS = ("monthly", "quarterly", "semiannual", "annual")
EXCHANGE_TRADED = ("etf", "stock", "bond")


def last_roll_date(as_of: date, freq: str) -> date:
    """The most recent glide-path roll-down date on or before `as_of` for a frequency (doc 17 item 16)."""
    if freq == "monthly":
        return date(as_of.year, as_of.month, 1)
    if freq == "quarterly":
        return date(as_of.year, 3 * ((as_of.month - 1) // 3) + 1, 1)
    if freq == "semiannual":
        return date(as_of.year, 1 if as_of.month < 7 else 7, 1)
    if freq == "annual":
        return date(as_of.year, 1, 1)
    raise ValueError(f"Unknown roll-down frequency: {freq}")


def year_frac(d: date) -> float:
    return d.year + (d.timetuple().tm_yday - 1) / 365.25


@dataclass
class Fund:
    id: str
    product: str
    product_name: str
    vehicle: str
    vintage: int
    account: str
    nav: float
    roll_down: str

    def as_dict(self) -> dict:
        return dict(self.__dict__, vehicle_name=VEHICLES[self.vehicle])


@dataclass
class TradingModel:
    raw: dict
    policy: Policy
    as_of: date
    funds: dict[str, Fund] = field(default_factory=dict)
    instruments: dict[str, dict] = field(default_factory=dict)

    # ----------------------------------------------------------------- reference data
    def fund_ids(self, vehicle: str = "all") -> list[str]:
        return [f.id for f in self.funds.values() if vehicle in ("all", "", None) or f.vehicle == vehicle]

    def fund_instruments(self, fund_id: str) -> list[dict]:
        f = self.funds[fund_id]
        return [i for i in self.instruments.values() if f.product in i["products"]]

    def has_target(self, inst: dict, fund_id: str) -> bool:
        return inst.get("status", "held") != "no_target" and self.share(inst, fund_id) > 0

    def share(self, inst: dict, fund_id: str) -> float:
        return float(inst.get("share", 0.0)) if self.funds[fund_id].product in inst["products"] else 0.0

    def route_for(self, inst: dict, routes: dict) -> str:
        return routes.get(inst["type"], "Internal trading desk")

    # ----------------------------------------------------------------- glide path and targets
    def neutral_asset_weights(self, fund_id: str, as_of: date | None = None) -> dict[str, float]:
        f = self.funds[fund_id]
        roll = last_roll_date(as_of or self.as_of, f.roll_down)
        w = self.policy.neutral_weights(f.vintage - year_frac(roll))
        return dict(zip(self.policy.assets, (float(x) for x in w)))

    def neutral_table(self, fund_id: str, as_of: date | None = None) -> dict[str, float]:
        aw = self.neutral_asset_weights(fund_id, as_of)
        out = {}
        for i in self.fund_instruments(fund_id):
            if self.has_target(i, fund_id):
                out[i["id"]] = aw[i["asset_class"]] * self.share(i, fund_id)
        tot = sum(out.values())
        return {k: v / tot for k, v in out.items() if v > 0}

    def previous_close_table(self, fund_id: str, positions: dict[str, float]) -> dict[str, float]:
        """Weights of actual holdings at last close, over securities that have a target."""
        inst = self.instruments
        out = {k: v for k, v in positions.items() if v > 0 and k in inst and self.has_target(inst[k], fund_id)}
        tot = sum(out.values())
        return {k: v / tot for k, v in out.items()} if tot > 0 else {}

    # ----------------------------------------------------------------- example positions (previous night close)
    def example_positions(self, fund_id: str) -> dict:
        """Deterministic example holdings at last close: neutral weights with a small drift, a legacy holding
        with no target, and uninvested cash. Replaced by custodian / transfer-agent position files."""
        f = self.funds[fund_id]
        seed = int(hashlib.sha256(fund_id.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        neutral = self.neutral_table(fund_id)
        cash_pct = float(self.raw.get("cash_account_pct", 0.006))
        drifted = {k: v * (1 + 0.025 * rng.standard_normal()) for k, v in neutral.items()}
        legacy = {i["id"]: float(i.get("legacy_pct", 0)) for i in self.fund_instruments(fund_id)
                  if i.get("status") == "no_target" and i.get("legacy_pct")}
        scale = (1 - cash_pct - sum(legacy.values())) / sum(drifted.values())
        weights = {k: v * scale for k, v in drifted.items()} | legacy
        values = {k: round(f.nav * w, 2) for k, w in weights.items()}
        return {"as_of": self.as_of.isoformat(), "cash": round(f.nav * cash_pct, 2), "values": values,
                "source": "Example positions (replace with custodian / transfer-agent files)"}


def load_model(path: Path = TRADING_PATH, policy: Policy | None = None) -> TradingModel:
    raw = yaml.safe_load(Path(path).read_text())
    policy = policy or load_policy()
    m = TradingModel(raw=raw, policy=policy, as_of=date.fromisoformat(str(raw["as_of"])))
    for i in raw["instruments"]:
        if i["asset_class"] not in policy.assets:
            raise ValueError(f"{i['id']}: unknown asset class {i['asset_class']}")
        m.instruments[i["id"]] = dict(i, status=i.get("status", "held"))
    for p in raw["products"]:
        if p["vehicle"] not in VEHICLES:
            raise ValueError(f"{p['id']}: vehicle must be one of {list(VEHICLES)}")
        for v in policy.vintages:
            freq = (p.get("roll_down_overrides") or {}).get(v, p.get("roll_down", "monthly"))
            if freq not in ROLL_FREQS:
                raise ValueError(f"{p['id']} {v}: roll-down must be one of {ROLL_FREQS}")
            fid = f"{p['fund_prefix']}-{v}"
            m.funds[fid] = Fund(id=fid, product=p["id"], product_name=p["name"], vehicle=p["vehicle"], vintage=v,
                                account=f"{p['account_prefix']}{v}", nav=float(p["nav_musd"][v]) * 1e6,
                                roll_down=freq)
    for p in raw["products"]:     # shares of each asset class must sum to 1 within a product line
        for ac in policy.assets:
            s = sum(float(i.get("share", 0)) for i in m.instruments.values()
                    if p["id"] in i["products"] and i["asset_class"] == ac and i["status"] != "no_target")
            if abs(s - 1) > 1e-6:
                raise ValueError(f"{p['id']}: instrument shares for {ac} sum to {s}, not 1")
    return m
