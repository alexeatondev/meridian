"""Cashflows, allocation strategies, routing, buffer, exclusions, trade lists and the Charles River file (doc 17)."""
import csv
import io

import pytest
from fastapi.testclient import TestClient

from meridian.trading import allocate_fund, load_model
from meridian.trading.model import last_roll_date

R = "UAT: reason long enough"


@pytest.fixture(scope="module")
def m():
    return load_model()


def test_both_vehicles_every_vintage_and_roll_downs(m):
    assert len(m.fund_ids("mutual_fund")) == len(m.fund_ids("cit")) == len(m.policy.vintages)
    assert m.funds["MTRS-2050"].vehicle == "mutual_fund" and m.funds["MTRT-2050"].vehicle == "cit"
    assert m.funds["MTRS-2050"].roll_down == "monthly" and m.funds["MTRS-2070"].roll_down == "annual"
    assert m.funds["MTRT-2050"].roll_down == "semiannual"
    import datetime as dt
    d = dt.date(2026, 11, 9)
    assert [last_roll_date(d, f).isoformat() for f in ("monthly", "quarterly", "semiannual", "annual")] == \
        ["2026-11-01", "2026-10-01", "2026-07-01", "2026-01-01"]


def test_tables_sum_to_one_and_skip_no_target(m):
    for fid in ("MTRS-2040", "MTRT-2040"):
        p = m.example_positions(fid)
        for t in (m.neutral_table(fid), m.previous_close_table(fid, p["values"])):
            assert abs(sum(t.values()) - 1) < 1e-9
            assert "MER-LISC-MF" not in t and "IEFA" not in t          # no target / candidate never allocated
    assert m.example_positions("MTRS-2040")["values"]["MER-LISC-MF"] > 0  # but the legacy holding is held


def test_inflow_is_pro_rata_with_routes_buffer_and_exclusion(m):
    fid = "MTRS-2030"              # near target: holds cash-sleeve T-bills
    p, t = m.example_positions(fid), m.neutral_table(fid)
    r = allocate_fund(m, fid, 10_000_000, p, t, routes=m.raw["routes"], buffer_bps=50, excluded={"MER-EM-MF"})
    o = {x["instrument"]: x for x in r["orders"]}
    assert "MER-EM-MF" not in o and "MER-LISC-MF" not in o
    assert all(x["side"] == "BUY" for x in r["orders"])
    assert o["MER-USLC-MF"]["route"] == "SS&C (formerly DST)" and o["VNQ"]["route"] == "Internal trading desk"
    assert o["TBILL-270211"]["route"] == "Internal trading desk"
    # pro rata: each security's share of the flow matches its share of the table (after the exclusion)
    denom = sum(v for k, v in t.items() if k != "MER-EM-MF")
    assert o["MER-USLC-MF"]["est_amount"] == pytest.approx(10e6 * t["MER-USLC-MF"] / denom, rel=1e-4)
    etf_target = 10e6 * t["VNQ"] / denom
    assert o["VNQ"]["est_amount"] <= etf_target * (1 - 0.005) + 1e-6 and r["buffer_held"] > 0
    assert float(o["VNQ"]["quantity"]).is_integer()                  # whole ETF shares
    assert r["cash_after"] >= r["cash_before"] and not r["errors"]
    cit = allocate_fund(m, "MTRT-2050", 5e6, m.example_positions("MTRT-2050"), m.neutral_table("MTRT-2050"),
                        routes=m.raw["routes"])
    assert {x["route"] for x in cit["orders"] if x["type"] == "cit"} == {"State Street"}


def test_excluded_share_can_stay_in_cash(m):
    fid = "MTRS-2050"
    p, t = m.example_positions(fid), m.neutral_table(fid)
    r = allocate_fund(m, fid, 10e6, p, t, routes=m.raw["routes"], excluded={"MER-INTL-MF"}, excluded_share="cash")
    assert r["cash_after"] - r["cash_before"] == pytest.approx(10e6 * t["MER-INTL-MF"], rel=1e-3)


def test_outflow_sells_pro_rata_and_never_more_than_held(m):
    fid = "MTRT-2065"
    p = m.example_positions(fid)
    t = m.previous_close_table(fid, p["values"])
    r = allocate_fund(m, fid, -50e6, p, t, routes=m.raw["routes"])
    assert r["orders"] and all(x["side"] == "SELL" for x in r["orders"])
    for x in r["orders"]:
        assert x["est_amount"] <= p["values"][x["instrument"]] + 1
    assert abs(sum(x["est_amount"] for x in r["orders"]) - 50e6) < 50e6 * 0.001


