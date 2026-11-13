"""Exceptions (auto-open, lifecycle rules, governance ledger), ledger search, previous-run summary."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient

R = "UAT: reason long enough"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_AUTH", "dev")
    monkeypatch.setenv("MERIDIAN_DB_URL", f"sqlite:///{tmp_path}/app.db")
    import meridian.app.main as m
    m._store = None
    return TestClient(m.app)


def login(c, name, *roles, email=""):
    c.cookies.clear()
    c.post("/dev-login", data={"name": name, "email": email, "roles": list(roles)}, follow_redirects=False)
    from meridian.app import auth
    return {"X-CSRF-Token": auth._serializer().loads(c.cookies.get(auth.SESSION_COOKIE))["csrf"]}


def test_rule_engine_warn_and_fail_open_exceptions_once(client):
    from meridian.app.oversight import list_cases, open_from_run
    login(client, "x", "audit")           # initialise the store
    results = {"vintages": {"2040": {"compliance": [
        {"rule_id": "POL-BAND-ASSET", "status": "FAIL", "measured": 0.31, "limit": 0.30, "ips": "§6.3", "severity": "hard", "detail": ""},
        {"rule_id": "TE-WARN", "status": "WARN", "measured": 0.011, "limit": 0.012, "ips": "§6.4", "severity": "warn", "detail": ""},
        {"rule_id": "POL-SUM", "status": "PASS"}]}}}
    assert len(open_from_run("run_a", results)) == 2
    assert open_from_run("run_a", results) == []                      # idempotent per run/vintage/rule
    cases = {c["rule_id"]: c for c in list_cases()}
    fail = cases["POL-BAND-ASSET"]
    assert fail["severity"] == "fail" and fail["source"] == "rule-engine" and "Measured 0.31 vs limit 0.3" in fail["details"]
    assert fail["due"] == (dt.date.today() + dt.timedelta(days=5)).isoformat()


def test_lifecycle_rules_and_governance_chain(client):
    h = login(client, "Nina Alvarez", "compliance")
    c = client.post("/api/exceptions", json={"title": "Guideline breach", "severity": "fail", "reason": R}, headers=h).json()
    act = lambda hh, body: client.post(f"/api/exceptions/{c['id']}/actions", json=body, headers=hh)
    assert act(h, {"action": "close", "reason": R}).status_code == 400                 # not remediated yet
    assert act(h, {"action": "remediate", "reason": R}).status_code == 200
    assert act(h, {"action": "close", "reason": R}).status_code == 400                 # opener alone can't close
    h2 = login(client, "Robert Hayes", "compliance")
    assert act(h2, {"action": "close", "reason": R}).status_code == 200
    h3 = login(client, "Maya Chen", "portfolio_manager", "approver")
    assert act(h3, {"action": "reopen", "reason": R}).status_code == 403
    from meridian.app.main import _verify_records, store
    gov = store().ledger("governance")
    assert [r["step"] for r in gov] == ["exception.open", "exception.remediate", "exception.close"]
    assert _verify_records(gov)[0]                                                     # hash chain intact


def test_search_filters_and_roles(client):
    from meridian.app.main import store
    login(client, "x", "audit")
    from meridian.app.oversight import open_case
    with store().Session.begin() as s:
        open_case(s, title="Alpha case", severity="warn", actor={"name": "Nina"}, reason=R, vintage=2050)
    h = login(client, "Grace Liu", "audit")
    j = client.get("/api/ledger/search", params={"dr_type": "exception", "vintage": "2050"}).json()
    assert j["matches"] == 1 and j["results"][0]["step"] == "exception.open"
    assert client.get("/api/ledger/search", params={"vintage": "2030"}).json()["matches"] == 0
    assert client.get("/api/ledger/search", params={"format": "csv"}).text.startswith("run_id,")
    login(client, "Maya Chen", "portfolio_manager", "approver")
    assert client.get("/api/ledger/search").status_code == 403
