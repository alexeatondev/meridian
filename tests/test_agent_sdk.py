"""Agent SDK backend tests with a fake SDK (no network, no key, no CLI needed)."""
import json
import sys
import types

import pytest

from meridian.agents import tools as T


# ------------------------------------------------------------------------------------------ fake SDK
class ResultMessage:
    def __init__(self, structured_output=None, result="", cost=0.01, subtype="success", turns=2):
        self.structured_output, self.result, self.total_cost_usd = structured_output, result, cost
        self.subtype, self.num_turns, self.session_id = subtype, turns, "sess_test"
        self.usage = {"input_tokens": 900, "cache_read_input_tokens": 100, "output_tokens": 200}


def make_fake_sdk(script, cost=0.01):
    """``script(system, prompt, call_tool)`` returns a dict (structured output), a str (raw text) or raises."""
    sdk = types.ModuleType("claude_agent_sdk")
    sdk.__version__ = "0.0-test"
    sdk.ResultMessage = ResultMessage
    sdk.sessions = []

    class ClaudeAgentOptions:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    def tool(name, description, schema):
        def deco(fn):
            return types.SimpleNamespace(name=name, description=description, schema=schema, handler=fn)
        return deco

    def create_sdk_mcp_server(name, version="1.0.0", tools=None):
        return {"name": name, "tools": {t.name: t for t in tools or []}}

    async def query(*, prompt, options):
        sdk.sessions.append(options)
        server = (options.mcp_servers or {}).get("meridian", {"tools": {}})

        async def call_tool(name, args):
            assert f"mcp__meridian__{name}" in options.allowed_tools
            res = await server["tools"][name].handler(args)
            return res["content"][0]["text"], res.get("is_error", False)

        out = await script(options.system_prompt, prompt, call_tool)
        if isinstance(out, dict):
            yield ResultMessage(structured_output=out, cost=cost)
        else:
            yield ResultMessage(result=out, cost=cost)

    sdk.ClaudeAgentOptions, sdk.tool, sdk.create_sdk_mcp_server, sdk.query = ClaudeAgentOptions, tool, create_sdk_mcp_server, query
    return sdk


def install(monkeypatch, script, cost=0.01, **env):
    sdk = make_fake_sdk(script, cost)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", sdk)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("MERIDIAN_LLM", "on")
    monkeypatch.setenv("MERIDIAN_AGENT_BACKEND", "sdk")
    monkeypatch.setenv("MERIDIAN_MODEL", "claude-test-model")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return sdk


METHODS = ["glide_path_neutral", "max_sharpe_tilt", "black_litterman_tilt", "min_variance_tilt",
           "max_diversification_tilt", "risk_budget_tilt", "adversarial_diversifier"]