# ---------------------------------------------------------------------------------------------- API
@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_AUTH", "dev")
    monkeypatch.setenv("MERIDIAN_DB_URL", f"sqlite:///{tmp_path}/app.db")
    monkeypatch.setenv("INGEST_TOKEN", "test-token")
    import meridian.app.main as mm
    mm._store = None
    return TestClient(mm.app)


def login(c, name, *roles, email=""):
    c.cookies.clear()
    c.post("/dev-login", data={"name": name, "email": email, "roles": list(roles)}, follow_redirects=False)
    from meridian.app import auth
    return {"X-CSRF-Token": auth._serializer().loads(c.cookies.get(auth.SESSION_COOKIE))["csrf"]}


def test_end_to_end_cashflows_to_charles_river_file(client):
    h = login(client, "Priya Raman", "analyst", email="priya@example.com")
    # Excel upload from a transfer agent, plus a CIT cashflow by account code, plus an API connection
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["trade_date", "fund_id", "type", "amount", "source"])
    ws.append(["2026-11-10", "MTRS-2050", "subscription", 12_500_000, "SS&C (formerly DST)"])
    ws.append(["2026-11-10", "MTRS-2030", "redemption", 8_000_000, "SS&C (formerly DST)"])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post("/api/trading/cashflows/upload", headers=h,
                    files={"file": ("ta.xlsx", buf.getvalue(), "application/octet-stream")})
    assert r.status_code == 200 and r.json()["loaded"] == 2, r.text
    bad = client.post("/api/trading/cashflows/upload", headers=h,
                      files={"file": ("bad.csv", b"trade_date,fund_id,amount\n2026-11-10,NOPE,5\n", "text/csv")})
    assert bad.status_code == 400 and "unknown fund" in bad.json()["detail"]
    client.cookies.clear()
    api = client.post("/api/trading/cashflows", headers={"Authorization": "Bearer test-token"},
                      json=[{"trade_date": "2026-11-10", "fund_id": "CIT2050", "amount": 6_000_000, "source": "State Street"}])
    assert api.status_code == 200
    assert client.post("/api/trading/cashflows", headers={"Authorization": "Bearer wrong"}, json=[]).status_code == 401
    h = login(client, "Priya Raman", "analyst", email="priya@example.com")
    st = client.get("/api/trading/state").json()
    assert {c["fund_id"] for c in st["cashflows"]} == {"MTRS-2050", "MTRS-2030", "MTRT-2050"}

    # CIT-only trade list takes only the CIT cashflow
    tl = client.post("/api/trading/trade-lists", headers=h,
                     json={"trade_date": "2026-11-10", "strategy": "neutral", "vehicle": "cit"}).json()
    assert [f["fund_id"] for f in tl["funds"]] == ["MTRT-2050"]
    # analyst can't approve; PM can, with checkbox and reason
    assert client.post(f"/api/trading/trade-lists/{tl['id']}/approve", headers=h,
                       json={"checked": True, "reason": R}).status_code == 403
    assert client.get(f"/api/trading/trade-lists/{tl['id']}/crd.csv").status_code == 409   # not approved yet
    tl2 = client.post("/api/trading/trade-lists", headers=h,
                      json={"trade_date": "2026-11-10", "strategy": "previous_close", "vehicle": "all"}).json()
    assert sorted(f["fund_id"] for f in tl2["funds"]) == ["MTRS-2030", "MTRS-2050"]
    hp = login(client, "Maya Chen", "portfolio_manager", email="maya@example.com")
    assert client.post(f"/api/trading/trade-lists/{tl2['id']}/approve", headers=hp,
                       json={"checked": False, "reason": R}).status_code == 400
    ok = client.post(f"/api/trading/trade-lists/{tl2['id']}/approve", headers=hp, json={"checked": True, "reason": R})
    assert ok.status_code == 200 and ok.json()["self_approved"] is False
    f = client.get(f"/api/trading/trade-lists/{tl2['id']}/crd.csv")
    assert f.status_code == 200
    rows = list(csv.DictReader(io.StringIO(f.text)))
    assert rows and {r["Account"] for r in rows} == {"MF2030", "MF2050"}
    assert {r["Side"] for r in rows if r["Account"] == "MF2030"} == {"SELL"}
    assert {r["Destination"] for r in rows} <= {"SS&C (formerly DST)", "Internal trading desk"}
    assert client.get(f"/api/trading/trade-lists/{tl2['id']}").json()["status"] == "exported"

    # cancelling the CIT list releases its cashflow
    assert client.post(f"/api/trading/trade-lists/{tl2['id']}/cancel", headers=hp, json={"reason": R}).status_code == 409
    assert client.post(f"/api/trading/trade-lists/{tl['id']}/cancel", headers=hp, json={"reason": R}).status_code == 200
    cf = [c for c in client.get("/api/trading/state").json()["cashflows"] if c["fund_id"] == "MTRT-2050"][0]
    assert cf["status"] == "new"

    from meridian.app.main import _verify_records, store
    gov = [r for r in store().ledger("governance") if r["dr_type"] == "trading"]
    assert [r["step"] for r in gov] == ["cashflow.load", "cashflow.load", "trades.generate", "trades.generate",
                                        "trades.approve", "trades.export", "trades.cancel"]
    assert _verify_records(store().ledger("governance"))[0]


