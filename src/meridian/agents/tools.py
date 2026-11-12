"""Read-only tools the judgment agents can call (Agent SDK backend).

Every tool returns numbers computed by Meridian's deterministic code. Tools cannot change policy,
weights, rule results or the ledger: they only let an agent look closer before it decides. The
pipeline builds them per step from data already in memory, so a tool never reaches outside the run.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np


@dataclass
class ToolSpec:
    name: str
    description: str
    schema: dict                      # JSON Schema for the arguments
    fn: Callable[[dict], Any]         # returns JSON-serializable data


def _obj(props: dict | None = None, required: list | None = None) -> dict:
    return {"type": "object", "properties": props or {}, "required": required or [], "additionalProperties": False}


def _r(x, nd: int = 4):
    """Round floats (recursively) so tool results stay small and readable."""
    if isinstance(x, dict):
        return {str(k): _r(v, nd) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_r(v, nd) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else round(float(x), nd)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


# ------------------------------------------------------------------------------------------ macro
def macro_tools(macro: dict, detail: dict, classify: Callable[[dict], dict]) -> list[ToolSpec]:
    """``detail`` maps indicator -> {value, date, source, synthetic}."""
    def indicator_detail(a: dict):
        name = a.get("indicator")
        if name:
            if name not in detail:
                raise ValueError(f"unknown indicator {name!r}; known: {sorted(detail)}")
            return _r({name: detail[name]})
        return _r(detail)

    def rescore_regime(a: dict):
        ov = {k: float(v) for k, v in (a.get("overrides") or {}).items()}
        unknown = sorted(set(ov) - set(macro))
        if unknown:
            raise ValueError(f"unknown indicator(s) {unknown}; known: {sorted(macro)}")
        return _r({"baseline": classify(dict(macro)), "with_overrides": classify({**macro, **ov}), "overrides": ov,
                   "note": "What-if only. The recorded scores are the baseline."})

    return [
        ToolSpec("indicator_detail", "value, as-of date, source and synthetic flag for one indicator, or all if none named",
                 _obj({"indicator": {"type": "string"}}), indicator_detail),
        ToolSpec("rescore_regime", "re-run the rule-based regime classifier with some indicator values changed, to see "
                 "how close the call is to a boundary", _obj({"overrides": {"type": "object", "additionalProperties": {"type": "number"}}},
                                                             ["overrides"]), rescore_regime),
    ]


# ------------------------------------------------------------------------------------------ CMA judge
def cma_tools(asset: str, methods: dict, blend: Callable, validate: Callable, facts: dict, cross: dict) -> list[ToolSpec]:
    """``facts``: history/valuation/yield for this asset. ``cross``: {asset: {name, min, max, auto_blend}}."""
    lo, hi = min(methods.values()), max(methods.values())

    def blend_preview(a: dict):
        w = validate(a.get("weights"), methods)
        if not w:
            raise ValueError(f"weights must be non-negative numbers over {sorted(methods)} with a positive sum")
        raw = float(blend(methods, w))
        return _r({"normalized_weights": w, "blended_return": raw, "final_after_bound": float(np.clip(raw, lo, hi)),
                   "auto_blend": float(blend(methods)), "method_range": [lo, hi]})

    def asset_facts(_a: dict):
        return _r({"asset": asset, "methods": methods, "dispersion_pp": (hi - lo) * 100, **facts})

    def cross_section(_a: dict):
        return _r(cross)

    return [
        ToolSpec("blend_preview", "the expected return a set of method weights would produce, after the code's bound",
                 _obj({"weights": {"type": "object", "additionalProperties": {"type": "number"}}}, ["weights"]), blend_preview),
        ToolSpec("asset_facts", "this asset class's history, valuation or yield inputs and the dispersion of the methods",
                 _obj(), asset_facts),
        ToolSpec("cross_section", "method range and automatic blend for every asset class, to check relative ordering",
                 _obj(), cross_section),
    ]


# ------------------------------------------------------------------------------------------ CIO
def cio_tools(assets: list, names: dict, neutral, ens: dict, ens_eval: dict, ens_rules: dict, cand: dict,
              ranking: list, ballots: list) -> list[ToolSpec]:
    def _tilts(w):
        act = np.asarray(w) - np.asarray(neutral)
        order = np.argsort(act)
        row = lambda i: {"asset": names.get(assets[i], assets[i]), "weight": float(w[i]), "active": float(act[i])}  # noqa: E731
        return {"largest_overweights": [row(i) for i in order[::-1][:4] if act[i] > 1e-6],
                "largest_underweights": [row(i) for i in order[:4] if act[i] < -1e-6]}

    def ensemble_detail(a: dict):
        k = a.get("ensemble")
        if k not in ens:
            raise ValueError(f"unknown ensemble {k!r}; choose from {sorted(ens)}")
        e = ens_eval[k]
        return _r({"ensemble": k, "expected_return": e["exp_ret"], "volatility": e["vol"], "tracking_error": e["te"],
                   "effective_n": e["eff_n"], "compliance_summary": e["compliance"],
                   "rules_not_passing": [r for r in ens_rules.get(k, []) if r.get("status") not in ("PASS", "OFF")],
                   **_tilts(ens[k])})

    def candidate_detail(a: dict):
        k = a.get("method")
        if k not in cand:
            raise ValueError(f"unknown method {k!r}; choose from {sorted(cand)}")
        c = cand[k]
        rk = next(({"composite": float(s), "votes": int(p)} for m, s, p in ranking if m == k), {})
        return _r({"method": k, "family": c["family"], "expected_return": c["exp_ret"], "volatility": c["vol"],
                   "tracking_error": c["te"], "sharpe": c["sharpe"], "effective_n": c["eff_n"],
                   "max_drawdown": c["backtest"].get("max_drawdown"), "distance_to_consensus": c["dist_centroid"],
                   "compliance_summary": c["compliance"], **rk, **_tilts(c["w"])})

    def dissent(_a: dict):
        return _r({"ballots": ballots, "note": "Each method ranks the others through its own lens; bottom_flag is its dissent."})

    return [
        ToolSpec("ensemble_detail", "risk, return, largest tilts versus the glide path and any rule not passing for one ensemble",
                 _obj({"ensemble": {"type": "string", "enum": sorted(ens)}}, ["ensemble"]), ensemble_detail),
        ToolSpec("candidate_detail", "metrics, vote score and largest tilts for one construction method",
                 _obj({"method": {"type": "string", "enum": sorted(cand)}}, ["method"]), candidate_detail),
        ToolSpec("dissent", "the ballots from the review vote, including each method's bottom flag", _obj(), dissent),
    ]


# ------------------------------------------------------------------------------------------ compliance officer
def compliance_tools(vintages: dict, records: Callable[[], list]) -> list[ToolSpec]:
    def rule_results(a: dict):
        v = str(a.get("vintage"))
        by = {str(k): d for k, d in vintages.items()}
        if v not in by:
            raise ValueError(f"unknown vintage {v!r}; choose from {sorted(by)}")
        rows = by[v]["compliance"]
        st = a.get("status")
        if st:
            rows = [r for r in rows if r.get("status") == st]
        return _r({"vintage": v, "summary": by[v]["compliance_summary"], "rules": rows[:60]})

    def judgment_paths(_a: dict):
        out: dict = {}
        for r in records():
            p = (r.get("output") or {}).get("judge_path")
            if p:
                fam = r["step"].split(".")[-1] if r["step"].startswith("ac-") else r["step"]
                out.setdefault(fam, {}).setdefault(p, 0)
                out[fam][p] += 1
        return {"judgment_paths_by_step": out,
                "note": "agent or llm = a model made the judgment; offline = the deterministic policy was used."}

    def ledger_search(a: dict):
        q = str(a.get("step_contains") or "").lower()
        hits = [{"step": r["step"], "type": r["dr_type"], "actor": r["actor"].get("id"), "summary": r["summary"][:240]}
                for r in records() if q in r["step"].lower()]
        return {"matches": len(hits), "records": hits[:25]}

    return [
        ToolSpec("rule_results", "full rule results (rule, status, measured value, limit) for one vintage, optionally one status",
                 _obj({"vintage": {"type": "string"}, "status": {"type": "string", "enum": ["PASS", "WARN", "FAIL", "ATTEST", "OFF"]}},
                      ["vintage"]), rule_results),
        ToolSpec("judgment_paths", "how many judgments in this run were made by a model versus the deterministic fallback",
                 _obj(), judgment_paths),
        ToolSpec("ledger_search", "summaries of this run's ledger records whose step name contains some text",
                 _obj({"step_contains": {"type": "string"}}, ["step_contains"]), ledger_search),
    ]


# ------------------------------------------------------------------------------------------ strategy review
def _tilts(w, neutral, assets, names, n=4):
    act = np.asarray(w) - np.asarray(neutral)
    order = np.argsort(act)
    row = lambda i: {"asset": names.get(assets[i], assets[i]), "weight": float(w[i]), "active": float(act[i])}  # noqa: E731
    return {"largest_overweights": [row(i) for i in order[::-1][:n] if act[i] > 1e-6],
            "largest_underweights": [row(i) for i in order[:n] if act[i] < -1e-6]}


def _metrics(c: dict) -> dict:
    return {"expected_return": c["exp_ret"], "volatility": c["vol"], "tracking_error": c["te"], "sharpe": c["sharpe"],
            "effective_n": c["eff_n"], "max_drawdown": c["backtest"].get("max_drawdown"),
            "distance_to_consensus": c["dist_centroid"], "compliance_summary": c["compliance"]}


def deliberation_tools(ctx: dict, assets: list, names: dict) -> list[ToolSpec]:
    """Tools for the construction agents and the risk officer during the strategy review.

    ``ctx[vintage]`` = {"n": glide path, "cand": {method: candidate}}. Tools read the candidates as they
    stand when called, so a revision by one agent is visible to the next."""
    vs = {str(v): v for v in ctx}
    methods = sorted(next(iter(ctx.values()))["cand"])

    def _get(a, key="method"):
        v, k = str(a.get("vintage")), a.get(key)
        if v not in vs:
            raise ValueError(f"unknown vintage {v!r}; choose from {sorted(vs)}")
        if k not in methods:
            raise ValueError(f"unknown method {k!r}; choose from {methods}")
        return ctx[vs[v]], k

    def candidate_detail(a: dict):
        d, k = _get(a)
        c = d["cand"][k]
        return _r({"method": k, "vintage": str(a.get("vintage")), "family": c["family"], **_metrics(c),
                   "rules_not_passing": [r for r in c.get("rules", []) if r.get("status") not in ("PASS", "OFF")],
                   **_tilts(c["w"], d["n"], assets, names)})

    def compare_candidates(a: dict):
        d, k1 = _get(a, "method_a")
        _, k2 = _get(a, "method_b")
        c1, c2 = d["cand"][k1], d["cand"][k2]
        diff = np.asarray(c1["w"]) - np.asarray(c2["w"])
        order = np.argsort(-np.abs(diff))[:5]
        return _r({"vintage": str(a.get("vintage")), k1: _metrics(c1), k2: _metrics(c2),
                   "weight_overlap": float(np.minimum(c1["w"], c2["w"]).sum()),
                   "largest_weight_differences": [{"asset": names.get(assets[i], assets[i]), f"{k1}_minus_{k2}": float(diff[i])} for i in order]})

    vint = {"type": "string", "enum": sorted(vs)}
    meth = {"type": "string", "enum": methods}
    return [
        ToolSpec("candidate_detail", "one method's metrics, largest tilts versus the glide path and any rule not passing, for one vintage",
                 _obj({"method": meth, "vintage": vint}, ["method", "vintage"]), candidate_detail),
        ToolSpec("compare_candidates", "two methods side by side for one vintage: metrics, weight overlap and largest weight differences",
                 _obj({"method_a": meth, "method_b": meth, "vintage": vint}, ["method_a", "method_b", "vintage"]), compare_candidates),
    ]


def revision_tools(method: str, methods: list, ctx: dict, original: dict, apply: Callable, validate: Callable) -> list[ToolSpec]:
    """``preview_revision``: what a tilt scale and peer blend would do to this method's proposal, without changing it."""
    def preview_revision(a: dict):
        rev = validate(a, method, methods)
        if rev is None:
            raise ValueError("tilt_scale and blend_weight must be numbers")
        rows = {}
        for v, d in ctx.items():
            w = apply(original[v][method], d["n"], original[v].get(rev["blend_with"]), rev)
            rows[str(v)] = d["preview"](w)
        keys = ("expected_return", "volatility", "tracking_error", "sharpe")
        return _r({"applied": {k: rev[k] for k in ("tilt_scale", "blend_with", "blend_weight")},
                   "series_average": {k: float(np.mean([r[k] for r in rows.values()])) for k in keys},
                   "any_compliance_fail": any(r["compliance"]["FAIL"] for r in rows.values()), "by_vintage": rows,
                   "note": "Preview only. Values outside the allowed ranges were clamped as shown in 'applied'."})

    others = [m for m in methods if m != method]
    return [ToolSpec("preview_revision", "metrics and compliance your proposal would have after a tilt scale (0.5-1.0) and an optional "
                     "blend toward one peer (weight up to 0.5), for every vintage",
                     _obj({"tilt_scale": {"type": "number"}, "blend_with": {"type": "string", "enum": others + ["none"]},
                           "blend_weight": {"type": "number"}}, ["tilt_scale"]), preview_revision)]