async def script(system, prompt, call_tool):
    import re
    me = re.search(r"for the method `(\w+)`", prompt)
    me = me.group(1) if me else None
    if "Write the thesis" in prompt:
        return {"thesis": f"{me} suits an expansion with modest growth.", "fits_regime": "well", "weaknesses": ["CMA error"]}
    if "standardized risk commentary" in prompt:
        text, err = await call_tool("candidate_detail", {"method": "max_sharpe_tilt", "vintage": "2050"})
        assert not err and "tracking_error" in text
        return {"overview": "All candidates sit inside the tracking-error budget.",
                "comments": [{"method": m, "comment": f"{m}: within limits.", "risk_flag": "watch" if m == "max_sharpe_tilt" else "none"}
                             for m in METHODS]}
    if "Review these two peers" in prompt:
        a, b = re.search(r"Review these two peers: (\w+) and (\w+)\.", prompt).groups()
        assert me not in (a, b)
        if me == "min_variance_tilt":
            return {"reviews": [{"peer": a, "assessment": "only one review", "concerns": [], "score": 4}]}     # incomplete -> fallback
        return {"reviews": [{"peer": a, "assessment": f"{a} is sound.", "concerns": ["estimation risk"], "score": 9},
                            {"peer": b, "assessment": f"{b} leans on the CMAs.", "concerns": [], "score": 2}]}
    if "Vote on the other candidates" in prompt:
        assert "reviews_received_by_each_candidate" in prompt
        others = [m for m in METHODS if m != me]
        if me == "risk_budget_tilt":
            return {"top": [me, others[0], others[1]], "bottom_flag": others[2], "rationale": "votes for itself"}   # invalid
        return {"top": ["glide_path_neutral" if me != "glide_path_neutral" else "min_variance_tilt",
                        *[m for m in others if m not in ("glide_path_neutral", "min_variance_tilt", "adversarial_diversifier")][:2]],
                "bottom_flag": "adversarial_diversifier" if me != "adversarial_diversifier" else "risk_budget_tilt",
                "rationale": "Reviews favoured the low tracking-error candidates."}
    if "You are shortlisted" in prompt:
        text, err = await call_tool("preview_revision", {"tilt_scale": 0.6, "blend_with": "none"})
        assert not err and "by_vintage" in text and "any_compliance_fail" in text
        return {"tilt_scale": 0.6, "blend_with": "none", "blend_weight": 0.9, "response_to_reviews": "Tempered the tilt for estimation risk."}
    if "opening summary of the board memo" in prompt:
        return {"narrative": "The agents recommend holding each vintage near its glide path. One method dissented. This run contains synthetic data."}
    if "regime classification" in prompt:
        text, err = await call_tool("rescore_regime", {"overrides": {"hy_spread_bp": 900}})
        assert not err and "with_overrides" in text
        return {"regime": "late_cycle", "confidence": 0.7, "rationale": "Spreads tight; checked sensitivity."}
    if "US Large Cap" in prompt:
        text, err = await call_tool("blend_preview", {"weights": {"historical": -1}})
        assert err                                                         # bad arguments are reported, not fatal
        return {"weights": {"historical": -1, "building_block": 2}, "rationale": "bad weights"}     # must be rejected
    if "expected return" in prompt:
        return 'Here you go: {"weights": {"building_block": 0.5, "equilibrium": 0.5}, "rationale": "Blend."}'
    if "2030 vintage" in prompt:
        raise RuntimeError("simulated agent failure")                      # must fall back
    if "ensemble method" in prompt:
        text, err = await call_tool("ensemble_detail", {"ensemble": "simple_average"})
        assert not err and "largest_overweights" in text
        return {"ensemble": "simple_average", "rationale": "Robust to CMA noise.", "invalidation_conditions": ["Recession"]}
    if "compliance review" in prompt:
        text, _ = await call_tool("judgment_paths", {})
        assert "agent" in text
        return {"narrative": "Draft review: no hard-limit breaches.", "recommended_actions": []}
    return {}


