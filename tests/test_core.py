import json

import numpy as np
import pytest

from meridian import entities
from meridian.compliance import evaluate, summarize
from meridian.data import DataRegistry, Request
from meridian.ledger import Ledger, verify
from meridian.policy import load_policy, load_universe


@pytest.fixture(scope="module")
def policy():
    return load_policy()


def test_glide_path_rows_sum_and_equity_declines(policy):
    for row in policy.raw["glide_path"]["anchors"]:
        assert abs(sum(row[1:]) - 100) < 1e-9, row
    eq = policy.group_mask("equity")
    shares = [eq @ policy.neutral_weights(v - 2026.8) for v in policy.vintages]
    assert all(a <= b + 1e-12 for a, b in zip(shares, shares[1:])), "equity must rise with years to target"
    assert 0.40 < shares[0] < 0.55 and shares[-1] > 0.80


def test_entity_merge_takes_strictest_retention_and_unions_rules():
    r = entities.resolve(["sec_ria", "broker_dealer"])
    assert r.retention_years == 6
    assert "chief_compliance_officer" in r.required_roles and "registered_principal" in r.required_roles
    assert r.approval_overrides["rebalance_material"]


def test_regime_scoped_rules_toggle(policy):
    u = load_universe()
    n = policy.neutral_weights(20)
    cov = np.eye(len(n)) * 0.02
    ria_only = {x.rule_id: x.status for x in evaluate(n, n, cov, policy, entities.resolve(["sec_ria"]), u)}
    fund = {x.rule_id: x.status for x in evaluate(n, n, cov, policy, entities.resolve(["registered_fund"]), u)}
    assert ria_only["DERIV-LDU"] == "OFF" and fund["DERIV-LDU"] in ("PASS", "FAIL")
    assert ria_only["LIQ-ILLIQUID-15"] == "OFF" and fund["LIQ-ILLIQUID-15"] == "PASS"


def test_engine_fails_out_of_band_portfolio(policy):
    u = load_universe()
    n = policy.neutral_weights(20)
    w = n.copy()
    w[0] += 0.10
    w[6] -= 0.10
    res = evaluate(w, n, np.eye(len(n)) * 0.02, policy, entities.resolve(["sec_ria"]), u)
    s = summarize(res)
    assert s["FAIL"] >= 1 and s["overall"] == "FAIL"


def test_ledger_detects_tampering(tmp_path):
    L = Ledger(tmp_path / "l.jsonl")
    for i in range(3):
        L.record(dr_type="signal", run_id="r", step=f"s{i}", actor={"id": "t"}, summary=str(i))
    assert verify(L.path)[0]
    lines = L.path.read_text().splitlines()
    rec = json.loads(lines[1]); rec["summary"] = "changed"; lines[1] = json.dumps(rec)
    L.path.write_text("\n".join(lines) + "\n")
    ok, msg = verify(L.path)
    assert not ok and "altered" in msg


def test_data_routing_falls_back_to_synthetic_and_records_attempts():
    reg = DataRegistry.from_config(overrides={"bloomberg_snowflake": True})   # enabled but no credentials
    u = load_universe()
    res = reg.get(Request("returns.monthly", list(u.values()), start="2010-01-31", end="2026-10-31"))
    assert res.synthetic and res.source == "synthetic"
    assert any(a["source"] == "bloomberg_snowflake" and a["status"].startswith("unavailable") for a in reg.attempts)


def test_pipeline_end_to_end(tmp_path):
    from meridian.pipelines.target_date import run
    r = run(as_of="2026-10-31", out_root=tmp_path)
    assert set(r.vintages) == set(load_policy().vintages)
    assert r.ledger_ok[0]
    for v, d in r.vintages.items():
        assert d["compliance_summary"]["FAIL"] == 0
        assert abs(sum(d["final"].values()) - 1) < 1e-3
        assert d["te"] <= 0.015
    assert "SYNTHETIC DATA" in r.memo_path.read_text()
    assert "DRAFT" in r.compliance_report_path.read_text()


def test_ledger_records_match_schema(tmp_path):
    import jsonschema
    from meridian import REPO_ROOT
    from meridian.pipelines.target_date import run
    schema = json.loads((REPO_ROOT / "schemas/decision_record.schema.json").read_text())
    r = run(out_root=tmp_path)
    for rec in Ledger(r.out_dir / "ledger.jsonl").records():
        jsonschema.validate(rec, schema)
