"""Target-date series pipeline (pilot).

Adapts the paper's SAA pipeline (macro -> CMAs -> covariance -> competing PC agents -> peer review &
Borda vote -> CRO -> CIO ensemble -> board memo) to a glide-path fund-of-funds series, and wraps it in
Meridian's governance layer (entity regimes, compliance engine, compliance-officer agent, ledger,
human approval gate).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .. import REPO_ROOT
from ..agents import LLMBackend, actor, load_agent
from ..analytics import core as A
from ..analytics.optimizers import PC_METHODS, Bounds, adversarial_diversifier
from ..compliance import evaluate, summarize
from ..data import DataRegistry, Request, snapshot, to_wide_returns
from ..entities import resolve
from ..ledger import Ledger, verify
from ..policy import load_policy, load_universe

SYSTEM = {"kind": "system", "id": "orchestrator", "version": "0.1.0"}


@dataclass
class RunResult:
    run_id: str
    out_dir: Path
    vintages: dict
    memo_path: Path
    compliance_report_path: Path
    ledger_ok: tuple


# ------------------------------------------------------------------------------------------ macro
def classify_regime(m: dict) -> dict:
    # activity term: ISM-style PMI if a source provides it, else Chicago Fed National Activity Index (3m avg)
    activity = (m["pmi"] - 50) / 5 if "pmi" in m else (m.get("cfnai_ma3", 0.0) / 0.5)
    growth = np.clip((m["real_gdp_growth_yoy"] - 2.0) / 1.5 + activity - m["unemployment_change_6m"] / 0.5, -2, 2)
    inflation = np.clip((m["core_cpi_yoy"] - 2.0) / 1.0, -2, 2)
    policy = np.clip(-m["policy_rate_change_6m"] / 0.5, -2, 2)          # + = easing
    fin = np.clip(-(m["hy_spread_bp"] - 400) / 150, -2, 2)              # + = loose
    if growth < -1.0 and fin < 0:
        regime = "recession"
    elif growth < 0 and (inflation > 0.5 or policy > 0):
        regime = "late_cycle"
    elif growth >= 0 and policy > 0 and inflation <= 0.5:
        regime = "recovery"
    else:
        regime = "expansion"
    conf = float(np.clip(0.5 + 0.12 * abs(growth) + 0.08 * abs(inflation), 0.5, 0.9))
    return {"regime": regime, "confidence": round(conf, 2),
            "scores": {"growth": round(float(growth), 2), "inflation": round(float(inflation), 2),
                       "monetary_policy": round(float(policy), 2), "financial_conditions": round(float(fin), 2)}}


# ------------------------------------------------------------------------------------------ CMA judge
def offline_cma_judge(asset: str, methods: dict, regime: str, valuation_row) -> tuple[dict, str]:
    """Deterministic implementation of skills/cma-judge rules (used when no LLM is configured)."""
    if "yield_based" in methods:
        w = {"yield_based": 0.6, "regime_adjusted": 0.2, "equilibrium": 0.1, "historical": 0.1}
        why = "Fixed income/cash: starting yield net of expected credit loss is the dominant predictor of 10y returns."
    else:
        cape = valuation_row["cape"] if valuation_row is not None else 20
        if cape > 28:
            w = {"building_block": 0.35, "cape_yield": 0.25, "equilibrium": 0.2, "regime_adjusted": 0.15, "historical": 0.05}
            why = f"Valuations stretched (CAPE≈{cape:.0f}): tilt to valuation-based methods; historical ERP down-weighted."
        elif cape < 16:
            w = {"historical": 0.3, "equilibrium": 0.3, "building_block": 0.25, "cape_yield": 0.15}
            why = f"Valuations cheap (CAPE≈{cape:.0f}): tilt to historical and equilibrium methods."
        else:
            w = {"building_block": 0.3, "equilibrium": 0.25, "historical": 0.2, "regime_adjusted": 0.15, "cape_yield": 0.1}
            why = f"Valuations near normal (CAPE≈{cape:.0f}): balanced blend."
        if regime in ("late_cycle", "recession"):
            w["regime_adjusted"] = w.get("regime_adjusted", 0) + 0.05
            why += f" {regime.replace('_', '-')} regime: +5% weight to regime-adjusted estimate."
    w = {k: v for k, v in w.items() if k in methods}
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}, why


def validate_weights(raw, methods: dict) -> dict | None:
    """Accept an LLM's method weights only if they are numeric, non-negative, over known methods and sum > 0."""
    if not isinstance(raw, dict):
        return None
    w = {}
    for k, v in raw.items():
        if k not in methods:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            return None
        if not np.isfinite(x) or x < 0:
            return None
        w[k] = x
    tot = sum(w.values())
    return {k: v / tot for k, v in w.items()} if tot > 0 else None


