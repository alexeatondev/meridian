"""Policy screen: versioned IPS (IC + CCO approval, redline) and named glide paths (IC approval)."""
import copy

import numpy as np
import pytest
from fastapi.testclient import TestClient

from meridian.policy import Policy, load_policy
from meridian.trading import glidepaths as GP

R = "UAT: reason long enough"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_AUTH", "dev")
    monkeypatch.setenv("MERIDIAN_DB_URL", f"sqlite:///{tmp_path}/app.db")
    monkeypatch.setenv("INGEST_TOKEN", "t0ken-for-tests")
    import meridian.app.main as mm
    mm._store = None
    return TestClient(mm.app)


def login(c, name, *roles, email=""):
    c.cookies.clear()
    c.post("/dev-login", data={"name": name, "email": email, "roles": list(roles)}, follow_redirects=False)
    from meridian.app import auth
    return {"X-CSRF-Token": auth._serializer().loads(c.cookies.get(auth.SESSION_COOKIE))["csrf"]}


def test_ips_versions_need_ic_and_cco(client):
    hp = login(client, "Maya Chen", "portfolio_manager")
    L = client.get("/api/policy/ips").json()
    assert L["current"] == 1 and L["versions"][0]["seeded"]
    cur = client.get("/api/policy/ips/1").json()["text"]
    assert cur.startswith("# Investment Policy Statement")
    new = cur.replace("At least annually", "At least twice a year", 1)
    assert client.post("/api/policy/ips", headers=hp, json={"text": new, "summary": "short"}).status_code == 400
    assert client.post("/api/policy/ips", headers=hp, json={"text": cur, "summary": "No change at all", "rules_change": False}).status_code == 400
    r = client.post("/api/policy/ips", headers=hp, json={"text": new, "summary": "Review the IPS twice a year", "rules_change": False})
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 2 and r.json()["changed_lines"] == 1
    assert client.post("/api/policy/ips", headers=hp, json={"text": new + "x", "summary": "Another change", "rules_change": False}).status_code == 409
    v2 = client.get("/api/policy/ips/2").json()
    assert v2["status"] == "pending" and v2["compare_to"] == 1
    chg = [x for x in v2["redline"] if x["op"] != "eq"]
    assert chg[0]["op"] == "chg" and ["ins", "twice a year;"] in [[o, t.strip()] for o, t in chg[0]["words"]]
    # the drafter can't approve, even holding the permission; an analyst can't draft
    hpi = login(client, "Maya Chen", "portfolio_manager", "investment_committee")
    assert client.post("/api/policy/ips/2/decide", headers=hpi, json={"action": "approve", "as": "ic", "reason": R}).status_code == 403
    ha = login(client, "Priya Raman", "analyst")
    assert client.post("/api/policy/ips", headers=ha, json={"text": new, "summary": "x" * 12, "rules_change": False}).status_code == 403
    # IC approval alone doesn't make it current
    hi = login(client, "Elena Rossi", "leadership", "investment_committee")
    assert client.post("/api/policy/ips/2/decide", headers=hi, json={"action": "approve", "as": "cco", "reason": R}).status_code == 403
    r = client.post("/api/policy/ips/2/decide", headers=hi, json={"action": "approve", "as": "ic", "reason": R})
    assert r.json() == {"ok": True, "status": "pending", "approvals": 1}
    # the same person can't give the second approval, even with both permissions
    hb = login(client, "Elena Rossi", "leadership", "investment_committee", "chief_compliance_officer")
    assert client.post("/api/policy/ips/2/decide", headers=hb, json={"action": "approve", "as": "cco", "reason": R}).status_code == 403
    hc = login(client, "Robert Hayes", "compliance", "chief_compliance_officer")
    r = client.post("/api/policy/ips/2/decide", headers=hc, json={"action": "approve", "as": "cco", "reason": R})
    assert r.json()["status"] == "approved"
    L = client.get("/api/policy/ips").json()
    assert L["current"] == 2 and [v["status"] for v in L["versions"]] == ["approved", "superseded"]
    import meridian.app.main as mm
    steps = [x["step"] for x in mm.store().ledger("governance") if x["dr_type"] == "policy_change"]
    assert steps == ["ips.propose", "ips.approve", "ips.approve", "ips.effective"]
    assert client.get("/api/policy/ledger").json()["records"][-1]["step"] == "ips.effective"