def test_agent_sdk_pipeline(monkeypatch, tmp_path):
    sdk = install(monkeypatch, script)
    from meridian.ledger import Ledger
    from meridian.pipelines.target_date import run
    r = run(out_root=tmp_path)
    recs = Ledger(r.out_dir / "ledger.jsonl").records()
    by = {x["step"]: x for x in recs}
    assert r.ledger_ok[0]

    macro = by["macro-regime"]
    assert macro["output"]["judge_path"] == "agent" and macro["actor"]["model"] == "claude-test-model"
    assert macro["actor"]["runtime"].startswith("claude-agent-sdk")
    assert [c["tool"] for c in macro["output"]["agent_trace"]["tool_calls"]] == ["rescore_regime"]

    lc = by["ac-us_large_cap.cma-judge"]                                   # rejected weights -> offline, not attributed to the model
    assert lc["output"]["judge_path"] == "offline" and lc["actor"]["model"] == "offline-deterministic"
    assert lc["output"]["agent_trace"]["tool_calls"][0]["error"]
    sm = by["ac-us_small_mid_cap.cma-judge"]["output"]
    assert sm["judge_path"] == "agent" and set(sm["weights"]) == {"building_block", "equilibrium"}

    cio = {x["portfolio_scope"][0]: x for x in recs if x["step"] == "cio.ensemble"}
    assert cio["MTRS-2030"]["output"]["judge_path"] == "offline" and r.vintages[2030]["ensemble"] == "inverse_tracking_error"
    assert cio["MTRS-2050"]["output"]["judge_path"] == "agent" and r.vintages[2050]["ensemble"] == "simple_average"
    assert by["compliance-officer.review"]["output"]["judge_path"] == "agent"
    assert "AI-drafted" in r.compliance_report_path.read_text()

    # steps computed by code are never attributed to a model
    for x in recs:
        if x["step"].startswith("pc-") and x["step"].endswith(".proposal") or x["step"] in ("cro.risk-report", "board-memo"):
            assert x["actor"]["kind"] == "system" and "model" not in x["actor"], x["step"]
            assert x["actor"]["implemented_by"] == "deterministic code"

    usage = by["llm.usage"]["output"]
    assert usage["backend"] == "claude-agent-sdk" and usage["calls"] == 50 and usage["failures"] == 1
    assert usage["cost_usd"] == pytest.approx(0.49) and usage["tool_calls"] >= 14

    # strategy review: thesis -> risk commentary -> peer review -> vote -> revision, all recorded
    sr = json.loads((r.out_dir / "results.json").read_text())["strategy_review"]
    assert by["pc-max_sharpe_tilt.thesis"]["actor"]["id"] == "pc-max_sharpe_tilt" and by["pc-max_sharpe_tilt.thesis"]["output"]["judge_path"] == "agent"
    assert by["cro.commentary"]["output"]["judge_path"] == "agent" and by["cro.commentary"]["actor"]["model"] == "claude-test-model"
    assert by["pc-review.assignments"]["output"]["seed"] == sr["seed"]
    assert by["pc-review.fact-sheet"]["actor"]["kind"] == "system" and sr["fact_sheet"]["compliance"]["passing"]
    for k, peers in sr["assignments"].items():                               # two different peers, never itself
        assert len(set(peers)) == 2 and k not in peers
        fam = sr["families"]
        same = [m for m in METHODS if m != k and fam[m] == fam[k]]
        assert (fam[peers[0]] == fam[k]) == bool(same) and fam[peers[1]] != fam[k]
    assert sr["reviews"]["max_sharpe_tilt"]["reviews"][0]["score"] == 5       # 9 clamped to the 1-5 scale
    assert sr["reviews"]["min_variance_tilt"]["source"] == "offline" and by["pc-min_variance_tilt.peer-review"]["actor"]["model"] == "offline-deterministic"
    assert set(sr["ballots"]) == set(METHODS) - {"risk_budget_tilt"}         # the self-vote was discarded
    assert by["pc-risk_budget_tilt.ballot"]["output"]["judge_path"] == "offline"
    vote = next(x for x in recs if x["step"] == "pc-review.borda-vote" and x["portfolio_scope"] == ["MTRS-2050"])
    src = {b["voter"]: b["source"] for b in vote["output"]["ballots"]}
    assert src["risk_budget_tilt"] == "lens" and src["max_sharpe_tilt"] == "agent" and "6 of 7 ballots cast by agents" in vote["summary"]
    assert all(b["voter"] not in b["top"] and b["voter"] != b["bottom_flag"] for b in vote["output"]["ballots"])
    assert len(sr["shortlist"]) == 3 and len({sr["families"][k] for k in sr["shortlist"]}) >= 2
    for k in sr["shortlist"]:
        rv = sr["revisions"][k]
        assert rv["tilt_scale"] == 0.6 and rv["blend_with"] is None and rv["blend_weight"] == 0.0
        assert by[f"pc-{k}.revision"]["output"]["agent_trace"]["tool_calls"][0]["tool"] == "preview_revision"
        revised = [x for x in recs if x["step"] == f"pc-{k}.proposal-revised"]
        assert len(revised) == (9 if rv["applied"] else 0) and all(x["actor"]["kind"] == "system" for x in revised)
    assert any(rv["applied"] for rv in sr["revisions"].values())
    assert all(v["compliance_summary"]["FAIL"] == 0 for v in r.vintages.values())
    memo = r.memo_path.read_text()
    assert "## Summary (AI-drafted)" in memo and "One method dissented" in memo and "peer reviews, ballots and revisions" in memo
    assert by["board-memo.summary"]["output"]["judge_path"] == "agent" and by["board-memo"]["actor"]["kind"] == "system"

    # every session is locked down: no built-in tools, no settings, capped turns and spend, schema-bound output
    for o in sdk.sessions:
        assert o.tools == [] and o.setting_sources == [] and o.max_turns == 8
        assert 0 < o.max_budget_usd <= 0.25 and o.output_format["type"] == "json_schema"
        assert all(t.startswith("mcp__meridian__") for t in o.allowed_tools)


