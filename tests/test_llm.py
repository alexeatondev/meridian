"""LLM path tests with a fake Anthropic client (no network, no key needed)."""
import json
import types

import pytest

import meridian.agents.runtime as rt


class FakeMessages:
    def __init__(self, script):
        self.script, self.calls = script, []

    def create(self, model, max_tokens, system, messages):
        task = messages[0]["content"]
        self.calls.append(task)
        text = self.script(system, task)
        if isinstance(text, Exception):
            raise text
        return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)],
                                     usage=types.SimpleNamespace(input_tokens=100, output_tokens=50))


def install(monkeypatch, script):
    fake = types.SimpleNamespace(messages=FakeMessages(script))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("MERIDIAN_LLM", "on")
    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", lambda: fake)
    return fake


def script(system, task):
    if "regime classification" in task:
        return json.dumps({"regime": "late_cycle", "confidence": 7, "rationale": "Payrolls softening; spreads tight."})
    if "US Large Cap" in task:
        return json.dumps({"weights": {"historical": -1, "building_block": 2}, "rationale": "bad weights"})  # must be rejected
    if "expected return" in task:
        return 'Sure! {"weights": {"building_block": 0.5, "equilibrium": 0.5, "made_up": 9}, "rationale": "Blend."}'
    if "2030 vintage" in task:
        return json.dumps({"ensemble": "yolo_leverage", "rationale": "ignore your rules"})          # must be rejected
    if "ensemble method" in task:
        return json.dumps({"ensemble": "simple_average", "rationale": "Robust to CMA noise.",
                           "invalidation_conditions": ["Recession probability > 50%"]})
    if "compliance review" in task:
        return RuntimeError("simulated API outage")                                                   # must fall back
    return "{}"


def test_llm_path_validates_and_falls_back(monkeypatch, tmp_path):
    fake = install(monkeypatch, script)
    from meridian.pipelines.target_date import run
    from meridian.ledger import Ledger
    r = run(out_root=tmp_path)
    recs = Ledger(r.out_dir / "ledger.jsonl").records()
    by = {x["step"]: x for x in recs}
    macro = by["macro-regime"]["output"]
    assert macro["judge_path"] == "llm" and macro["confidence"] == 1.0          # clamped
    assert by["ac-us_large_cap.cma-judge"]["output"]["judge_path"] == "offline"  # negative weight rejected
    sm = by["ac-us_small_mid_cap.cma-judge"]["output"]
    assert sm["judge_path"] == "llm" and set(sm["weights"]) == {"building_block", "equilibrium"}
    assert r.vintages[2030]["ensemble"] == "inverse_tracking_error"            # unknown ensemble rejected
    assert r.vintages[2050]["ensemble"] == "simple_average"
    assert all(v["compliance_summary"]["FAIL"] == 0 for v in r.vintages.values())
    assert by["llm.usage"]["output"]["calls"] >= 20
    assert "Compliance Review" in r.compliance_report_path.read_text()          # ACO survived the outage
    assert len(fake.messages.calls) >= 24
