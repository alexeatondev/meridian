"""Deterministic compliance rule engine.

The ONLY component allowed to determine PASS/WARN/FAIL. LLM agents (incl. the agentic
compliance officer) may explain results but can never change them.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from ..analytics.core import port_vol, tracking_error
from ..entities import EffectiveRegime
from ..policy import Policy


@dataclass
class RuleResult:
    rule_id: str
    kind: str
    status: str          # PASS | WARN | FAIL | ATTEST | OFF
    measured: float | str | None
    limit: float | str | None
    severity: str
    ips: str
    detail: str = ""

    def to_dict(self):
        return asdict(self)


def evaluate(weights: np.ndarray, neutral: np.ndarray, cov: np.ndarray, policy: Policy,
             regime: EffectiveRegime, universe: dict[str, dict],
             attestations: dict[str, bool] | None = None, risk_budget: float | None = None,
             band_neutral: np.ndarray | None = None) -> list[RuleResult]:
    """`neutral` is the glide path the portfolio is managed against (tracking error, risk budget, volatility).
    `band_neutral` is the IPS glide path that the IPS bands are measured from; it differs from `neutral` only
    when the Investment Committee has approved a glide-path adjustment inside the bands."""
    w, n = np.asarray(weights, float), np.asarray(neutral, float)
    nb = n if band_neutral is None else np.asarray(band_neutral, float)
    assets = policy.assets
    attestations = attestations or {}
    out: list[RuleResult] = []

    def res(rule, ok, measured, limit, detail=""):
        status = "PASS" if ok else ("FAIL" if rule["severity"] == "hard" else "WARN")
        out.append(RuleResult(rule["id"], rule["kind"], status,
                              None if measured is None else (round(measured, 6) if isinstance(measured, float) else measured),
                              limit, rule["severity"], rule.get("ips", ""), detail))

    for rule in policy.rules:
        if not regime.rule_enabled(rule["id"], rule.get("applies_to_regimes")):
            out.append(RuleResult(rule["id"], rule["kind"], "OFF", None, None, rule["severity"], rule.get("ips", ""),
                                  "Not applicable to selected entity types"))
            continue
        k = rule["kind"]
        if k == "sum_to_one":
            res(rule, abs(w.sum() - 1) <= rule["tolerance"], float(w.sum()), 1.0)
        elif k == "long_only":
            res(rule, (w >= -1e-9).all(), float(w.min()), 0.0)
        elif k == "band_vs_neutral":
            dev = np.abs(w - nb) * 100
            i = int(dev.argmax())
            res(rule, dev.max() <= rule["per_asset_pp"] + 1e-6, float(dev.max()), rule["per_asset_pp"],
                f"largest deviation: {assets[i]}")
        elif k == "group_band_vs_neutral":
            m = policy.group_mask(rule["group"])
            dev = abs(m @ w - m @ nb) * 100
            res(rule, dev <= rule["pp"] + 1e-6, float(dev), rule["pp"], f"{rule['group']} {m @ w:.1%} vs IPS glide path {m @ nb:.1%}")
        elif k == "group_max":
            m = policy.group_mask(rule["group"])
            res(rule, m @ w <= rule["max"] + 1e-9, float(m @ w), rule["max"])
        elif k == "group_share_of_group_max":
            m, of = policy.group_mask(rule["group"]), policy.group_mask(rule["of"])
            share = float((m @ w) / (of @ w)) if of @ w > 0 else 0.0
            res(rule, share <= rule["max"] + 1e-9, share, rule["max"])
        elif k == "asset_max":
            v = float(w[assets.index(rule["asset"])])
            res(rule, v <= rule["max"] + 1e-9, v, rule["max"])
        elif k == "asset_max_all":
            res(rule, w.max() <= rule["max"] + 1e-9, float(w.max()), rule["max"], f"largest: {assets[int(w.argmax())]}")
        elif k == "tracking_error_max":
            te = tracking_error(w, n, cov)
            res(rule, te <= rule["max"] + 1e-9, te, rule["max"])
        elif k == "risk_budget_max":
            te = tracking_error(w, n, cov)
            lim = risk_budget if risk_budget is not None else float(policy.raw["risk_objectives"]["tracking_error_budget_vs_neutral"])
            res(rule, te <= lim + 1e-9, te, lim, f"{te / lim:.0%} of risk budget used" if lim else "")
        elif k == "volatility_vs_neutral":
            ratio = port_vol(w, cov) / port_vol(n, cov)
            res(rule, ratio <= rule["max_ratio"], float(ratio), rule["max_ratio"])
        elif k == "liquidity_all":
            bad = [a for a, x in zip(assets, w) if x > 1e-6 and universe[a].get("liquidity") not in rule["allowed"]]
            res(rule, not bad, ",".join(bad) or "none", ",".join(rule["allowed"]))
        elif k == "illiquid_max":
            v = float(sum(x for a, x in zip(assets, w) if universe[a].get("liquidity") == "illiquid"))
            res(rule, v <= rule["max"], v, rule["max"])
        elif k == "derivatives_exposure_max":
            # Pilot proxy: building-block funds that use derivatives (FX hedges, commodity futures)
            # count at a conservative 100% gross notional of their weight. Replace with look-through
            # notional from fund holdings when available.
            v = float(sum(x for a, x in zip(assets, w) if universe[a].get("uses_derivatives")))
            res(rule, v <= rule["max"] + 1e-9, v, rule["max"], "proxy: full weight of derivative-using funds")
        elif k == "attestation":
            ok = attestations.get(rule["id"])
            out.append(RuleResult(rule["id"], k, "PASS" if ok else "ATTEST", None, None, rule["severity"],
                                  rule.get("ips", ""), rule["text"] + ("" if ok else " — awaiting human attestation")))
        else:
            out.append(RuleResult(rule["id"], k, "FAIL", None, None, "hard", rule.get("ips", ""), "Unknown rule kind"))
    return out


def summarize(results: list[RuleResult]) -> dict:
    counts = {s: sum(r.status == s for r in results) for s in ("PASS", "WARN", "FAIL", "ATTEST", "OFF")}
    counts["overall"] = ("FAIL" if counts["FAIL"] else "WARN" if counts["WARN"]
                         else "PASS (attestations pending)" if counts["ATTEST"] else "PASS")
    return counts