def test_ips_reject_and_withdraw(client):
    hp = login(client, "Maya Chen", "portfolio_manager")
    cur = client.get("/api/policy/ips/1").json()["text"]
    client.post("/api/policy/ips", headers=hp, json={"text": cur + "\nNew line.", "summary": "Add a closing line", "rules_change": True})
    hc = login(client, "Robert Hayes", "compliance", "chief_compliance_officer")
    assert client.post("/api/policy/ips/2/decide", headers=hc, json={"action": "withdraw", "reason": R}).status_code == 403
    assert client.post("/api/policy/ips/2/decide", headers=hc, json={"action": "reject", "as": "cco", "reason": R}).json()["status"] == "rejected"
    hp = login(client, "Maya Chen", "portfolio_manager")
    client.post("/api/policy/ips", headers=hp, json={"text": cur + "\nOther.", "summary": "Add another line", "rules_change": False})
    assert client.post("/api/policy/ips/3/decide", headers=hp, json={"action": "withdraw", "reason": R}).json()["status"] == "withdrawn"
    assert client.get("/api/policy/ips").json()["current"] == 1


def _anchors(eq_shift=0.0):
    a = copy.deepcopy(load_policy().raw["glide_path"]["anchors"])
    for r in a:                       # move eq_shift pp from core bonds to US large cap at every anchor
        r[1] += eq_shift
        r[7] -= eq_shift
    return a


def test_clean_anchors_validation():
    n = len(load_policy().assets)
    assert GP.clean_anchors(_anchors(), n)[0][0] == 40
    for bad, msg in [([_anchors()[0]], "at least two"), ([[40] + [10] * n, _anchors()[1]], "add to"),
                     ([_anchors()[0], _anchors()[0]], "appears twice"), ([[40, -1] + [101 / (n - 1)] * (n - 1), _anchors()[1]], "negative")]:
        with pytest.raises(ValueError, match=msg):
            GP.clean_anchors(bad, n)


def test_named_path_flows_to_trading_bands_and_export(client):
    hp = login(client, "Maya Chen", "portfolio_manager")
    r = client.post("/api/policy/glide-paths/requests", headers=hp, json={
        "kind": "new_path", "name": "Higher equity", "description": "2pp more US large cap", "anchors": _anchors(2), "reason": R})
    assert r.status_code == 200, r.text
    req = r.json()["request"]
    assert req["vs_ips"]["pp"] == pytest.approx(2.0) and req["vs_ips"]["equity_pp"] == pytest.approx(2.0)
    # not usable until approved
    assert client.post("/api/policy/glide-paths/requests", headers=hp, json={
        "kind": "assign", "path_id": req["path_id"], "funds": ["MTRS-2050"], "reason": R}).status_code == 400
    assert client.post(f"/api/policy/glide-paths/requests/{req['id']}/decide", headers=hp,
                       json={"action": "approve", "reason": R}).status_code == 403
    hi = login(client, "Elena Rossi", "leadership", "investment_committee")
    assert client.post(f"/api/policy/glide-paths/requests/{req['id']}/decide", headers=hi,
                       json={"action": "approve", "reason": R}).json()["status"] == "approved"
    hp = login(client, "Maya Chen", "portfolio_manager")
    a = client.post("/api/policy/glide-paths/requests", headers=hp, json={
        "kind": "assign", "path_id": req["path_id"], "funds": ["MTRS-2050", "MTRT-2050"], "reason": R}).json()["request"]
    from meridian.app.trading import base_aw, glide_export, model, neutral_aw
    import meridian.app.main as mm
    with mm.store().Session() as s:
        assert neutral_aw(s, "MTRS-2050") == pytest.approx(model().neutral_asset_weights("MTRS-2050"))   # not yet
    hi = login(client, "Elena Rossi", "leadership", "investment_committee")
    client.post(f"/api/policy/glide-paths/requests/{a['id']}/decide", headers=hi, json={"action": "approve", "reason": R})
    m = model()
    with mm.store().Session() as s:
        ips = m.neutral_asset_weights("MTRS-2050")
        assert base_aw(s, "MTRS-2050")["us_large_cap"] - ips["us_large_cap"] == pytest.approx(0.02, abs=1e-9)
        assert neutral_aw(s, "MTRS-2045") == pytest.approx(m.neutral_asset_weights("MTRS-2045"))
    gl = client.get("/api/policy/glide-paths").json()
    hi_eq = next(p for p in gl["paths"] if p["id"] == req["path_id"])
    assert hi_eq["funds"] == ["MTRS-2050", "MTRT-2050"] and hi_eq["version"] == 1
    # the agent export separates the path from adjustments; the policy centres the IPS bands on the path
    ex = glide_export()["vintages"]["2050"]
    assert ex["path_by_line"]["cit"]["us_large_cap"] == pytest.approx(0.02) and ex["by_line"]["mutual_fund"]["us_core_bond"] == pytest.approx(-0.02)
    raw = copy.deepcopy(load_policy().raw)
    raw["glide_adjustments"] = {"vintages": {"2050": ex}}
    n, base, adj = Policy(raw).adjusted_neutral(23.0, 2050)
    i = Policy(raw).assets.index("us_large_cap")
    assert np.allclose(n, base) and base[i] - Policy(raw).neutral_weights(23.0)[i] == pytest.approx(0.02, abs=1e-6)
    # a new version needs approval again; the IPS path can't be edited here
    hp = login(client, "Maya Chen", "portfolio_manager")
    assert client.post("/api/policy/glide-paths/requests", headers=hp, json={
        "kind": "new_version", "path_id": "ips", "anchors": _anchors(1), "reason": R}).status_code == 400
    v2 = client.post("/api/policy/glide-paths/requests", headers=hp, json={
        "kind": "new_version", "path_id": req["path_id"], "anchors": _anchors(3), "reason": R}).json()["request"]
    assert v2["version"] == 2
    with mm.store().Session() as s:      # still version 1 until approved
        assert base_aw(s, "MTRS-2050")["us_large_cap"] - ips["us_large_cap"] == pytest.approx(0.02, abs=1e-9)
    hi = login(client, "Elena Rossi", "leadership", "investment_committee")
    client.post(f"/api/policy/glide-paths/requests/{v2['id']}/decide", headers=hi, json={"action": "approve", "reason": R})
    with mm.store().Session() as s:
        assert base_aw(s, "MTRS-2050")["us_large_cap"] - ips["us_large_cap"] == pytest.approx(0.03, abs=1e-9)
    p = next(p for p in client.get("/api/policy/glide-paths").json()["paths"] if p["id"] == req["path_id"])
    assert [v["status"] for v in p["versions"]] == ["superseded", "active"]


