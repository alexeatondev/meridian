"""Approved glide-path adjustments reach the agent pipeline (doc 03 next step 3, 2026-11-18)."""
import copy

import numpy as np
import pytest
from fastapi.testclient import TestClient

from meridian.compliance import evaluate
from meridian.entities import resolve
from meridian.policy import Policy, load_policy, load_universe

R = "UAT: reason long enough"


def _with_adj(by_line: dict, vintage: int = 2050) -> Policy:
    raw = copy.deepcopy(load_policy().raw)
    raw["glide_adjustments"] = {"vintages": {str(vintage): {"by_line": by_line, "ids": ["GPA-1"], "labels": ["GPA-1: test"]}}}
    return Policy(raw)


def test_policy_adjusted_neutral_and_band_check():
    p = _with_adj({"mutual_fund": {"us_large_cap": 0.01, "us_core_bond": -0.01},
                   "cit": {"us_large_cap": 0.01, "us_core_bond": -0.01}})
    n, ips, adj = p.adjusted_neutral(23.0, 2050)
    i, j = p.assets.index("us_large_cap"), p.assets.index("us_core_bond")
    assert n[i] - ips[i] == pytest.approx(0.01) and n[j] - ips[j] == pytest.approx(-0.01) and not adj["lines_differ"]
    n2, _, adj2 = p.adjusted_neutral(23.0, 2045)
    assert np.allclose(n2, p.neutral_weights(23.0)) and not adj2["ids"]
    # lines differ -> average
    q = _with_adj({"mutual_fund": {"us_large_cap": 0.02, "us_core_bond": -0.02}, "cit": {}})
    _, _, a = q.adjusted_neutral(23.0, 2050)
    assert a["lines_differ"] and a["delta"][i] == pytest.approx(0.01)
    with pytest.raises(ValueError):
        _with_adj({"cit": {"bitcoin": 0.01}}).glide_adjustment(2050)
    # the IPS bands are measured from the IPS glide path, not the adjusted one
    cov = np.eye(len(p.assets)) * 0.01
    w = ips.copy()
    w[i] += 0.035
    w[j] -= 0.035
    band = lambda res: next(r for r in res if r.kind == "band_vs_neutral")
    on_adj = band(evaluate(w, n, cov, p, resolve(), load_universe()))
    on_ips = band(evaluate(w, n, cov, p, resolve(), load_universe(), band_neutral=ips))
    assert on_adj.status == "PASS" and on_ips.status == "FAIL"


def test_pipeline_builds_on_adjusted_glide_path(tmp_path, monkeypatch):
    import meridian.pipelines.target_date as TD
    p = _with_adj({"mutual_fund": {"us_large_cap": 0.02, "us_core_bond": -0.02},
                   "cit": {"us_large_cap": 0.02, "us_core_bond": -0.02}})
    monkeypatch.setattr(TD, "load_policy", lambda: p)
    r = TD.run(as_of="2026-10-31", out_root=tmp_path)
    d50, d45 = r.vintages[2050], r.vintages[2045]
    assert d50["neutral"]["us_large_cap"] - d50["neutral_ips"]["us_large_cap"] == pytest.approx(0.02, abs=1e-3)
    assert d50["glide_adjustment"]["ids"] == ["GPA-1"] and d45["glide_adjustment"] is None
    assert d50["compliance_summary"]["FAIL"] == 0
    # every asset stays within 3pp of the IPS glide path even though the managed glide path moved 2pp
    assert max(abs(d50["final"][a] - d50["neutral_ips"][a]) for a in d50["final"]) <= 0.03 + 1e-6
    recs = [x for x in r.out_dir.joinpath("ledger.jsonl").read_text().splitlines() if "glide-path.adjustments" in x]
    assert len(recs) == 1
    memo = r.memo_path.read_text()
    assert "Investment Committee glide-path adjustments in force" in memo and "GPA-1" in memo


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_AUTH", "dev")
    monkeypatch.setenv("MERIDIAN_DB_URL", f"sqlite:///{tmp_path}/app.db")
    monkeypatch.setenv("INGEST_TOKEN", "t0ken-for-tests")
    import meridian.app.main as mm
    mm._store = None
    return TestClient(mm.app)


