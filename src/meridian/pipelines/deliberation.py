"""Portfolio-construction strategy review (paper §3.5), run by agents.

The construction methods act as a panel that works on the whole series at once:

1. **Thesis.** Each method's agent explains its proposal and names its own weaknesses.
2. **Risk commentary.** The risk officer agent comments on every candidate. It does not vote.
3. **Peer review.** Each agent reviews two peers: one from its own family where one exists and one
   from another family. Assignments are random with a recorded seed, and all reviews are released
   together before anyone votes.
4. **Vote.** Each agent submits a top-3 ballot (3/2/1 points) and one bottom flag (−2), never for
   itself. Code tallies the points and blends them with the metric composite.
5. **Revision.** The shortlisted agents may temper their tilt or blend toward a peer in response
   to the reviews. Code recomputes the weights and the compliance engine re-checks them.

Agents write judgment and text. Every weight, risk number, tally and compliance result is computed
by code, and anything an agent returns is validated before it is used. Without a model (or when a
session fails, or the run budget is used up) each stage falls back to a deterministic policy, so an
offline run produces the same portfolios as before this module existed.
"""
from __future__ import annotations

import hashlib
import random

import numpy as np

from ..agents import actor
from ..agents import tools as T

TOP_K = 3
SHORTLIST = 3
SCALE_MIN, BLEND_MAX = 0.5, 0.5
LENSES = {"heuristic": "lowest tracking error versus the glide path",
          "return_optimized": "highest expected Sharpe ratio",
          "risk_structured": "lowest volatility and highest effective number of assets",
          "adversarial": "furthest from the consensus of the other candidates"}


# ------------------------------------------------------------------------------------------ pure helpers
def seed_for(run_id: str) -> int:
    """Review-assignment seed, derived from the run ID so it is recorded and reproducible."""
    return int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16)


def assign_reviews(families: dict, seed: int) -> dict:
    """reviewer -> [peer, peer]. One same-family peer where one exists and one from another family;
    a method alone in its family reviews two peers from other families. Random with ``seed``; the
    least-reviewed eligible peer is preferred so every candidate is reviewed."""
    rng = random.Random(seed)
    load = {k: 0 for k in families}
    out = {}
    order = sorted(families)
    rng.shuffle(order)

    def pick(pool):
        low = min(load[p] for p in pool)
        choice = rng.choice(sorted(p for p in pool if load[p] == low))
        load[choice] += 1
        return choice

    for r in order:
        same = [k for k in families if k != r and families[k] == families[r]]
        other = [k for k in families if families[k] != families[r]]
        first = pick(same) if same else pick(other)
        second = pick([k for k in other if k != first])
        out[r] = [first, second]
    return {r: out[r] for r in sorted(out)}


def validate_ballot(raw, voter: str, methods: list) -> dict | None:
    """A usable ballot: three different methods, none the voter, and a bottom flag that is neither."""
    if not isinstance(raw, dict):
        return None
    top, bottom = raw.get("top"), raw.get("bottom_flag")
    others = [m for m in methods if m != voter]
    if not isinstance(top, list) or len(top) != TOP_K or len(set(top)) != TOP_K or any(t not in others for t in top):
        return None
    if bottom not in others or bottom in top:
        return None
    return {"voter": voter, "top": list(top), "bottom_flag": bottom, "rationale": str(raw.get("rationale", ""))[:1200]}


def validate_reviews(raw, assigned: list) -> list | None:
    """Reviews for exactly the assigned peers, with a 1–5 score."""
    if not isinstance(raw, dict) or not isinstance(raw.get("reviews"), list):
        return None
    by = {}
    for r in raw["reviews"]:
        if isinstance(r, dict) and r.get("peer") in assigned and r["peer"] not in by:
            try:
                score = int(round(float(r.get("score", 3))))
            except (TypeError, ValueError):
                score = 3
            by[r["peer"]] = {"peer": r["peer"], "assessment": str(r.get("assessment", ""))[:1500],
                             "concerns": [str(c)[:300] for c in (r.get("concerns") or []) if isinstance(c, (str, int, float))][:5],
                             "score": min(5, max(1, score))}
    return [by[p] for p in assigned] if all(p in by for p in assigned) else None