def test_settings_and_strategic_table_are_controlled_and_logged(client):
    h = login(client, "Priya Raman", "analyst")
    assert client.put("/api/trading/settings", headers=h, json={"buffer_bps": 25, "reason": R}).status_code == 403
    assert client.put("/api/trading/targets/MTRS-2050/strategic", headers=h,
                      json={"follows_glide_path": False, "reason": R}).status_code == 403
    hp = login(client, "Maya Chen", "portfolio_manager")
    assert client.put("/api/trading/settings", headers=hp, json={"buffer_bps": 25, "reason": "short"}).status_code == 400
    assert client.put("/api/trading/settings", headers=hp,
                      json={"routes": {"etf": "Somewhere else"}, "reason": R}).status_code == 400
    r = client.put("/api/trading/settings", headers=hp, json={
        "routes": {"etf": "State Street"}, "buffer_bps": 75,
        "excluded": [{"instrument": "VNQ", "fund": "*"}], "reason": R})
    assert r.status_code == 200 and set(r.json()["changed"]) == {"routes", "buffer_bps", "excluded"}
    st = client.get("/api/trading/state").json()["settings"]
    assert st["routes"]["etf"] == "State Street" and st["buffer_bps"] == 75 and st["excluded"][0]["reason"] == R
    # strategic table: custom weights must sum to 100% and only use the fund's securities
    d = client.get("/api/trading/funds/MTRS-2050").json()
    w = {x["instrument"]: x["t_neutral"] for x in d["rows"] if x["t_neutral"]}
    assert client.put("/api/trading/targets/MTRS-2050/strategic", headers=hp, json={
        "follows_glide_path": False, "weights": dict(w, **{"MER-USLC-MF": w["MER-USLC-MF"] + 0.01}),
        "reason": R}).status_code == 400
    assert client.put("/api/trading/targets/MTRS-2050/strategic", headers=hp, json={
        "follows_glide_path": False, "weights": {"MER-USLC-CIT": 1.0}, "reason": R}).status_code == 400
    tilt = dict(w)
    tilt["MER-USLC-MF"] += 0.01
    tilt["MER-CORE-MF"] -= 0.01
    ok = client.put("/api/trading/targets/MTRS-2050/strategic", headers=hp,
                    json={"follows_glide_path": False, "weights": tilt, "reason": R})
    assert ok.status_code == 200 and ok.json()["version"] == 1
    d2 = client.get("/api/trading/funds/MTRS-2050").json()
    row = {x["instrument"]: x for x in d2["rows"]}
    assert row["MER-USLC-MF"]["t_strategic"] == pytest.approx(row["MER-USLC-MF"]["t_neutral"] + 0.01)
    assert row["VNQ"]["excluded"] is True
    # a strategic trade list uses the custom table, excludes VNQ and routes ETFs per the new setting
    client.post("/api/trading/cashflows", headers=hp, json={"trade_date": "2026-11-10", "fund_id": "MTRS-2050",
                                                            "amount": 1e7, "type": "subscription"})
    hp = login(client, "Maya Chen", "portfolio_manager")
    tl = client.post("/api/trading/trade-lists", headers=hp, json={"trade_date": "2026-11-10", "strategy": "strategic"}).json()
    orders = {o["instrument"]: o for o in tl["funds"][0]["orders"]}
    assert "VNQ" not in orders and orders["PDBC"]["route"] == "State Street"
    steps = [r["step"] for r in client.get("/api/trading/state").json()["trading_records"]]
    assert steps[:2] == ["settings.change", "targets.strategic"]


def test_page_access(client):
    login(client, "Maya Chen", "portfolio_manager")
    assert "Meridian · Trading" in client.get("/trading").text
    login(client, "x", "manager_selection")
    assert client.get("/trading").status_code == 403
    login(client, "Grace Liu", "audit")
    assert client.get("/trading").status_code == 200
    assert client.post("/api/trading/trade-lists", json={}, headers={"X-CSRF-Token": "x"}).status_code == 403
