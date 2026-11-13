"""Fund-level regulations (doc 18), plus next-step items: approved-proposal table, rebalance, positions upload,
fills and booking, market holidays and Treasury issuer consolidation (F-4)."""
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from meridian import regulations as RG
from meridian.trading import load_model

R = "UAT: reason long enough"


def test_library_has_domestic_and_international():
    lib = RG.library()["regulations"]
    assert {"ICA40", "ERISA", "OCC_CIT"} <= set(lib) and {"UCITS", "UK_UCITS", "CA_81102"} <= set(lib)
    assert {r["scope"] for r in lib.values()} == {"domestic", "international"}
    assert lib["ICA40"]["short"] == "ACT 40"
    for r in lib.values():
        assert r["counsel_review"] == "required" and r["obligations"]


def test_controls_on_holdings():
    m = load_model()
    rows = RG.holdings_rows(m.example_positions("MTRS-2050"), m.instruments)
    act40 = RG.evaluate_controls(rows, m.instruments, [{"reg_id": "ICA40"}])
    assert RG.overall(act40) == "PASS"
    ucits = {r["rule_id"]: r for r in RG.evaluate_controls(rows, m.instruments, [{"reg_id": "UCITS"}])}
    assert ucits["UCITS-55-SINGLE"]["status"] == "FAIL"           # US large cap fund is ~45% of the fund
    assert ucits["UCITS-55-NONUCITS"]["status"] == "FAIL"
    # a big unaffiliated ETF breaches 12(d)(1)(A) unless the fund relies on Rule 12d1-4
    big = rows + [{"instrument": "IEFA", "type": "etf", "post_w": 0.08}]
    r = {x["rule_id"]: x for x in RG.evaluate_controls(big, m.instruments, [{"reg_id": "ICA40"}])}
    assert r["ICA-12D1-UNAFF"]["status"] == "FAIL"
    r = {x["rule_id"]: x for x in RG.evaluate_controls(big, m.instruments, [{"reg_id": "ICA40", "params": {"rule_12d1_4": True}}])}
    assert r["ICA-12D1-UNAFF"]["status"] == "PASS"


def test_schedules():
    ob = {"frequency": "quarterly", "due_days": 60}
    t = RG.first_task(ob, date(2026, 11, 10))
    assert t == {"period": "Q4 2026", "period_end": "2026-12-31", "due": "2027-03-01"}
    assert RG.next_task(ob, t["period_end"])["period"] == "Q1 2027"
    assert RG.first_task({"frequency": "once", "due_days": 30}, date(2026, 11, 10))["due"] == "2026-12-10"
    assert RG.next_task({"frequency": "once", "due_days": 30}, "2026-11-10") is None
    assert RG.first_task({"frequency": "annual", "due_days": 75}, date(2026, 11, 10))["due"] == "2027-03-16"


def test_treasury_issuer_consolidated():
    from meridian.analytics.risk import normalize_issuers
    h = pd.DataFrame({"name": ["TREASURY NOTE", "TREASURY (CPI) NOTE", "TBILL TREASURY BILL", "APPLE INC",
                               "TREASURY WINE ESTATES"], "country": ["United States"] * 4 + ["Australia"],
                      "ticker": ["T", "TII", "B", "AAPL", "TWE"], "sector": "", "asset_class": "", "security_id": list("abcde")})
    out = normalize_issuers(h)
    assert out["security_id"].tolist()[:3] == ["UST|United States|Treasury"] * 3
    assert out["name"].tolist()[3:] == ["APPLE INC", "TREASURY WINE ESTATES"]


def test_holidays_block_tranche_dates():
    from meridian.trading.allocate import validate_schedule
    m = load_model()
    errs = validate_schedule([{"date": "2026-11-26", "pct": 100}], "2026-11-20", holidays=m.holidays)
    assert any("market holiday" in e for e in errs)


# ---------------------------------------------------------------------------------------------- API
@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_AUTH", "dev")
    monkeypatch.setenv("MERIDIAN_DB_URL", f"sqlite:///{tmp_path}/app.db")
    import meridian.app.main as mm
    mm._store = None
    return TestClient(mm.app)


def login(c, name, *roles):
    c.cookies.clear()
    c.post("/dev-login", data={"name": name, "roles": list(roles)}, follow_redirects=False)
    from meridian.app import auth
    return {"X-CSRF-Token": auth._serializer().loads(c.cookies.get(auth.SESSION_COOKIE))["csrf"]}