# ------------------------------------------------------------------------------------------ output schemas
REGIMES = ["expansion", "late_cycle", "recession", "recovery"]

MACRO_SCHEMA = _obj({"regime": {"type": "string", "enum": REGIMES}, "confidence": {"type": "number"},
                     "rationale": {"type": "string"}}, ["regime", "confidence", "rationale"])

COMPLIANCE_SCHEMA = _obj({"narrative": {"type": "string"}, "recommended_actions": {"type": "array", "items": {"type": "string"}}},
                         ["narrative", "recommended_actions"])


def cma_schema(methods: dict) -> dict:
    return _obj({"weights": _obj({m: {"type": "number"} for m in methods}, sorted(methods)), "rationale": {"type": "string"}},
                ["weights", "rationale"])


def cio_schema(ensembles: list) -> dict:
    return _obj({"ensemble": {"type": "string", "enum": sorted(ensembles)}, "rationale": {"type": "string"},
                 "invalidation_conditions": {"type": "array", "items": {"type": "string"}}},
                ["ensemble", "rationale", "invalidation_conditions"])


THESIS_SCHEMA = _obj({"thesis": {"type": "string"}, "fits_regime": {"type": "string", "enum": ["well", "partly", "poorly"]},
                      "weaknesses": {"type": "array", "items": {"type": "string"}}}, ["thesis", "fits_regime", "weaknesses"])