def test_rejected_new_path_disappears(client):
    hp = login(client, "Maya Chen", "portfolio_manager")
    req = client.post("/api/policy/glide-paths/requests", headers=hp, json={
        "kind": "new_path", "name": "Lower equity", "anchors": _anchors(-2), "reason": R}).json()["request"]
    hi = login(client, "Elena Rossi", "leadership", "investment_committee")
    client.post(f"/api/policy/glide-paths/requests/{req['id']}/decide", headers=hi, json={"action": "reject", "reason": R})
    assert [p["id"] for p in client.get("/api/policy/glide-paths").json()["paths"]] == ["ips"]


def test_policy_page_and_nav(client):
    login(client, "Grace Liu", "audit")
    r = client.get("/policy")
    assert r.status_code == 200 and "Investment Policy Statement" in r.text and 'href="/policy"' in r.text or "/policy" in r.text


def test_pipeline_centres_bands_on_named_path(tmp_path, monkeypatch):
    import meridian.pipelines.target_date as TD
    raw = copy.deepcopy(load_policy().raw)
    d = {"us_large_cap": 0.04, "us_core_bond": -0.04}           # a path 4pp above the IPS path: outside the IPS band
    raw["glide_adjustments"] = {"vintages": {"2050": {"by_line": {"mutual_fund": d, "cit": d}, "path_by_line": {"mutual_fund": d, "cit": d},
                                                      "paths": {"mutual_fund": "higher-equity v1", "cit": "higher-equity v1"}, "ids": [], "labels": []}}}
    monkeypatch.setattr(TD, "load_policy", lambda: Policy(raw))
    r = TD.run(as_of="2026-10-31", out_root=tmp_path)
    v = r.vintages[2050]
    assert v["neutral_ips"]["us_large_cap"] - Policy(raw).neutral_weights(v["years_to_target"] if "years_to_target" in v else 23.17)[Policy(raw).assets.index("us_large_cap")] == pytest.approx(0.04, abs=2e-3)
    assert v["compliance_summary"]["FAIL"] == 0 and v["glide_adjustment"]["paths"]["cit"] == "higher-equity v1"
    assert max(abs(v["final"][a] - v["neutral_ips"][a]) for a in v["final"]) <= 0.03 + 1e-6
