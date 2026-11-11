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


async def script(system, prompt, call_tool):
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
    assert usage["backend"] == "claude-agent-sdk" and usage["calls"] == 24 and usage["failures"] == 1
    assert usage["cost_usd"] == pytest.approx(0.23) and usage["tool_calls"] >= 10

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
    assert usage["skipped_over_budget"] == 21 and usage["cost_usd"] == pytest.approx(0.30)
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