def login(c, name, *roles):
    c.cookies.clear()
    c.post("/dev-login", data={"name": name, "roles": list(roles)}, follow_redirects=False)
    from meridian.app import auth
    return {"X-CSRF-Token": auth._serializer().loads(c.cookies.get(auth.SESSION_COOKIE))["csrf"]}


def test_export_carries_approved_adjustments_per_line(client):
    hp = login(client, "Maya Chen", "portfolio_manager")
    req = client.post("/api/trading/glide-path/requests", headers=hp, json={
        "scope": "vehicle:cit", "vintages": [2050, 2055], "reason": R,
        "shifts": [{"asset_class": "us_large_cap", "from": "us_core_bond", "pp": 1}]})
    assert req.status_code == 200, req.text
    hi = login(client, "Elena Rossi", "leadership", "investment_committee")
    rid = req.json()["id"]
    assert client.post(f"/api/trading/glide-path/requests/{rid}/decide", headers=hi,
                       json={"decision": "approve", "reason": R}).status_code == 200
    from meridian.app.trading import glide_export
    ex = glide_export()["vintages"]
    assert set(ex) == {"2050", "2055"}
    assert ex["2050"]["by_line"]["cit"] == {"us_large_cap": 0.01, "us_core_bond": -0.01}
    assert ex["2050"]["by_line"]["mutual_fund"] == {}
    ov = client.get("/api/export/policy-overrides", headers={"Authorization": "Bearer t0ken-for-tests"})
    assert ov.status_code == 200 and "2050" in ov.json()["glide_adjustments"]["vintages"]
    # the workflow writes it into the policy file; the policy reads it back with the lines' average
    from meridian.app.store import apply_overrides
    raw = copy.deepcopy(load_policy().raw)
    apply_overrides(raw, ov.json())
    a = Policy(raw).glide_adjustment(2050)
    assert a["lines_differ"] and a["delta"][Policy(raw).assets.index("us_large_cap")] == pytest.approx(0.005)


def test_approved_table_adds_each_lines_own_difference(client):
    hp = login(client, "Maya Chen", "portfolio_manager")
    req = client.post("/api/trading/glide-path/requests", headers=hp, json={
        "scope": "vehicle:cit", "vintages": [2050], "reason": R,
        "shifts": [{"asset_class": "us_large_cap", "from": "us_core_bond", "pp": 1}]}).json()
    hi = login(client, "Elena Rossi", "leadership", "investment_committee")
    client.post(f"/api/trading/glide-path/requests/{req['id']}/decide", headers=hi, json={"decision": "approve", "reason": R})
    import meridian.app.main as mm
    from meridian.app.store import Position, Run
    from meridian.app.trading import approved_aw_for_fund
    ips = load_policy().neutral_weights(23.2)
    assets = load_policy().assets
    with mm.store().Session.begin() as s:
        # a run made after the feed: it built in the average of the two lines (0.5pp)
        s.add(Run(id="run_x", as_of="2026-10-31", results={"vintages": {"2050": {"glide_adjustment": {
            "applied": {"us_large_cap": 0.005, "us_core_bond": -0.005}}}}}))
        for a, x in zip(assets, ips):
            s.add(Position(as_of="2026-10-31", vintage=2050, asset=a, weight=float(x), run_id="run_x", status="approved"))
    with mm.store().Session() as s:
        cit, src, rc = approved_aw_for_fund(s, "MTRT-2050")
        mf, _, rm = approved_aw_for_fund(s, "MTRS-2050")
    assert src.startswith("run_x")
    assert rc == pytest.approx({"us_large_cap": 0.005, "us_core_bond": -0.005})
    assert rm == pytest.approx({"us_large_cap": -0.005, "us_core_bond": 0.005})
    assert cit["us_large_cap"] - mf["us_large_cap"] == pytest.approx(0.01, abs=1e-9)
    hp = login(client, "Maya Chen", "portfolio_manager")
    d = client.get("/api/trading/funds/MTRT-2050").json()
    assert d["approved"]["line_adjustment_pp"] == pytest.approx({"us_large_cap": 0.5, "us_core_bond": -0.5})