MEMO_SCHEMA = _obj({"narrative": {"type": "string"}}, ["narrative"])


def cro_schema(methods: list) -> dict:
    item = _obj({"method": {"type": "string", "enum": sorted(methods)}, "comment": {"type": "string"},
                 "risk_flag": {"type": "string", "enum": ["none", "watch", "concern"]}}, ["method", "comment", "risk_flag"])
    return _obj({"overview": {"type": "string"}, "comments": {"type": "array", "items": item}}, ["overview", "comments"])


def review_schema(peers: list) -> dict:
    item = _obj({"peer": {"type": "string", "enum": sorted(peers)}, "assessment": {"type": "string"},
                 "concerns": {"type": "array", "items": {"type": "string"}}, "score": {"type": "integer"}},
                ["peer", "assessment", "concerns", "score"])
    return _obj({"reviews": {"type": "array", "items": item}}, ["reviews"])


def ballot_schema(others: list) -> dict:
    m = {"type": "string", "enum": sorted(others)}
    return _obj({"top": {"type": "array", "items": m}, "bottom_flag": m, "rationale": {"type": "string"}},
                ["top", "bottom_flag", "rationale"])


def revision_schema(others: list) -> dict:
    return _obj({"tilt_scale": {"type": "number"}, "blend_with": {"type": "string", "enum": sorted(others) + ["none"]},
                 "blend_weight": {"type": "number"}, "response_to_reviews": {"type": "string"}},
                ["tilt_scale", "blend_with", "blend_weight", "response_to_reviews"])
