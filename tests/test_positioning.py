import json

import numpy as np
import pytest

from meridian.analytics.positioning import Taxonomy, apply_adjustment, parse_adjustment, positioning_table
from meridian.policy import load_policy


@pytest.fixture(scope="module")
def tax():
    return Taxonomy.load(load_policy().assets)


def node(tax, w, name):
    names, M = tax.node_matrix()
    return float(M[names.index(name)] @ w)


def test_tree_totals_add_up(tax):
    w = load_policy().neutral_weights(20)
    tops = sum(node(tax, w, t) for t in ["Equity", "Fixed Income", "Real Assets"])
    assert abs(tops - 1) < 1e-9
    assert abs(node(tax, w, "Fixed Income/Long-dated") + node(tax, w, "Fixed Income/Short-dated") - node(tax, w, "Fixed Income")) < 1e-9


def test_relative_fi_long_to_short_keeps_other_groups(tax):
    w = load_policy().neutral_weights(5)
    w1 = apply_adjustment(w, tax, "Fixed Income/Short-dated", "relative", 0.02, "Fixed Income/Long-dated")
    assert abs(node(tax, w1, "Fixed Income/Short-dated") - node(tax, w, "Fixed Income/Short-dated") - 0.02) < 1e-9
    assert abs(node(tax, w1, "Equity") - node(tax, w, "Equity")) < 1e-9
    assert abs(w1.sum() - 1) < 1e-9


def test_absolute_equity_target(tax):
    w = load_policy().neutral_weights(25)
    w1 = apply_adjustment(w, tax, "Equity", "absolute", 0.80)
    assert abs(node(tax, w1, "Equity") - 0.80) < 1e-9


def test_parse_and_guardrails(tax):
    assert parse_adjustment("Equity=+1.5pp")["value"] == pytest.approx(0.015)
    assert parse_adjustment("Fixed Income/Short-dated=+2pp from Fixed Income/Long-dated")["funded_from"] == "Fixed Income/Long-dated"
    w = load_policy().neutral_weights(25)
    with pytest.raises(ValueError):
        apply_adjustment(w, tax, "Fixed Income/Short-dated/TIPS", "relative", 0.5, "Fixed Income/Long-dated")
    with pytest.raises(ValueError):
        apply_adjustment(w, tax, "Equity", "relative", 0.01, "Equity/US")


def test_pipeline_positioning_metrics_and_adjust(tmp_path):
    from meridian.adjustments import adjust
    from meridian.approvals import record_decision
    from meridian.ledger import verify
    from meridian.pipelines.target_date import run
    r = run(out_root=tmp_path)
    d = r.vintages[2050]
    assert d["risk"]["used_pct"] <= 1.0 and d["risk"]["budget"] == load_policy().risk_budget(2050)
    tree = d["positioning"]["views"]["asset_class_tree"]
    assert {"current", "last_week", "last_month", "glide_path", "market", "relative_vs_market", "risk_budget_used"} <= set(tree[0])
    m = d["metrics"]["5y"]["portfolio"]
    assert 0.3 < m["beta_vs_market"] < 2.0 and m["window_months"] == 60
    out = adjust(r.out_dir, 2050, ["Fixed Income/Short-dated=+1pp from Fixed Income/Long-dated"], "Analyst A", "analyst",
                 "Shorten duration ahead of supply.")
    assert out["compliance_summary"]["FAIL"] == 0 and verify(r.out_dir / "ledger.jsonl")[0]
    with pytest.raises(SystemExit):
        adjust(r.out_dir, 2050, ["Equity=+1pp"], "X", "risk", "risk cannot adjust weights")
    assert record_decision(r.out_dir, 2050, "risk", "Risk R", "approve", "Duration shift within budget.").startswith("dr_")
    big = adjust(r.out_dir, 2050, ["Equity=+8pp"], "PM", "portfolio_manager", "Testing a breach of the band.")
    assert big["compliance_summary"]["FAIL"] >= 1
    with pytest.raises(SystemExit):
        record_decision(r.out_dir, 2050, "portfolio_manager", "PM", "approve", "should be blocked by FAIL")


def test_risk_budget_change_request_flow(tmp_path):
    import shutil
    from meridian import governance as gv
    from meridian.policy import POLICY_PATH, load_policy as lp
    pol = tmp_path / "policy.yaml"
    shutil.copy(POLICY_PATH, pol)
    gd = tmp_path / "gov"
    with pytest.raises(SystemExit):
        gv.request_risk_budget_change(2050, 0.02, "PM", "portfolio_manager", "above hard limit test", gd, pol)
    cr = gv.request_risk_budget_change(2050, 0.009, "PM", "portfolio_manager", "Tighter budget late cycle.", gd, pol)
    with pytest.raises(SystemExit):
        gv.approve_change(cr["id"], "PM", "portfolio_manager", "approve", "self approval attempt", gd, pol)
    gv.approve_change(cr["id"], "PM2", "portfolio_manager", "approve", "Agree with tighter budget.", gd, pol)
    assert lp(pol).risk_budget(2050) == load_policy().risk_budget(2050)        # not applied yet
    done = gv.approve_change(cr["id"], "Risk", "risk", "approve", "Risk agrees, consistent with regime.", gd, pol)
    assert done["status"] == "applied" and lp(pol).risk_budget(2050) == 0.009
    assert "# Operating risk budgets" in pol.read_text()