# ------------------------------------------------------------------------------------------ voting
def lens_score(lens: str, c: dict) -> float:
    if lens == "heuristic":
        return -c["te"]
    if lens == "return_optimized":
        return c["sharpe"]
    if lens == "risk_structured":
        return -c["vol"] + 0.002 * c["eff_n"]
    if lens == "adversarial":
        return c["dist_centroid"]
    return 0.0


def borda_vote(cands: dict, top_k: int = 3) -> tuple[dict, list]:
    points = {k: 0 for k in cands}
    ballots = []
    for voter, cv in cands.items():
        others = [k for k in cands if k != voter]
        ranked = sorted(others, key=lambda k: lens_score(cv["family"], cands[k]), reverse=True)
        for i, k in enumerate(ranked[:top_k]):
            points[k] += top_k - i
        points[ranked[-1]] -= 2
        ballots.append({"voter": voter, "lens": cv["family"], "top": ranked[:top_k], "bottom_flag": ranked[-1]})
    return points, ballots


def _norm(x: np.ndarray) -> np.ndarray:
    return (x - x.min()) / (x.max() - x.min()) if x.max() > x.min() else np.ones_like(x) * 0.5


# ------------------------------------------------------------------------------------------ main
def run(as_of: str = "2026-10-31", selected_entities: list[str] | None = None,
        attestations: dict | None = None, out_root: Path | None = None,
        source_overrides: dict | None = None, positions_path: Path | None = None) -> RunResult:
    regime_cfg = resolve(selected_entities)
    policy, universe = load_policy(), load_universe()
    assets = policy.assets
    as_of_ts = pd.Timestamp(as_of)
    as_of_frac = as_of_ts.year + (as_of_ts.dayofyear - 1) / 365.25
    run_id = f"run_tds_{as_of_ts:%Y%m%d}_{uuid.uuid4().hex[:6]}"
    out = Path(out_root or REPO_ROOT / "runs") / run_id
    out.mkdir(parents=True, exist_ok=True)
    L = Ledger(out / "ledger.jsonl")
    llm = LLMBackend()
    pv = policy.id

    # 0. preflight ---------------------------------------------------------------------------
    L.record(dr_type="decision", run_id=run_id, step="preflight.entity_regime", actor=SYSTEM, policy_version=pv,
             summary=f"Entities {regime_cfg.selected}; retention {regime_cfg.retention_years}y; mode {regime_cfg.operating_mode}; autonomy {regime_cfg.autonomy_level}",
             output={"obligations": [o["id"] for o in regime_cfg.obligations], "reports": regime_cfg.reports,
                     "production_blockers": regime_cfg.production_blockers})

    # 1. data ----------------------------------------------------------------------------------
    reg = DataRegistry.from_config(overrides=source_overrides)
    ulist = [universe[a] for a in assets]
    res = {
        "returns.monthly": reg.get(Request("returns.monthly", ulist, start="1999-01-31", end=as_of)),
        "macro.indicators": reg.get(Request("macro.indicators", ulist, as_of=as_of)),
        "fundamentals.valuation": reg.get(Request("fundamentals.valuation", ulist, as_of=as_of)),
        "yields.current": reg.get(Request("yields.current", ulist, as_of=as_of)),
    }
    snap = snapshot(res, out / "snapshot")
    synthetic = any(r.synthetic for r in res.values())
    synthetic_detail = {ds: r.notes for ds, r in res.items() if r.synthetic}
    snap_dr = L.record(dr_type="signal", run_id=run_id, step="data.snapshot", actor=SYSTEM, policy_version=pv,
                       summary=f"Snapshot {snap['snapshot_id']} " + (f"(partly SYNTHETIC: {', '.join(synthetic_detail)})" if synthetic else "(no synthetic data)"),
                       output=snap, data_flags={"synthetic": synthetic, "synthetic_detail": synthetic_detail, "routing_attempts": reg.attempts})
    rets = to_wide_returns(res["returns.monthly"].frame, assets)
    macro = dict(zip(res["macro.indicators"].frame["indicator"], res["macro.indicators"].frame["value"]))
    val, yl = res["fundamentals.valuation"].frame, res["yields.current"].frame
    rf = float(yl.set_index("asset_id").loc["cash", "yield"]) if "cash" in set(yl["asset_id"]) else 0.0385
    inflation = macro.get("cpi_yoy", 2.5) / 100

    # 2. macro regime agent ----------------------------------------------------------------------
    spec = load_agent("macro-regime", ["macro-regime"])
    mv = classify_regime(macro)
    llm_mv = llm.judge(spec, "Review the deterministic regime classification. You may confirm it or choose another of "
                       "[expansion, late_cycle, recession, recovery] with rationale.", {"indicators": macro, "scored": mv},
                       '{"regime": str, "confidence": float, "rationale": str}')
    if llm_mv and llm_mv.get("regime") in ("expansion", "late_cycle", "recession", "recovery"):
        try:
            conf = float(np.clip(float(llm_mv.get("confidence", mv["confidence"])), 0, 1))
        except (TypeError, ValueError):
            conf = mv["confidence"]
        mv.update(regime=llm_mv["regime"], confidence=conf, rationale=str(llm_mv.get("rationale", ""))[:2000],
                  rule_based_regime=mv["regime"], judge_path="llm")
    else:
        mv["judge_path"] = "offline"
        mv["rationale"] = (f"Growth score {mv['scores']['growth']}, inflation {mv['scores']['inflation']}, "
                           f"policy {mv['scores']['monetary_policy']}, financial conditions {mv['scores']['financial_conditions']} "
                           f"→ {mv['regime']} (rule-based classifier).")
    macro_dr = L.record(dr_type="signal", run_id=run_id, step="macro-regime", actor=actor(spec, llm), policy_version=pv,
                        inputs=[snap_dr], summary=f"Regime: {mv['regime']} (confidence {mv['confidence']})",
                        output=mv, rationale=mv["rationale"])

    # 3. covariance agent -------------------------------------------------------------------------
    cov, shrink = A.ledoit_wolf_cov(rets)
    stats = A.annual_stats(rets)
    cov_dr = L.record(dr_type="signal", run_id=run_id, step="covariance", actor=SYSTEM, policy_version=pv,
                      inputs=[snap_dr], summary=f"Ledoit-Wolf covariance, shrinkage {shrink:.2f}, {len(rets)} months",
                      output={"vols": dict(zip(assets, np.sqrt(np.diag(cov)).round(4)))})

    # 4. asset-class agents + CMA judge -----------------------------------------------------------
    series_neutral = np.mean([policy.neutral_weights(v - as_of_frac) for v in policy.vintages], axis=0)
    cands = A.cma_candidates(assets, stats, cov, series_neutral, val, yl, rf, inflation, mv["regime"])
    judge_spec = load_agent("asset-class-analyst", ["cma-judge"])
    vrow = val.set_index("asset_id")
    mu, cma_table, cma_drs = [], [], []
    for a in assets:
        m = cands[a]
        lo, hi = min(m.values()), max(m.values())
        llm_j = llm.judge(judge_spec, f"Select the final 10-year expected return for {universe[a]['name']}.",
                          {"methods": m, "regime": mv, "valuation": vrow.loc[a].to_dict() if a in vrow.index else None},
                          '{"weights": {method: float}, "rationale": str}')
        w = validate_weights(llm_j.get("weights") if llm_j else None, m)
        if w:
            why, path = str(llm_j.get("rationale", ""))[:2000], "llm"
        else:
            w, why = offline_cma_judge(a, m, mv["regime"], vrow.loc[a] if a in vrow.index else None)
            path = "offline"
        final = float(np.clip(A.auto_blend(m, w), lo, hi))          # hard bound: within method range
        blend = A.auto_blend(m)
        mu.append(final)
        cma_table.append({"asset": a, "name": universe[a]["name"], **{k: round(v, 4) for k, v in m.items()},
                          "auto_blend": round(blend, 4), "judge": round(final, 4), "judge_minus_blend": round(final - blend, 4),
                          "vol": round(float(np.sqrt(cov[assets.index(a), assets.index(a)])), 4)})
        cma_drs.append(L.record(dr_type="decision", run_id=run_id, step=f"ac-{a}.cma-judge", actor=actor(judge_spec, llm),
                                policy_version=pv, inputs=[macro_dr, cov_dr, snap_dr], portfolio_scope=[a],
                                summary=f"{universe[a]['name']}: E[r] {final:.2%} (auto-blend {blend:.2%})",
                                output={"expected_return": final, "weights": w, "judge_path": path},
                                rationale=why, alternatives=[{"option": k, "value": v} for k, v in m.items()],
                                constraints_checked=[{"rule_id": "CMA-BOUND", "result": "PASS", "range": [lo, hi]}]))
    mu = np.array(mu)

    # 5. per-vintage portfolio construction, review, CIO -----------------------------------------
    eq_m, nonus_m = policy.group_mask("equity"), policy.group_mask("non_us_equity")
    big_m = policy.group_mask("below_ig")
    cash_m = np.array([a == "cash" for a in assets], float)
    deriv_m = np.array([bool(universe[a].get("uses_derivatives")) for a in assets], float)
    te_budget = policy.raw["risk_objectives"]["tracking_error_budget_vs_neutral"] * 0.96
    ldu_on = regime_cfg.rule_enabled("DERIV-LDU", ["registered_fund", "cftc_derivatives"])
    vint_out = {}
    cio_spec, cro_spec = load_agent("cio", ["ensemble-methods"]), load_agent("cro")
    pc_spec = load_agent("pc-agent", ["peer-review"])
    for v in policy.vintages:
        ytt = v - as_of_frac
        n = policy.neutral_weights(ytt)
        rb = policy.risk_budget(v)
        neq = eq_m @ n
        groups = [(eq_m, neq - 0.05, neq + 0.05), (policy.group_mask("growth_assets"), policy.group_mask("growth_assets") @ n - 0.05,
                  policy.group_mask("growth_assets") @ n + 0.05), (big_m, 0, 0.10), (cash_m, 0, 0.25),
                  (nonus_m - 0.45 * eq_m, -1, 0)]
        if ldu_on:
            groups.append((deriv_m, 0, 0.10))
        b = Bounds(lo=np.maximum(n - 0.03, 0), hi=np.minimum(n + 0.03, 0.5), group_masks=groups, te_max=min(te_budget, rb * 0.96))
        cand = {}
        for name, (fam, fn) in PC_METHODS.items():
            w, status = fn(mu, cov, n, b)
            cand[name] = {"family": fam, "w": w, "status": status}
        centroid = np.mean([c["w"] for c in cand.values()], axis=0)
        w, status = adversarial_diversifier(mu, cov, n, b, centroid=centroid, rf=rf)
        cand["adversarial_diversifier"] = {"family": "adversarial", "w": w, "status": status}
        centroid = np.mean([c["w"] for k, c in cand.items() if k != "adversarial_diversifier"], axis=0)

        # CRO risk report (neutral assessor; does not vote)
        for k, c in cand.items():
            wv = c["w"]
            bt = A.historical_backtest(wv, rets)
            comp = evaluate(wv, n, cov, policy, regime_cfg, universe, attestations, risk_budget=rb)
            c.update(exp_ret=float(mu @ wv), vol=A.port_vol(wv, cov), te=A.tracking_error(wv, n, cov),
                     eff_n=A.effective_n(wv), backtest=bt, compliance=summarize(comp),
                     dist_centroid=float(np.abs(wv - centroid).sum()))
            c["sharpe"] = (c["exp_ret"] - rf) / c["vol"]
            L.record(dr_type="signal", run_id=run_id, step=f"pc-{k}.proposal", actor={**actor(pc_spec, llm), "id": f"pc-{k}"},
                     policy_version=pv, inputs=cma_drs[:1] + [cov_dr], portfolio_scope=[f"MTRS-{v}"],
                     summary=f"{v}: {k} E[r] {c['exp_ret']:.2%}, vol {c['vol']:.2%}, TE {c['te']:.2%}; compliance {c['compliance']['overall']}",
                     output={"weights": dict(zip(assets, np.round(c["w"], 4))), "solver": c["status"]})
        cro_dr = L.record(dr_type="signal", run_id=run_id, step="cro.risk-report", actor=actor(cro_spec, llm),
                          policy_version=pv, portfolio_scope=[f"MTRS-{v}"],
                          summary=f"{v}: risk report on {len(cand)} candidates",
                          output={k: {x: (c[x] if x != "backtest" else c[x]) for x in ("exp_ret", "vol", "te", "eff_n", "backtest", "compliance")} for k, c in cand.items()})

        # peer review & modified Borda vote, blended with metric composite
        points, ballots = borda_vote(cand)
        keys = list(cand)
        metric = (0.30 * _norm(np.array([cand[k]["sharpe"] for k in keys])) +
                  0.25 * _norm(-np.array([cand[k]["te"] for k in keys])) +
                  0.20 * _norm(np.array([cand[k]["backtest"]["max_drawdown"] for k in keys])) +
                  0.15 * _norm(np.array([cand[k]["eff_n"] for k in keys])) +
                  0.10 * np.array([1.0 if cand[k]["compliance"]["FAIL"] == 0 else 0.0 for k in keys]))
        vote_w = 0.4 if mv["regime"] in ("late_cycle", "recession") else 0.5
        composite = vote_w * _norm(np.array([points[k] for k in keys], float)) + (1 - vote_w) * metric
        ranking = sorted(zip(keys, composite, [points[k] for k in keys]), key=lambda x: -x[1])
        dissent = [{"candidate": b_["bottom_flag"], "flagged_by": b_["voter"], "lens": b_["lens"]} for b_ in ballots]
        vote_dr = L.record(dr_type="decision", run_id=run_id, step="pc-review.borda-vote", actor=SYSTEM,
                           policy_version=pv, inputs=[cro_dr], portfolio_scope=[f"MTRS-{v}"],
                           summary=f"{v}: top = {ranking[0][0]}; vote weight {vote_w}",
                           output={"ranking": [{"method": k, "composite": round(float(s), 3), "votes": p} for k, s, p in ranking],
                                   "ballots": ballots, "seed": "deterministic-lens"}, dissent=dissent)

        # CIO agent: ensemble selection
        eligible = [k for k in keys if cand[k]["compliance"]["FAIL"] == 0]
        ens = {}
        W = np.array([cand[k]["w"] for k in eligible])
        ens["simple_average"] = W.mean(0)
        # paper §4.4: weight methods by inverse tracking error to the ensemble centroid (floor 25bp)
        ctr = W.mean(0)
        inv_te = np.array([1 / max(A.tracking_error(cand[k]["w"], ctr, cov), 0.0025) for k in eligible])
        ens["inverse_tracking_error"] = (W * (inv_te / inv_te.sum())[:, None]).sum(0)
        cs = np.array([dict((k, s) for k, s, _ in ranking)[k] for k in eligible]) + 1e-6
        ens["composite_score_weighted"] = (W * (cs / cs.sum())[:, None]).sum(0)
        ens["top_ranked_single"] = cand[[k for k, _, _ in ranking if k in eligible][0]]["w"]
        ens_eval = {}
        for k, wv in ens.items():
            wv = wv / wv.sum()
            ens[k] = wv
            ens_eval[k] = {"exp_ret": float(mu @ wv), "vol": A.port_vol(wv, cov), "te": A.tracking_error(wv, n, cov),
                           "eff_n": A.effective_n(wv), "compliance": summarize(evaluate(wv, n, cov, policy, regime_cfg, universe, attestations, risk_budget=rb))}
        llm_c = llm.judge(cio_spec, f"Choose the ensemble method for the {v} vintage.",
                          {"regime": mv, "ensembles": ens_eval, "ranking": ranking[:5]},
                          '{"ensemble": str, "rationale": str, "invalidation_conditions": [str]}')
        if llm_c and llm_c.get("ensemble") in ens and ens_eval[llm_c["ensemble"]]["compliance"]["FAIL"] == 0:
            choice, why = llm_c["ensemble"], str(llm_c.get("rationale", ""))[:3000]
            invalid = [str(c)[:300] for c in (llm_c.get("invalidation_conditions") or []) if isinstance(c, (str, int, float))][:8]
            if not invalid:
                invalid = [f"Macro regime shifts away from {mv['regime'].replace('_', '-')}"]
        else:
            choice = "inverse_tracking_error"
            why = ("Inverse-tracking-error ensemble (paper §4.4): weights methods closer to the consensus more heavily, "
                   "keeps every method's information, and stays well inside the TE budget; individual optimizers are "
                   "sensitive to CMA error in a " + mv["regime"].replace("_", "-") + " regime.")
            invalid = [f"Macro regime shifts away from {mv['regime'].replace('_', '-')}",
                       "Any CMA moves outside its method range on the next run",
                       "Equity drawdown > 15% from run date (off-cycle review trigger)",
                       "Tracking error vs. glide path rises above 1.0% (warning threshold)"]
        final = ens[choice]
        comp = evaluate(final, n, cov, policy, regime_cfg, universe, attestations, risk_budget=rb)
        summ = summarize(comp)
        bt = A.historical_backtest(final, rets)
        bt_n = A.historical_backtest(n, rets)
        cio_dr = L.record(dr_type="decision", run_id=run_id, step="cio.ensemble", actor=actor(cio_spec, llm),
                          policy_version=pv, inputs=[vote_dr, cro_dr, macro_dr], portfolio_scope=[f"MTRS-{v}"],
                          summary=f"{v}: {choice}; equity {eq_m @ final:.1%} vs neutral {neq:.1%}; compliance {summ['overall']}",
                          output={"weights": dict(zip(assets, np.round(final, 4))), "ensemble": choice,
                                  "invalidation_conditions": invalid},
                          rationale=why, alternatives=[{"option": k, **{x: round(y, 4) for x, y in e.items() if x != 'compliance'}} for k, e in ens_eval.items()],
                          constraints_checked=[r.to_dict() for r in comp], dissent=dissent)
        approvers = policy.raw["approvals"]["tactical_tilt"]
        approvers = sorted(set(approvers) | set(regime_cfg.approval_overrides.get("rebalance_material", [])))
        L.record(dr_type="approval", run_id=run_id, step="approval.pending", actor=SYSTEM, policy_version=pv,
                 inputs=[cio_dr], portfolio_scope=[f"MTRS-{v}"],
                 summary=f"{v}: proposal awaiting human approval by {approvers}" + ("; BLOCKED by FAIL" if summ["FAIL"] else ""),
                 approvals=[{"role": r, "status": "pending"} for r in approvers])
        vint_out[v] = {"years_to_target": round(ytt, 2), "neutral": dict(zip(assets, np.round(n, 4))),
                       "final": dict(zip(assets, np.round(final, 4))), "ensemble": choice, "rationale": why,
                       "invalidation_conditions": invalid, "equity_neutral": float(neq), "equity_final": float(eq_m @ final),
                       "exp_ret": float(mu @ final), "vol": A.port_vol(final, cov), "te": A.tracking_error(final, n, cov),
                       "eff_n": A.effective_n(final), "backtest": bt, "backtest_neutral": bt_n,
                       "compliance": [r.to_dict() for r in comp], "compliance_summary": summ,
                       "ranking": [{"method": k, "composite": round(float(s), 3), "votes": p} for k, s, p in ranking],
                       "candidates": {k: {"exp_ret": c["exp_ret"], "vol": c["vol"], "te": c["te"], "sharpe": c["sharpe"],
                                          "compliance": c["compliance"]["overall"]} for k, c in cand.items()},
                       "approvers": approvers, "risk_budget": rb}

    # 5b. positioning, risk-budget usage and portfolio metrics -------------------------------------
    from ..analytics.positioning import Taxonomy, active_risk_contributions, portfolio_metrics, positioning_table
    from ..governance import POSITIONS_PATH, positions_as_of, record_positions
    pos_path = Path(positions_path) if positions_path else (Path(out_root) / "positions.csv" if out_root else POSITIONS_PATH)
    tax = Taxonomy.load(assets)
    mkt_w = tax.market_weights()
    rf_series = rets["cash"] if "cash" in rets else None
    for v, d in vint_out.items():
        cur = np.array([d["final"][a] for a in assets])
        n = np.array([d["neutral"][a] for a in assets])
        cols, col_src = {"current": cur}, {"current": f"this run ({run_id}, proposed)"}
        for label, when in (("last_week", as_of_ts - pd.Timedelta(days=7)), ("last_month", as_of_ts - pd.DateOffset(months=1))):
            w_prev, src = positions_as_of(str(when.date()), v, assets, pos_path, before_run=run_id)
            if w_prev is None:
                frac = when.year + (when.dayofyear - 1) / 365.25
                cols[label], col_src[label] = policy.neutral_weights(v - frac), f"glide path on {when.date()} (no recorded positions)"
            else:
                cols[label], col_src[label] = np.array([w_prev[a] for a in assets]), src
        cols["glide_path"], col_src["glide_path"] = n, f"policy {policy.id}"
        cols["market"], col_src["market"] = mkt_w, tax.raw["market_benchmark"]["name"]
        te, contrib = active_risk_contributions(cur, n, cov)
        d["positioning"] = {"columns": col_src,
                            "views": {vw: positioning_table(tax, cols, cov, n, d["risk_budget"], vw) for vw in tax.raw["views"]}}
        d["risk"] = {"te": te, "budget": d["risk_budget"], "used_pct": te / d["risk_budget"] if d["risk_budget"] else None,
                     "warn_at": policy.raw["risk_budgets"].get("warn_at_pct_used", 0.8),
                     "contributors": sorted(({"asset": a, "active_weight": float(cur[i] - n[i]), "te_contribution": float(contrib[i]),
                                              "budget_used": float(contrib[i] / d["risk_budget"])} for i, a in enumerate(assets)),
                                            key=lambda x: -abs(x["te_contribution"]))}
        d["metrics"] = {lbl: {"portfolio": portfolio_metrics(cur, rets, mkt_w, n, rf_series, m),
                              "glide_path": portfolio_metrics(n, rets, mkt_w, n, rf_series, m),
                              "market": portfolio_metrics(mkt_w, rets, mkt_w, n, rf_series, m)}
                        for lbl, m in (("5y", 60), ("full", None))}
    record_positions(as_of, run_id, vint_out, "proposed", pos_path)
    L.record(dr_type="signal", run_id=run_id, step="positioning.risk-metrics", actor=SYSTEM, policy_version=pv,
             summary="Look-through positioning, risk-budget usage and metrics computed for all vintages",
             output={v: {"te": d["risk"]["te"], "budget": d["risk"]["budget"], "used_pct": d["risk"]["used_pct"],
                         "beta_5y": d["metrics"]["5y"]["portfolio"]["beta_vs_market"]} for v, d in vint_out.items()})

    # 6. compliance officer agent --------------------------------------------------------------
    from ..compliance.officer import review as co_review
    co = co_review(run_id, regime_cfg, vint_out, synthetic_detail, L, policy)
    (out / "compliance_report.md").write_text(co["report_md"])

    if llm.enabled:
        L.record(dr_type="signal", run_id=run_id, step="llm.usage", actor=SYSTEM, policy_version=pv,
                 summary=f"LLM {llm.model}: {llm.usage['calls']} calls, {llm.usage['failures']} fell back to deterministic policy",
                 output=llm.usage)

    # 7. board memo ----------------------------------------------------------------------------
    from .memo import board_memo
    memo = board_memo(run_id, as_of, mv, cma_table, vint_out, regime_cfg, co, synthetic_detail, policy, llm.label, snap["snapshot_id"], snap)
    (out / "board_memo.md").write_text(memo)
    L.record(dr_type="signal", run_id=run_id, step="board-memo", actor=actor(load_agent("board-memo-writer"), llm),
             policy_version=pv, summary="Board memo generated", output={"path": "board_memo.md"})
    (out / "results.json").write_text(json.dumps({"run_id": run_id, "as_of": as_of, "macro": mv, "cma": cma_table,
                                                  "model": {"assets": assets, "cov": np.round(cov, 8).tolist(), "mu": mu.round(6).tolist(),
                                                            "taxonomy": tax.leaves, "views": tax.raw["views"],
                                                            "market": dict(zip(assets, mkt_w.round(6))),
                                                            "market_name": tax.raw["market_benchmark"]["name"]},
                                                  "vintages": vint_out, "compliance_officer": {k: v for k, v in co.items() if k != "report_md"},
                                                  "snapshot": snap}, indent=2, default=str))
    return RunResult(run_id, out, vint_out, out / "board_memo.md", out / "compliance_report.md", verify(out / "ledger.jsonl"))