def validate_revision(raw, method: str, methods: list) -> dict | None:
    if not isinstance(raw, dict):
        return None
    try:
        scale = float(raw.get("tilt_scale", 1.0))
        bw = float(raw.get("blend_weight", 0.0) or 0.0)
    except (TypeError, ValueError):
        return None
    if not (np.isfinite(scale) and np.isfinite(bw)):
        return None
    peer = raw.get("blend_with")
    peer = peer if peer in methods and peer != method else None
    bw = min(BLEND_MAX, max(0.0, bw)) if peer else 0.0
    return {"tilt_scale": min(1.0, max(SCALE_MIN, scale)), "blend_with": peer if bw > 0 else None, "blend_weight": bw,
            "response_to_reviews": str(raw.get("response_to_reviews", ""))[:1500]}


def apply_revision(w, neutral, w_peer, rev: dict) -> np.ndarray:
    """Temper the tilt toward the glide path, then blend toward a peer. Both steps are convex
    combinations of policy-feasible portfolios, so the result stays inside the bands and the
    tracking-error budget; the compliance engine re-checks it anyway."""
    w, neutral = np.asarray(w, float), np.asarray(neutral, float)
    out = neutral + rev["tilt_scale"] * (w - neutral)
    if rev.get("blend_with") and w_peer is not None:
        out = (1 - rev["blend_weight"]) * out + rev["blend_weight"] * np.asarray(w_peer, float)
    out = np.clip(out, 0, None)
    return out / out.sum()


def shortlist(avg_composite: dict, families: dict, size: int = SHORTLIST) -> list:
    """Top ``size`` by average composite, with at least two families represented (paper: diversity constraint)."""
    ranked = sorted(avg_composite, key=lambda k: -avg_composite[k])
    pick = ranked[:size]
    if len({families[k] for k in pick}) < 2:
        alt = next((k for k in ranked[size:] if families[k] != families[pick[0]]), None)
        if alt:
            pick = pick[:-1] + [alt]
    return pick


def series_summary(ctx: dict, assets: list, names: dict) -> dict:
    """Per method, averaged over the vintages: the numbers every agent sees."""
    out = {}
    vs = list(ctx)
    for k in ctx[vs[0]]["cand"]:
        cs = [ctx[v]["cand"][k] for v in vs]
        act = np.mean([np.asarray(ctx[v]["cand"][k]["w"]) - np.asarray(ctx[v]["n"]) for v in vs], axis=0)
        order = np.argsort(act)
        worst = max(cs, key=lambda c: (c["compliance"]["FAIL"], c["compliance"].get("WARN", 0)))["compliance"]["overall"]
        out[k] = {"family": cs[0]["family"],
                  "expected_return": float(np.mean([c["exp_ret"] for c in cs])), "volatility": float(np.mean([c["vol"] for c in cs])),
                  "tracking_error": float(np.mean([c["te"] for c in cs])), "max_tracking_error": float(max(c["te"] for c in cs)),
                  "sharpe": float(np.mean([c["sharpe"] for c in cs])), "effective_n": float(np.mean([c["eff_n"] for c in cs])),
                  "worst_drawdown": float(min(c["backtest"]["max_drawdown"] for c in cs)),
                  "distance_to_consensus": float(np.mean([c["dist_centroid"] for c in cs])), "compliance_worst": worst,
                  "largest_overweights": [{"asset": names[assets[i]], "active": float(act[i])} for i in order[::-1][:3] if act[i] > 1e-6],
                  "largest_underweights": [{"asset": names[assets[i]], "active": float(act[i])} for i in order[:3] if act[i] < -1e-6]}
    return T._r(out)


FACT_MEASURES = [  # (key in the summary, label, True if higher is better)
    ("expected_return", "expected return", True), ("volatility", "volatility", False), ("sharpe", "Sharpe ratio", True),
    ("tracking_error", "tracking error versus the glide path", False), ("effective_n", "effective number of assets", True),
    ("worst_drawdown", "worst simulated drawdown", True), ("distance_to_consensus", "distance to consensus", False)]