def test_run_budget_stops_agent_calls(monkeypatch, tmp_path):
    async def ok(system, prompt, call_tool):
        return {"regime": "expansion", "confidence": 0.6, "rationale": "ok", "weights": {}, "ensemble": "simple_average",
                "invalidation_conditions": [], "narrative": "ok", "recommended_actions": []}
    sdk = install(monkeypatch, ok, cost=0.10, MERIDIAN_RUN_BUDGET_USD="0.25")
    from meridian.ledger import Ledger
    from meridian.pipelines.target_date import run
    r = run(out_root=tmp_path)
    by = {x["step"]: x for x in Ledger(r.out_dir / "ledger.jsonl").records()}
    usage = by["llm.usage"]["output"]
    assert len(sdk.sessions) == 3 and usage["calls"] == 3                  # third call crosses the cap; the rest are skipped
    assert usage["skipped_over_budget"] == 47 and usage["cost_usd"] == pytest.approx(0.30)
    skipped = by["compliance-officer.review"]["output"]
    assert skipped["judge_path"] == "offline" and skipped["agent_trace"]["skipped"] == "run budget used up"
    assert all(v["compliance_summary"]["FAIL"] == 0 for v in r.vintages.values())


def test_tools_are_read_only_and_bounded():
    m = {"historical": 0.09, "equilibrium": 0.06, "building_block": 0.04}
    from meridian.analytics.core import auto_blend
    from meridian.pipelines.target_date import classify_regime, validate_weights
    tools = {t.name: t for t in T.cma_tools("us_large_cap", m, auto_blend, validate_weights, {"history": {}}, {})}
    out = tools["blend_preview"].fn({"weights": {"historical": 3, "equilibrium": 1, "made_up": 5}})
    assert out["method_range"] == [0.04, 0.09] and 0.04 <= out["final_after_bound"] <= 0.09
    assert set(out["normalized_weights"]) == {"historical", "equilibrium"}
    with pytest.raises(ValueError):
        tools["blend_preview"].fn({"weights": {"historical": -1}})

    macro = {"real_gdp_growth_yoy": 2.0, "cfnai_ma3": 0.0, "unemployment_change_6m": 0.1, "core_cpi_yoy": 2.8,
             "policy_rate_change_6m": -0.5, "hy_spread_bp": 300}
    mt = {t.name: t for t in T.macro_tools(macro, {k: {"value": v} for k, v in macro.items()}, classify_regime)}
    res = mt["rescore_regime"].fn({"overrides": {"real_gdp_growth_yoy": -2.0, "hy_spread_bp": 900}})
    assert res["baseline"]["regime"] != res["with_overrides"]["regime"] and macro["hy_spread_bp"] == 300   # input untouched
    with pytest.raises(ValueError):
        mt["rescore_regime"].fn({"overrides": {"nope": 1}})
    json.dumps(T.cma_schema(m)), json.dumps(T.cio_schema(["a", "b"]))        # schemas are plain JSON


def test_model_selection_precedence(monkeypatch, tmp_path):
    from meridian.agents import runtime as R
    cfg = tmp_path / "models.yaml"
    cfg.write_text("default: model-default\nagents:\n  cio: model-cio\n")
    monkeypatch.setattr(R, "MODELS_PATH", cfg)
    monkeypatch.delenv("MERIDIAN_MODEL", raising=False)
    cio, macro = R.load_agent("cio"), R.load_agent("macro-regime")
    b = R.LLMBackend()
    assert b.model == "model-default" and b.model_for(macro) == "model-default" and b.model_for(cio) == "model-cio"
    monkeypatch.setenv("MERIDIAN_MODEL", "")                       # the workflow passes an empty value for "config default"
    assert R.LLMBackend().model == "model-default"
    monkeypatch.setenv("MERIDIAN_MODEL", "model-run")              # the workflow's dropdown
    b = R.LLMBackend()
    assert b.model_for(macro) == "model-run" and b.model_for(cio) == "model-cio"
    monkeypatch.setenv("MERIDIAN_MODEL_CIO", "model-env")
    assert b.model_for(cio) == "model-env"
    monkeypatch.setattr(R, "MODELS_PATH", tmp_path / "missing.yaml")
    monkeypatch.delenv("MERIDIAN_MODEL")
    assert R.LLMBackend().model == R.FALLBACK_MODEL == "claude-haiku-5-5"