def test_tagging_obligations_and_controls_in_trading(client, monkeypatch):
    ha = login(client, "Nina Alvarez", "compliance")
    st = client.get("/api/regulations/state").json()
    f = {x["id"]: x for x in st["funds"]}
    assert f["MTRS-2050"]["suggested"] == ["ICA40"] and f["MTRT-2050"]["suggested"] == ["ERISA", "OCC_CIT"]
    assert client.post("/api/regulations/tags", headers=ha, json={"reg_id": "ICA40", "fund_ids": ["MTRS-2050"],
                                                                  "reason": "short"}).status_code == 400
    r = client.post("/api/regulations/tags", headers=ha, json={"reg_id": "ICA40", "fund_ids": ["MTRS-2050", "MTRS-2040"],
                                                               "reason": R})
    assert r.status_code == 200 and r.json()["tasks_created"] == 2 * len(RG.library()["regulations"]["ICA40"]["obligations"])
    assert client.post("/api/regulations/tags", headers=ha, json={"reg_id": "UCITS", "fund_ids": ["MTRS-2050"],
                                                                  "reason": R}).status_code == 200
    st = client.get("/api/regulations/state").json()
    f = {x["id"]: x for x in st["funds"]}["MTRS-2050"]
    assert [t["regulation"] for t in f["tags"]] == ["ACT 40", "UCITS"] or sorted(t["regulation"] for t in f["tags"]) == ["ACT 40", "UCITS"]
    assert f["controls_status"] == "FAIL" and f["retention_years"] == 6
    assert any(not r_["filled"] for r_ in f["roles"])                # e.g. fund board unfilled
    # a PM can't tag; compliance analyst can't remove; the CCO can
    hp = login(client, "Maya Chen", "portfolio_manager", "approver")
    assert client.post("/api/regulations/tags", headers=hp, json={"reg_id": "ICA40", "fund_ids": ["MTRS-2030"],
                                                                  "reason": R}).status_code == 403
    # regulation controls flow into trading: UCITS FAIL blocks the 2050 trade list
    client.post("/api/trading/cashflows", headers=hp, json={"trade_date": "2026-11-10", "fund_id": "MTRS-2050", "amount": 1e7})
    hp = login(client, "Maya Chen", "portfolio_manager", "approver")
    tl = client.post("/api/trading/trade-lists", headers=hp, json={"trade_date": "2026-11-10", "strategy": "neutral"}).json()
    comp = tl["funds"][0]["compliance"]
    assert comp["status"] == "FAIL" and "MTRS-2050" in tl["blocked_funds"]
    assert {x["rule_id"] for x in comp["regulations"]} >= {"UCITS-55-SINGLE", "ICA-12D1-UNAFF"}
    ha = login(client, "Nina Alvarez", "compliance")
    assert client.post("/api/regulations/tags/remove", headers=ha, json={"reg_id": "UCITS", "fund_ids": ["MTRS-2050"],
                                                                         "reason": R}).status_code == 403
    hc = login(client, "Robert Hayes", "compliance", "chief_compliance_officer")
    rm = client.post("/api/regulations/tags/remove", headers=hc, json={"reg_id": "UCITS", "fund_ids": ["MTRS-2050"], "reason": R})
    assert rm.status_code == 200 and rm.json()["cancelled_tasks"] == len(RG.library()["regulations"]["UCITS"]["obligations"])

    # obligations: complete needs evidence and creates the next occurrence; waive needs the CCO
    st = client.get("/api/regulations/state").json()
    nport = next(t for t in st["tasks"] if t["obligation_id"] == "ICA-NPORT" and t["fund_id"] == "MTRS-2050")
    ha = login(client, "Nina Alvarez", "compliance")
    assert client.post(f"/api/regulations/tasks/{nport['id']}/actions", headers=ha,
                       json={"action": "complete", "evidence": "x"}).status_code == 400
    done = client.post(f"/api/regulations/tasks/{nport['id']}/actions", headers=ha,
                       json={"action": "complete", "evidence": "EDGAR accession 0001-26-000123"})
    assert done.status_code == 200 and done.json()["next_task"]
    once = next(t for t in st["tasks"] if t["obligation_id"] == "ICA-SETUP" and t["fund_id"] == "MTRS-2050")
    assert client.post(f"/api/regulations/tasks/{once['id']}/actions", headers=ha,
                       json={"action": "waive", "note": "Not needed for the pilot"}).status_code == 403
    hc = login(client, "Robert Hayes", "compliance", "chief_compliance_officer")
    w = client.post(f"/api/regulations/tasks/{once['id']}/actions", headers=hc, json={"action": "waive", "note": "Not needed for the pilot"})
    assert w.status_code == 200 and w.json()["next_task"] is None

    # overdue obligations open one exception each
    import meridian.app.regulations as AR
    monkeypatch.setattr(AR, "_today", lambda: date(2028, 1, 1))
    st = client.get("/api/regulations/state").json()
    esc = [t for t in st["tasks"] if t.get("escalated")]
    assert esc and all(t["status"] in ("open", "in_progress") for t in esc)
    from meridian.app.oversight import list_cases
    n = len(list_cases())
    client.get("/api/regulations/state")
    assert len(list_cases()) == n and n >= len(esc)                       # escalated once only
    from meridian.app.main import store
    steps = [r["step"] for r in store().ledger("governance") if r["dr_type"] == "regulation"]
    assert steps[:3] == ["regulation.tag", "regulation.tag", "regulation.remove"] and "obligation.complete" in steps