def fact_sheet(summ: dict) -> dict:
    """Rankings computed by code so agents quote them instead of working them out. Ties share a place."""
    out = {"note": ("Computed by code from the series-average metrics. Quote these rankings rather than deriving your own. "
                    "'Best' means highest for return, Sharpe, effective N and drawdown (least negative), and lowest for "
                    "volatility, tracking error and distance to consensus. The glide path is the policy benchmark, not a tilt.")}
    for key, label, high in FACT_MEASURES:
        vals = {k: round(float(s[key]), 4) for k, s in summ.items()}
        order = sorted(vals, key=lambda k: -vals[k] if high else vals[k])
        best, worst = vals[order[0]], vals[order[-1]]
        out[key] = {"measure": label, "ranking_best_first": [{"method": k, "value": vals[k]} for k in order],
                    "best": [k for k in order if vals[k] == best], "worst": [k for k in order if vals[k] == worst]}
    by_status: dict = {}
    for k, s in summ.items():
        by_status.setdefault(s["compliance_worst"], []).append(k)
    out["compliance"] = {"by_status": {st: sorted(ks) for st, ks in sorted(by_status.items())},
                         "passing": sorted(k for k, s in summ.items() if s["compliance_worst"].startswith("PASS")),
                         "with_warnings": sorted(by_status.get("WARN", [])), "failing": sorted(by_status.get("FAIL", [])),
                         "note": "Status is the worst result across the vintages. 'PASS (attestations pending)' counts as passing."}
    out["family_members"] = {}
    for k, s in summ.items():
        out["family_members"].setdefault(s["family"], []).append(k)
    return out


# ------------------------------------------------------------------------------------------ deterministic fallbacks
def offline_thesis(k: str, s: dict, regime: str) -> dict:
    return {"thesis": (f"{k} ({s['family'].replace('_', '-')}): average expected return {s['expected_return']:.2%}, volatility "
                       f"{s['volatility']:.2%}, tracking error {s['tracking_error']:.2%} versus the glide path in a "
                       f"{regime.replace('_', '-')} regime."),
            "fits_regime": "partly", "weaknesses": []}


def offline_review(reviewer_family: str, peer: str, s: dict) -> dict:
    return {"peer": peer, "score": 3, "concerns": [],
            "assessment": (f"Judged through the {reviewer_family.replace('_', '-')} lens ({LENSES.get(reviewer_family, 'metrics')}): "
                           f"Sharpe {s['sharpe']:.2f}, tracking error {s['tracking_error']:.2%}, effective N {s['effective_n']:.1f}, "
                           f"compliance {s['compliance_worst']}.")}