def test_shipped_default_is_cheapest_model():
    from meridian.agents.runtime import model_config
    assert model_config() == {"default": "claude-haiku-5-5", "agents": {}}


def test_strategy_review_rules():
    from meridian.pipelines import deliberation as D
    import numpy as np
    fam = {"a1": "x", "a2": "x", "b1": "y", "b2": "y", "solo": "z"}
    a1, a2 = D.assign_reviews(fam, 7), D.assign_reviews(fam, 7)
    assert a1 == a2                                                            # same seed, same draw
    for r, (p1, p2) in a1.items():
        assert r not in (p1, p2) and p1 != p2 and fam[p2] != fam[r]
        assert (fam[p1] == fam[r]) == (r != "solo")
    assert set(p for ps in a1.values() for p in ps) == set(fam)                # everyone is reviewed
    ms = list(fam)
    assert D.validate_ballot({"top": ["a2", "b1", "b2"], "bottom_flag": "solo"}, "a1", ms)["top"] == ["a2", "b1", "b2"]
    for bad in ({"top": ["a1", "b1", "b2"], "bottom_flag": "solo"}, {"top": ["a2", "a2", "b2"], "bottom_flag": "solo"},
                {"top": ["a2", "b1"], "bottom_flag": "solo"}, {"top": ["a2", "b1", "b2"], "bottom_flag": "b2"},
                {"top": ["a2", "b1", "b2"], "bottom_flag": "a1"}, {"top": ["a2", "b1", "nope"], "bottom_flag": "solo"}, None):
        assert D.validate_ballot(bad, "a1", ms) is None
    rev = D.validate_revision({"tilt_scale": 0.1, "blend_with": "b1", "blend_weight": 3}, "a1", ms)
    assert rev["tilt_scale"] == 0.5 and rev["blend_with"] == "b1" and rev["blend_weight"] == 0.5
    assert D.validate_revision({"tilt_scale": 2, "blend_with": "a1", "blend_weight": 0.3}, "a1", ms)["blend_with"] is None   # not with itself
    assert D.validate_revision({"tilt_scale": "abc"}, "a1", ms) is None
    n, w, peer = np.array([0.5, 0.3, 0.2]), np.array([0.56, 0.27, 0.17]), np.array([0.5, 0.32, 0.18])
    out = D.apply_revision(w, n, peer, {"tilt_scale": 0.5, "blend_with": "b1", "blend_weight": 0.5})
    assert out.sum() == pytest.approx(1.0) and np.allclose(out, 0.5 * (n + 0.5 * (w - n)) + 0.5 * peer)
    assert np.all(np.abs(out - n) <= np.maximum(np.abs(w - n), np.abs(peer - n)) + 1e-12)   # never further from the glide path
    assert D.shortlist({"a1": 0.9, "a2": 0.8, "b1": 0.5, "solo": 0.4, "b2": 0.1}, fam, 2) == ["a1", "b1"]   # family diversity


def test_fact_sheet_rankings():
    from meridian.pipelines.deliberation import fact_sheet
    base = dict(volatility=0.12, tracking_error=0.01, effective_n=4.0, worst_drawdown=-0.5, distance_to_consensus=0.2)
    summ = {"gp": {**base, "family": "heuristic", "expected_return": 0.0773, "sharpe": 0.31, "compliance_worst": "PASS (attestations pending)"},
            "rb": {**base, "family": "risk", "expected_return": 0.078, "sharpe": 0.32, "volatility": 0.11, "compliance_worst": "PASS (attestations pending)"},
            "ad": {**base, "family": "adv", "expected_return": 0.078, "sharpe": 0.30, "worst_drawdown": -0.51, "compliance_worst": "WARN"}}
    f = fact_sheet(summ)
    assert f["expected_return"]["best"] == ["rb", "ad"] and "gp" not in f["expected_return"]["best"]   # ties share first place
    assert f["volatility"]["best"] == ["rb"] and f["worst_drawdown"]["worst"] == ["ad"]
    assert f["compliance"]["passing"] == ["gp", "rb"] and f["compliance"]["with_warnings"] == ["ad"]  # two pass, not "only one"
    assert f["family_members"]["heuristic"] == ["gp"]