def test_approved_table_rebalance_positions_and_fills(client):
    hp = login(client, "Maya Chen", "portfolio_manager", "approver")
    # approved proposal: none yet -> clear error
    r = client.post("/api/trading/rebalance", headers=hp, json={"strategy": "approved", "fund_ids": ["MTRS-2050"],
                                                               "trade_date": "2026-11-10", "reason": R})
    assert r.status_code == 409 and "no approved proposal" in r.json()["detail"]
    from meridian.app.main import store
    from meridian.app.store import Position
    m = load_model()
    aw = m.neutral_asset_weights("MTRS-2050")
    aw = dict(aw, us_large_cap=aw["us_large_cap"] + 0.02, us_core_bond=aw["us_core_bond"] - 0.02)
    with store().Session.begin() as s:
        for a, w in aw.items():
            s.add(Position(as_of="2026-10-31", vintage=2050, asset=a, weight=w, run_id="run_x", status="approved"))
    d = client.get("/api/trading/funds/MTRS-2050").json()
    row = {x["instrument"]: x for x in d["rows"]}
    assert row["MER-USLC-MF"]["t_approved"] == pytest.approx(row["MER-USLC-MF"]["t_neutral"] + 0.02, abs=1e-6)
    rb = client.post("/api/trading/rebalance", headers=hp, json={"strategy": "approved", "fund_ids": ["MTRS-2050"],
                                                                "trade_date": "2026-11-10", "min_drift_bps": 0, "reason": R}).json()
    assert rb["id"].startswith("RB-") and rb["kind"] == "rebalance" and not rb["funds"][0]["errors"]
    post = {x["instrument"]: x for x in rb["funds"][0]["preview"]}
    assert abs(post["MER-USLC-MF"]["post_w"] - post["MER-USLC-MF"]["target_w"]) < 0.001
    assert post["MER-LISC-MF"]["trade"] == 0                       # no target: untouched

    # positions upload replaces example holdings for the funds in the file
    csv_text = ("as_of,fund_id,security_id,quantity,price,market_value\n"
                "2026-11-10,MF2030,MER-USLC-MF,1000000,40,\n2026-11-10,MTRS-2030,VNQ,,,5000000\n"
                "2026-11-10,MTRS-2030,CASH,,,1000000\n")
    bad = client.post("/api/trading/positions/upload", headers=hp,
                      files={"file": ("p.csv", (csv_text + "2026-11-10,MTRS-2030,NOPE,,,1\n").encode(), "text/csv")})
    assert bad.status_code == 400 and "unknown security" in bad.json()["detail"]
    ok = client.post("/api/trading/positions/upload", headers=hp, files={"file": ("p.csv", csv_text.encode(), "text/csv")})
    assert ok.status_code == 200 and ok.json()["funds"] == ["MTRS-2030"]
    d = client.get("/api/trading/funds/MTRS-2030").json()
    assert d["nav"] == pytest.approx(46e6) and d["cash"] == 1e6 and "Uploaded" in d["positions_source"]

    # cashflow -> approve -> export -> fills book to positions
    client.post("/api/trading/cashflows", headers=hp, json={"trade_date": "2026-11-10", "fund_id": "MTRS-2030", "amount": 4e6})
    hp = login(client, "Maya Chen", "portfolio_manager", "approver")
    tl = client.post("/api/trading/trade-lists", headers=hp, json={"trade_date": "2026-11-10", "strategy": "previous_close"}).json()
    client.post(f"/api/trading/trade-lists/{tl['id']}/approve", headers=hp, json={"checked": True, "reason": R})
    assert client.post(f"/api/trading/trade-lists/{tl['id']}/fills", headers=hp, json={"all": True}).status_code == 409
    rows = client.get(f"/api/trading/trade-lists/{tl['id']}/crd.csv").text.splitlines()
    first_id = rows[1].split(",")[0]
    part = ("External Order ID,Filled Quantity,Fill Price,Status\n" + f"{first_id},10,40.5,PARTIAL\n").encode()
    pr = client.post(f"/api/trading/trade-lists/{tl['id']}/fills", headers=hp, files={"file": ("f.csv", part, "text/csv")})
    assert pr.status_code == 200 and pr.json()["fill_status"] == "partially_filled"
    d = client.get("/api/trading/funds/MTRS-2030").json()
    assert d["cash"] == pytest.approx(1e6 + 4e6 - 10 * 40.5)             # cashflow settled, partial fill paid
    al = client.post(f"/api/trading/trade-lists/{tl['id']}/fills", headers=hp, json={"all": True})
    assert al.status_code == 200 and al.json()["fill_status"] == "filled"
    t = client.get(f"/api/trading/trade-lists/{tl['id']}").json()
    assert t["status"] == "filled"
    d = client.get("/api/trading/funds/MTRS-2030").json()
    assert d["nav"] == pytest.approx(50e6, rel=1e-3) and 0 <= d["cash"] < 1e6 + 1e5