# ------------------------------------------------------------------------------------------ the review
def deliberate(llm, L, run_id: str, pv: str, mv: dict, ctx: dict, assets: list, names: dict, specs: dict,
               inputs: list, reevaluate) -> dict:
    """Run thesis → risk commentary → peer review → vote → revision for the whole series.

    ``ctx[v]`` holds ``n`` (glide path), ``cand`` (method -> candidate dict with weights and metrics) and
    ``composite`` (method -> pre-vote metric composite). ``reevaluate(v, method, w)`` recomputes a
    candidate's metrics and compliance in place and returns its compliance summary.
    Returns the artifacts for results.json; ``ballots`` holds only ballots made by agents.
    """
    pc, cro = specs["pc"], specs["cro"]
    vs = list(ctx)
    methods = list(ctx[vs[0]]["cand"])
    fam = {k: ctx[vs[0]]["cand"][k]["family"] for k in methods}
    summ = series_summary(ctx, assets, names)
    scope = [f"MTRS-{v}" for v in vs]
    facts = fact_sheet(summ)
    base = {"regime": {"regime": mv["regime"], "confidence": mv["confidence"]}, "vintages": vs, "fact_sheet": facts, "candidates": summ}
    detail = T.deliberation_tools(ctx, assets, names)

    def pc_actor(k, path):
        return {**actor(pc, llm, path=path), "id": f"pc-{k}"}

    def persona(k):
        return (f"You are the portfolio-construction agent for the method `{k}` (family: {fam[k].replace('_', '-')}). "
                f"Your family's lens when judging portfolios: {LENSES.get(fam[k], 'overall quality')}. ")

    def rec(step, act, summary, output, rationale=None, dr_type="signal", **kw):
        if rationale:
            kw["rationale"] = rationale
        return L.record(dr_type=dr_type, run_id=run_id, step=step, actor=act, policy_version=pv, inputs=inputs,
                        portfolio_scope=scope, summary=summary, output=output, **kw)

    def traced(output, path):
        return {**output, "judge_path": path, **({"agent_trace": llm.last_trace} if llm.last_trace else {})}

    rec("pc-review.fact-sheet", {"kind": "system", "id": "orchestrator", "version": "0.1.0"},
        "Fact sheet for the strategy review: best " + ", ".join(f"{m[1]} {'/'.join(facts[m[0]]['best'])}" for m in FACT_MEASURES[:3])
        + f"; passing: {', '.join(facts['compliance']['passing']) or 'none'}", facts)

    # 1. thesis --------------------------------------------------------------------------------
    theses = {}
    for k in methods:
        j = llm.judge(pc, persona(k) + "Write the thesis for your proposal across the series: why this method suits the "
                      "current regime and capital market assumptions, and where it is weakest. Three or four sentences. "
                      "Use only numbers given in the context or returned by a tool. For any claim that a method is highest, "
                      "lowest, best, worst or the only one passing, check the fact_sheet and state it exactly as it says.",
                      {**base, "your_method": k}, '{"thesis": str, "fits_regime": "well|partly|poorly", "weaknesses": [str]}',
                      tools=detail, schema=T.THESIS_SCHEMA)
        ok = isinstance(j, dict) and isinstance(j.get("thesis"), str) and j["thesis"].strip()
        path = llm.path_name if ok else "offline"
        t = ({"thesis": j["thesis"][:1500], "fits_regime": j.get("fits_regime") if j.get("fits_regime") in ("well", "partly", "poorly") else "partly",
              "weaknesses": [str(x)[:300] for x in (j.get("weaknesses") or []) if isinstance(x, (str, int, float))][:4]}
             if ok else offline_thesis(k, summ[k], mv["regime"]))
        theses[k] = {**t, "source": path}
        rec(f"pc-{k}.thesis", pc_actor(k, path), f"{k}: thesis (fits regime: {t['fits_regime']})", traced(t, path), rationale=t["thesis"])

    # 2. risk officer commentary (neutral; no vote) ----------------------------------------------
    j = llm.judge(cro, "Write the standardized risk commentary on every candidate for the series. One or two sentences per "
                  "method and a risk flag. You are a neutral assessor: you do not rank or vote, and you report compliance "
                  "results exactly as given. Any 'highest', 'lowest' or 'only' statement must match the fact_sheet.", base,
                  '{"overview": str, "comments": [{"method": str, "comment": str, "risk_flag": "none|watch|concern"}]}',
                  tools=detail, schema=T.cro_schema(methods))
    got = {c["method"]: c for c in (j.get("comments") or []) if isinstance(c, dict) and c.get("method") in methods} if isinstance(j, dict) else {}
    path = llm.path_name if len(got) == len(methods) else "offline"
    if path == "offline":
        cro_out = {"overview": "Risk metrics and compliance results for each candidate are in the risk report records.",
                   "comments": [{"method": k, "risk_flag": "none" if summ[k]["compliance_worst"] == "PASS" else "watch",
                                 "comment": f"Tracking error {summ[k]['tracking_error']:.2%} (max {summ[k]['max_tracking_error']:.2%}), "
                                            f"worst simulated drawdown {summ[k]['worst_drawdown']:.1%}, compliance {summ[k]['compliance_worst']}."}
                                for k in methods]}
    else:
        cro_out = {"overview": str(j.get("overview", ""))[:1500],
                   "comments": [{"method": k, "comment": str(got[k].get("comment", ""))[:600],
                                 "risk_flag": got[k].get("risk_flag") if got[k].get("risk_flag") in ("none", "watch", "concern") else "watch"}
                                for k in methods]}
    cro_out["source"] = path
    flags = ", ".join(f"{c['method']}={c['risk_flag']}" for c in cro_out["comments"] if c["risk_flag"] != "none") or "none"
    rec("cro.commentary", actor(cro, llm, path=path), f"Risk commentary on {len(methods)} candidates; flags: {flags}",
        traced(cro_out, path), rationale=cro_out["overview"])
    cro_by = {c["method"]: c for c in cro_out["comments"]}

    # 3. peer review: assignments are random with a recorded seed; reviews are released together -------
    seed = seed_for(run_id)
    assign = assign_reviews(fam, seed)
    rec("pc-review.assignments", {"kind": "system", "id": "orchestrator", "version": "0.1.0"},
        f"Peer-review assignments drawn with seed {seed}", {"seed": seed, "assignments": assign})
    reviews = {}
    for k in methods:
        peers = assign[k]
        j = llm.judge(pc, persona(k) + f"Review these two peers: {peers[0]} and {peers[1]}. For each give an assessment "
                      "(strengths, weaknesses, fit with the policy, estimation risk, one concrete improvement), a short list "
                      "of concerns, and a score from 1 (weak) to 5 (strong). Be specific and critical; do not review yourself. "
                      "Check every ranking or 'only' claim, yours and the peer's, against the fact_sheet; call out a peer's claim "
                      "that the fact_sheet contradicts.",
                      {**base, "your_method": k, "peers_to_review": {p: {"thesis": theses[p]["thesis"], "weaknesses": theses[p]["weaknesses"],
                                                                         "risk_officer": cro_by[p]} for p in peers}},
                      '{"reviews": [{"peer": str, "assessment": str, "concerns": [str], "score": 1-5}]}',
                      tools=detail, schema=T.review_schema(peers))
        rv = validate_reviews(j, peers)
        path = llm.path_name if rv else "offline"
        rv = rv or [offline_review(fam[k], p, summ[p]) for p in peers]
        reviews[k] = {"reviews": rv, "source": path}
        rec(f"pc-{k}.peer-review", pc_actor(k, path), f"{k} reviewed " + ", ".join(f"{r['peer']} ({r['score']}/5)" for r in rv),
            traced({"reviews": rv}, path), rationale=" | ".join(f"{r['peer']}: {r['assessment']}" for r in rv)[:3000])
    received = {k: [{"reviewer": r, **x} for r, d in reviews.items() for x in d["reviews"] if x["peer"] == k] for k in methods}

    # 4. vote: every agent has read every review -------------------------------------------------
    ballots = {}
    released = {k: [{"reviewer": x["reviewer"], "score": x["score"], "concerns": x["concerns"], "assessment": x["assessment"][:400]}
                    for x in received[k]] for k in methods}
    for k in methods:
        j = llm.judge(pc, persona(k) + f"Vote on the other candidates. Rank your top {TOP_K} (first is best) and flag one as the "
                      "weakest. Never vote for yourself. Weigh the reviews and the risk commentary, not only your own lens, and "
                      "say briefly why.",
                      {**base, "your_method": k, "reviews_received_by_each_candidate": released, "risk_officer": cro_out["comments"]},
                      '{"top": [str, str, str], "bottom_flag": str, "rationale": str}',
                      tools=detail, schema=T.ballot_schema([m for m in methods if m != k]))
        b = validate_ballot(j, k, methods)
        path = llm.path_name if b else "offline"
        if b:
            ballots[k] = {**b, "lens": fam[k], "source": path}
        rec(f"pc-{k}.ballot", pc_actor(k, path),
            (f"{k} voted: top {', '.join(b['top'])}; bottom flag {b['bottom_flag']}" if b
             else f"{k}: no usable ballot; the rule-based {fam[k].replace('_', '-')} lens votes for it in each vintage"),
            traced({"top": b["top"], "bottom_flag": b["bottom_flag"]} if b else {"fallback": "family lens, per vintage"}, path),
            rationale=b["rationale"] if b else None, dr_type="decision")

    # 5. revision by the shortlist ---------------------------------------------------------------
    pts = {k: 0 for k in methods}
    for b in ballots.values():
        for i, t in enumerate(b["top"]):
            pts[t] += TOP_K - i
        pts[b["bottom_flag"]] -= 2
    norm = (lambda d: {k: (d[k] - min(d.values())) / (max(d.values()) - min(d.values())) if max(d.values()) > min(d.values()) else 0.5 for k in d})
    metric = {k: float(np.mean([ctx[v]["composite"][k] for v in vs])) for k in methods}
    vote_w = 0.4 if mv["regime"] in ("late_cycle", "recession") else 0.5
    blended = {k: (vote_w * norm(pts)[k] + (1 - vote_w) * metric[k]) if ballots else metric[k] for k in methods}
    short = shortlist(blended, fam)
    original = {v: {k: np.array(ctx[v]["cand"][k]["w"], float) for k in methods} for v in vs}
    revisions = {}
    for k in short:
        tools = detail + T.revision_tools(k, methods, ctx, original, apply_revision, validate_revision)
        j = llm.judge(pc, persona(k) + "You are shortlisted. Revise your proposal in response to the reviews and the risk "
                      "commentary. You may temper your tilt toward the glide path (tilt_scale between 0.5 and 1.0, where 1.0 keeps "
                      "it unchanged) and you may blend toward one peer's original proposal (blend_weight up to 0.5; use "
                      "blend_with \"none\" for no blend). Use preview_revision to see the effect before you answer. Keeping your "
                      "proposal unchanged is acceptable if the criticism does not hold; say why either way.",
                      {**base, "your_method": k, "reviews_of_you": received[k], "risk_officer_on_you": cro_by[k],
                       "shortlist": short}, '{"tilt_scale": float, "blend_with": str, "blend_weight": float, "response_to_reviews": str}',
                      tools=tools, schema=T.revision_schema([m for m in methods if m != k]))
        rev = validate_revision(j, k, methods)
        path = llm.path_name if rev else "offline"
        changed, note = False, ("no usable revision; proposal unchanged" if llm.enabled or llm.last_trace
                                else "not revised (deterministic run)")
        if rev:
            note = "kept unchanged"
            if rev["tilt_scale"] < 1.0 or rev["blend_with"]:
                new = {v: apply_revision(original[v][k], ctx[v]["n"], original[v].get(rev["blend_with"]), rev) for v in vs}
                fails = [v for v in vs if reevaluate(v, k, new[v])["FAIL"]]
                if fails:                                   # compliance decides: put the original back everywhere
                    for v in vs:
                        reevaluate(v, k, original[v][k])
                    note = f"revision rejected: compliance FAIL in {fails}; original kept"
                else:
                    changed = True
                    note = (f"tilt scaled to {rev['tilt_scale']:.2f}" + (f", blended {rev['blend_weight']:.0%} toward {rev['blend_with']}"
                                                                         if rev["blend_with"] else ""))
        revisions[k] = {**(rev or {"tilt_scale": 1.0, "blend_with": None, "blend_weight": 0.0, "response_to_reviews": ""}),
                        "applied": changed, "note": note, "source": path}
        rec(f"pc-{k}.revision", pc_actor(k, path), f"{k}: {note}", traced({x: revisions[k][x] for x in ("tilt_scale", "blend_with", "blend_weight", "applied", "note")}, path),
            rationale=revisions[k]["response_to_reviews"] or None, dr_type="decision")

    return {"seed": seed, "fact_sheet": facts, "assignments": assign, "theses": theses, "risk_commentary": cro_out, "reviews": reviews,
            "ballots": ballots, "shortlist": short, "revisions": revisions, "families": fam,
            "by_agents": sum(1 for d in list(theses.values()) + list(reviews.values()) + list(ballots.values()) + list(revisions.values())
                             if d.get("source") not in (None, "offline")) + (cro_out["source"] != "offline")}
