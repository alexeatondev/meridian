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
    hp = login(client, "Maya Chen", "portfolio_manager", "approver", email="maya@example.com")
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
    hp = login(client, "Maya Chen", "portfolio_manager", "approver")
    assert client.put("/api/trading/settings", headers=hp, json={"buffer_bps": 25, "reason": "short"}).status_code == 400
    assert client.put("/api/trading/settings", headers=hp,
                      json={"routes": {"etf": "Somewhere else"}, "reason": R}).status_code == 400
    # routes need the route permission, even for a PM; the permission alone covers routes only
    assert client.put("/api/trading/settings", headers=hp,
                      json={"routes": {"etf": "State Street"}, "reason": R}).status_code == 403
    hr = login(client, "Daniel Okafor", "risk", "route_manager", "approver")
    assert client.put("/api/trading/settings", headers=hr, json={"buffer_bps": 10, "reason": R}).status_code == 403
    only = client.put("/api/trading/settings", headers=hr, json={"routes": {"bond": "State Street"}, "reason": R})
    assert only.status_code == 200 and only.json()["changed"] == ["routes"]
    hp = login(client, "Maya Chen", "portfolio_manager", "route_manager", "approver")
    r = client.put("/api/trading/settings", headers=hp, json={
        "routes": {"etf": "State Street", "bond": "Internal trading desk"}, "buffer_bps": 75,
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
    hp = login(client, "Maya Chen", "portfolio_manager", "approver")
    tl = client.post("/api/trading/trade-lists", headers=hp, json={"trade_date": "2026-11-10", "strategy": "strategic"}).json()
    orders = {o["instrument"]: o for o in tl["funds"][0]["orders"]}
    assert "VNQ" not in orders and orders["PDBC"]["route"] == "State Street"
    steps = [r["step"] for r in client.get("/api/trading/state").json()["trading_records"]]
    assert steps[:3] == ["routes.change", "settings.change", "targets.strategic"]


def test_page_access(client):
    login(client, "Maya Chen", "portfolio_manager", "approver")
    assert "Meridian · Trading" in client.get("/trading").text
    login(client, "x", "manager_selection")
    assert client.get("/trading").status_code == 403
    login(client, "Grace Liu", "audit")
    assert client.get("/trading").status_code == 200
    assert client.post("/api/trading/trade-lists", json={}, headers={"X-CSRF-Token": "x"}).status_code == 403


def test_tilts_fund_pro_rata_and_total_100(m):
    from meridian.trading.allocate import apply_tilts
    t = m.neutral_table("MTRS-2050")
    out, notes = apply_tilts(t, {"MER-EM-MF": 100, "MER-HY-MF": -50, "NOPE": 10})
    assert abs(sum(out.values()) - 1) < 1e-9
    assert out["MER-EM-MF"] == pytest.approx(t["MER-EM-MF"] + 0.01) and out["MER-HY-MF"] == pytest.approx(t["MER-HY-MF"] - 0.005)
    rest = [k for k in t if k not in ("MER-EM-MF", "MER-HY-MF")]
    ratios = {round(out[k] / t[k], 9) for k in rest}
    assert len(ratios) == 1                                          # everything else scaled by one factor
    assert any("NOPE" in n for n in notes)
    away, _ = apply_tilts(t, {"MER-EMD-MF": -500})                   # can't go below zero
    assert "MER-EMD-MF" not in away and abs(sum(away.values()) - 1) < 1e-9


def test_tranche_checks_and_split(m):
    from meridian.trading.allocate import split_order, validate_schedule
    ok = [{"date": "2026-11-10", "pct": 50}, {"date": "2026-11-12", "pct": 30}, {"date": "2026-11-13", "pct": 20}]
    assert validate_schedule(ok, "2026-11-10") == []
    assert "not 100%" in validate_schedule(ok[:2], "2026-11-10")[0]
    assert any("weekend" in e for e in validate_schedule([{"date": "2026-11-14", "pct": 100}], "2026-11-10"))
    assert any("before" in e for e in validate_schedule([{"date": "2026-11-09", "pct": 100}], "2026-11-10"))
    assert any("order" in e for e in validate_schedule(list(reversed(ok)), "2026-11-10"))
    o = {"instrument": "VNQ", "quantity": 1001.0, "quantity_type": "SHARES", "price": 92.15}
    parts, errs = split_order(o, ok)
    assert not errs and [p["quantity"] for p in parts] == [500, 300, 201] and sum(p["quantity"] for p in parts) == 1001
    tiny, errs = split_order(dict(o, quantity=1.0), ok)
    assert errs                                                      # too small to split


def test_tickets_exits_tilts_and_tranches_api(client):
    hp = login(client, "Maya Chen", "portfolio_manager", "approver", email="maya@example.com")
    ha = login(client, "Priya Raman", "analyst", email="priya@example.com")
    # analysts can't set tilts or exits
    assert client.put("/api/trading/settings", headers=ha, json={
        "tilts": [{"instrument": "MER-EM-MF", "fund": "MTRS-2050", "bps": 100}], "reason": R}).status_code == 403
    hp = login(client, "Maya Chen", "portfolio_manager", "approver", email="maya@example.com")
    assert client.put("/api/trading/settings", headers=hp, json={
        "tilts": [{"instrument": "MER-EM-MF", "fund": "MTRS-2050", "bps": 900}], "reason": R}).status_code == 400
    r = client.put("/api/trading/settings", headers=hp, json={
        "tilts": [{"instrument": "MER-EM-MF", "fund": "MTRS-2050", "bps": 100}],
        "exits": [{"instrument": "MER-LISC-MF", "fund": "*"}, {"instrument": "MER-HY-MF", "fund": "MTRS-2050"}],
        "reason": R})
    assert r.status_code == 200 and set(r.json()["changed"]) == {"tilts", "exits"}
    row = {x["instrument"]: x for x in client.get("/api/trading/funds/MTRS-2050").json()["rows"]}
    assert row["MER-EM-MF"]["tilt_bps"] == 100 and row["MER-HY-MF"]["exiting"] and row["MER-LISC-MF"]["exiting"]

    # cashflow trades: tilt applied, exiting security not traded
    client.post("/api/trading/cashflows", headers=hp, json=[
        {"trade_date": "2026-11-10", "fund_id": "MTRS-2050", "amount": 2e7, "type": "subscription"},
        {"trade_date": "2026-11-10", "fund_id": "MTRS-2040", "amount": 1e7, "type": "subscription"}])
    hp = login(client, "Maya Chen", "portfolio_manager", "approver", email="maya@example.com")
    tl = client.post("/api/trading/trade-lists", headers=hp, json={"trade_date": "2026-11-10", "strategy": "neutral"}).json()
    f50 = next(f for f in tl["funds"] if f["fund_id"] == "MTRS-2050")
    o = {x["instrument"]: x for x in f50["orders"]}
    assert "MER-HY-MF" not in o and any("Tilt +100 bp on MER-EM-MF" in n for n in f50["notes"])
    prev = {x["instrument"]: x for x in f50["preview"]}
    assert o["MER-EM-MF"]["est_amount"] == pytest.approx(2e7 * prev["MER-EM-MF"]["target_w"], rel=1e-4)

    # tranches: list-level equal split, a fund-level unequal series, one security series, one order excluded
    days = [{"date": "2026-11-10", "pct": 50}, {"date": "2026-11-11", "pct": 50}]
    bad = client.put(f"/api/trading/trade-lists/{tl['id']}/tranches", headers=hp,
                     json={"default": [{"date": "2026-11-10", "pct": 60}, {"date": "2026-11-11", "pct": 50}]})
    assert bad.status_code == 400 and "110.00%" in bad.json()["detail"]
    t = client.put(f"/api/trading/trade-lists/{tl['id']}/tranches", headers=hp, json={
        "default": days,
        "funds": {"MTRS-2040": [{"date": "2026-11-10", "pct": 20}, {"date": "2026-11-12", "pct": 30}, {"date": "2026-11-13", "pct": 50}]},
        "securities": {"MTRS-2050|VNQ": [{"date": "2026-11-12", "pct": 25}, {"date": "2026-11-13", "pct": 75}]},
        "excluded": ["MTRS-2050|MER-USLC-MF"], "note": "UAT tranche plan"})
    assert t.status_code == 200, t.text
    b = t.json()
    f50 = next(f for f in b["funds"] if f["fund_id"] == "MTRS-2050")
    f40 = next(f for f in b["funds"] if f["fund_id"] == "MTRS-2040")
    o = {x["instrument"]: x for x in f50["orders"]}
    assert "tranches" not in o["MER-USLC-MF"] and o["VNQ"]["tranche_level"] == "security" and len(o["VNQ"]["tranches"]) == 2
    assert o["MER-EM-MF"]["tranche_level"] == "list" and len(o["MER-EM-MF"]["tranches"]) == 2
    assert all(len(x["tranches"]) == 3 and x["tranche_level"] == "fund" for x in f40["orders"])
    for f in b["funds"]:
        for x in f["orders"]:
            if "tranches" in x:
                assert sum(p["quantity"] for p in x["tranches"]) == pytest.approx(x["quantity"], abs=1e-6)
    assert b["tranche_summary"]["orders_whole"] == 1
    assert [d["date"] for d in b["tranche_summary"]["by_date"]] == ["2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"]
    client.post(f"/api/trading/trade-lists/{tl['id']}/approve", headers=hp, json={"checked": True, "reason": R})
    assert client.put(f"/api/trading/trade-lists/{tl['id']}/tranches", headers=hp, json={"default": days}).status_code == 409
    rows = list(csv.DictReader(io.StringIO(client.get(f"/api/trading/trade-lists/{tl['id']}/crd.csv").text)))
    vnq = [r for r in rows if r["Security ID"] == "VNQ" and r["Account"] == "MF2050"]
    assert [r["Trade Date"] for r in vnq] == ["2026-11-12", "2026-11-13"] and vnq[0]["Tranche"] == "1 of 2"
    assert vnq[0]["Parent Order ID"] and vnq[0]["External Order ID"].endswith("-T1")
    whole = [r for r in rows if r["Security ID"] == "MER-USLC-MF" and r["Account"] == "MF2050"]
    assert len(whole) == 1 and whole[0]["Tranche"] == ""

    # manual ticket: buy a candidate ETF from cash; too big a buy and a buy of an exiting security are refused
    ha = login(client, "Priya Raman", "analyst", email="priya@example.com")
    tk = client.post("/api/trading/tickets", headers=ha, json={"fund_id": "MTRS-2050", "trade_date": "2026-11-10",
                     "orders": [{"instrument": "IEFA", "side": "BUY", "amount": 5e6}], "reason": R})
    assert tk.status_code == 200 and tk.json()["id"].startswith("TK-") and tk.json()["kind"] == "ticket"
    f = tk.json()["funds"][0]
    assert f["orders"][0]["route"] == "Internal trading desk" and f["cash_after"] == pytest.approx(f["cash_before"] - f["orders"][0]["est_amount"])
    for orders, msg in (([{"instrument": "IEFA", "side": "BUY", "amount": 5e9}], "Cash would go negative"),
                        ([{"instrument": "MER-HY-MF", "side": "BUY", "amount": 1e5}], "being exited"),
                        ([{"instrument": "MER-USLC-CIT", "side": "BUY", "amount": 1e5}], "not available"),
                        ([{"instrument": "VNQ", "side": "SELL", "amount": 9e9}], "only")):
        bad = client.post("/api/trading/tickets", headers=ha, json={"fund_id": "MTRS-2050", "trade_date": "2026-11-10",
                                                                    "orders": orders, "reason": R})
        assert bad.status_code == 400 and msg in bad.json()["detail"], bad.text
    # full exit: sells the whole flagged position; only flagged securities qualify
    assert client.post("/api/trading/tickets", headers=ha, json={"fund_id": "MTRS-2050", "trade_date": "2026-11-10", "kind": "exit",
                       "orders": [{"instrument": "VNQ"}], "reason": R}).status_code == 400
    ex = client.post("/api/trading/tickets", headers=ha, json={"fund_id": "MTRS-2050", "trade_date": "2026-11-10", "kind": "exit",
                     "orders": [{"instrument": "MER-HY-MF"}, {"instrument": "MER-LISC-MF"}], "reason": R}).json()
    assert ex["id"].startswith("EX-")
    post = {x["instrument"]: x for x in ex["funds"][0]["preview"]}
    assert abs(post["MER-HY-MF"]["post"]) < 0.02 and abs(post["MER-LISC-MF"]["post"]) < 0.02
    assert all(x["side"] == "SELL" for x in ex["funds"][0]["orders"])


def test_route_managers_list(client):
    login(client, "Maya Chen", "portfolio_manager", "approver")
    j = client.get("/api/trading/route-managers").json()
    assert j["permission"] == "route_manager" and isinstance(j["holders"], list)


def test_bulk_scopes_glide_path_and_strategic(client):
    hp = login(client, "Maya Chen", "portfolio_manager", "approver", email="maya@example.com")
    # asset-class tilt on all CITs, 2050+ only; exclusion for all mutual funds; roll-down for all CITs
    r = client.put("/api/trading/settings", headers=hp, json={
        "tilts": [{"asset_class": "emerging_eq", "fund": "vehicle:cit", "vintage_from": 2050, "bps": 50}],
        "excluded": [{"instrument": "PDBC", "fund": "vehicle:mutual_fund"}],
        "roll_down": {"MTRT-2030": "annual", "MTRT-2035": "annual"}, "reason": R})
    assert r.status_code == 200, r.text
    assert client.put("/api/trading/settings", headers=hp, json={
        "tilts": [{"asset_class": "nope", "fund": "*", "bps": 10}], "reason": R}).status_code == 400
    assert client.put("/api/trading/settings", headers=hp, json={
        "tilts": [{"asset_class": "emerging_eq", "fund": "vehicle:cit", "vintage_from": 2060, "vintage_to": 2040, "bps": 10}],
        "reason": R}).status_code == 400
    row = lambda fid, k: {x["instrument"]: x for x in client.get(f"/api/trading/funds/{fid}").json()["rows"]}[k]
    assert row("MTRT-2050", "MER-EM-CIT")["tilt_bps"] == pytest.approx(50)
    assert row("MTRT-2040", "MER-EM-CIT")["tilt_bps"] == 0 and row("MTRS-2050", "MER-EM-MF")["tilt_bps"] == 0
    assert row("MTRS-2050", "PDBC")["excluded"] and not row("MTRT-2050", "PDBC")["excluded"]
    st = client.get("/api/trading/state").json()
    rd = {f["id"]: f["roll_down"] for f in st["funds"]}
    assert rd["MTRT-2030"] == "annual" and rd["MTRT-2040"] == "semiannual"

    # glide path: preview, refusal outside the IPS band, request, segregation of duties, IC approval
    shifts = [{"asset_class": "us_large_cap", "from": "us_core_bond", "pp": 1.5}]
    pv = client.post("/api/trading/glide-path/preview", headers=hp, json={"scope": "vehicle:cit", "shifts": shifts}).json()
    assert len(pv["funds"]) == 9 and pv["ok"]
    wide = client.post("/api/trading/glide-path/requests", headers=hp, json={
        "scope": "*", "shifts": [{"asset_class": "us_large_cap", "from": "us_core_bond", "pp": 4}], "reason": R})
    assert wide.status_code == 400 and "IPS amendment" in wide.json()["detail"]
    req = client.post("/api/trading/glide-path/requests", headers=hp, json={"scope": "vehicle:cit", "vintage_to": 2045,
                                                                            "shifts": shifts, "reason": R}).json()
    assert req["funds"] == 4
    before = row("MTRT-2040", "MER-USLC-CIT")["t_neutral"]
    assert client.post(f"/api/trading/glide-path/requests/{req['id']}/decide", headers=hp,
                       json={"decision": "approve", "reason": R}).status_code == 403          # no IC permission
    hm = login(client, "Maya Chen", "portfolio_manager", "investment_committee", "approver", email="maya@example.com")
    assert client.post(f"/api/trading/glide-path/requests/{req['id']}/decide", headers=hm,
                       json={"decision": "approve", "reason": R}).status_code == 403          # own request
    he = login(client, "Elena Rossi", "leadership", "investment_committee", email="elena@example.com")
    ok = client.post(f"/api/trading/glide-path/requests/{req['id']}/decide", headers=he, json={"decision": "approve", "reason": R})
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    hp = login(client, "Maya Chen", "portfolio_manager", "approver", email="maya@example.com")
    after = row("MTRT-2040", "MER-USLC-CIT")["t_neutral"]
    assert after == pytest.approx(before + 0.015, abs=1e-6)
    st = client.get("/api/trading/state").json()
    adj = {f["id"]: f["glide_adjusted"] for f in st["funds"]}
    assert adj["MTRT-2040"] and not adj["MTRT-2050"] and not adj["MTRS-2040"]

    # strategic table in bulk: all mutual funds = glide path plus a shift
    sb = client.put("/api/trading/targets/strategic-bulk", headers=hp, json={
        "scope": "vehicle:mutual_fund", "follows_glide_path": False,
        "shifts": [{"asset_class": "emerging_eq", "from": "intl_developed_eq", "pp": 1}], "reason": R})
    assert sb.status_code == 200 and sb.json()["funds"] == 9
    r50 = row("MTRS-2050", "MER-EM-MF")
    assert r50["t_strategic"] == pytest.approx(r50["t_neutral"] + 0.01, abs=1e-6)
    from meridian.app.main import store
    steps = [x["step"] for x in store().ledger("governance") if x["dr_type"] == "trading"]
    assert {"glidepath.request", "glidepath.approve", "targets.strategic-bulk", "settings.change"} <= set(steps)


def test_dry_run_previews_impact_without_saving(client):
    """New trade 'See the impact': dry_run returns the impact for every kind of list and saves nothing."""
    hp = login(client, "Maya Chen", "portfolio_manager", "approver", email="maya@example.com")
    client.post("/api/trading/cashflows", headers=hp, json=[
        {"trade_date": "2026-11-10", "fund_id": "MTRS-2050", "amount": 2e7, "type": "subscription"}])
    hp = login(client, "Maya Chen", "portfolio_manager", "approver", email="maya@example.com")
    before = len(client.get("/api/trading/state").json()["trade_lists"])
    ledger_before = len(client.get("/api/trading/state").json()["trading_records"])
    fd = client.get("/api/trading/funds/MTRS-2040").json()
    big = max((r for r in fd["rows"] if r["value"] > 0 and r["type"] != "cash"), key=lambda r: r["value"])
    previews = {
        "cashflow": client.post("/api/trading/trade-lists", headers=hp,
                                json={"trade_date": "2026-11-10", "strategy": "previous_close", "dry_run": True}),
        "rebalance": client.post("/api/trading/rebalance", headers=hp,
                                 json={"strategy": "neutral", "trade_date": "2026-11-13", "fund_ids": ["MTRS-2070"], "dry_run": True}),
        "ticket": client.post("/api/trading/tickets", headers=hp,
                              json={"fund_id": "MTRS-2040", "trade_date": "2026-11-13", "dry_run": True,
                                    "orders": [{"instrument": big["instrument"], "side": "SELL", "amount": 1e7}]}),
    }
    for kind, r in previews.items():
        assert r.status_code == 200, (kind, r.text)
        b = r.json()
        assert b["id"] == "PREVIEW" and b["status"] == "preview", kind
        f = b["funds"][0]
        imp = f["impact"]
        assert set(imp) >= {"asset_classes", "gap_to_target_before", "gap_to_target_after"}, kind
        ac = imp["asset_classes"]
        assert abs(sum(v["current"] for v in ac.values()) - 1) < 1e-4 and abs(sum(v["post"] for v in ac.values()) - 1) < 1e-4
    reb = previews["rebalance"].json()["funds"][0]["impact"]
    assert reb["gap_to_target_after"] <= reb["gap_to_target_before"] + 1e-9           # rebalance closes gaps
    st = client.get("/api/trading/state").json()
    assert len(st["trade_lists"]) == before                                            # nothing saved
    assert len(st["trading_records"]) == ledger_before                                     # nothing recorded
    assert all(c["status"] == "new" for c in st["cashflows"])                          # cashflows not consumed
    # without dry_run the reason is still required for tickets and rebalances
    assert client.post("/api/trading/rebalance", headers=hp, json={
        "strategy": "neutral", "trade_date": "2026-11-13", "fund_ids": ["MTRS-2070"]}).status_code == 400


def test_trade_list_approval_needs_the_approver_permission(client):
    hp = login(client, "Maya Chen", "portfolio_manager", "approver", email="maya@example.com")
    t = client.post("/api/trading/rebalance", headers=hp, json={"strategy": "neutral", "trade_date": "2026-11-13",
                    "fund_ids": ["MTRS-2070"], "reason": "UAT: rebalance for the approver check"}).json()
    h = login(client, "Jordan Ellis", "portfolio_manager", email="jordan@example.com")
    assert client.get("/trading").text.count('"can_approve_lists": false') == 1
    r = client.post(f"/api/trading/trade-lists/{t['id']}/approve", headers=h,
                    json={"checked": True, "reason": "UAT: approve without the permission"})
    assert r.status_code == 403 and "Approver permission" in r.text
    assert not any(i["title"] == f"Approve {t['id']}" for i in client.get("/api/my-work").json()["items"])
    h = login(client, "Jordan Ellis", "portfolio_manager", "approver", email="jordan@example.com")
    assert any(i["title"] == f"Approve {t['id']}" for i in client.get("/api/my-work").json()["items"])
    assert client.post(f"/api/trading/trade-lists/{t['id']}/approve", headers=h,
                       json={"checked": True, "reason": "UAT: approve with the permission"}).status_code == 200


def test_glide_path_scope_by_picked_vintages(client):
    """The vintage picker sends a list: only those vintages are in scope, the label names them, and they're kept on
    the request and the adjustment."""
    hp = login(client, "Maya Chen", "portfolio_manager", "approver", email="maya@example.com")
    shifts = [{"asset_class": "us_large_cap", "from": "us_core_bond", "pp": 0.5}]
    pv = client.post("/api/trading/glide-path/preview", headers=hp,
                     json={"scope": "vehicle:mutual_fund", "vintages": [2030, 2050, 2070], "shifts": shifts}).json()
    assert sorted(f["fund_id"] for f in pv["funds"]) == ["MTRS-2030", "MTRS-2050", "MTRS-2070"]
    assert client.post("/api/trading/glide-path/preview", headers=hp,
                       json={"scope": "*", "vintages": [2031], "shifts": shifts}).status_code == 400   # unknown vintage
    req = client.post("/api/trading/glide-path/requests", headers=hp, json={
        "scope": "*", "vintages": [2035, 2040], "shifts": shifts, "reason": "UAT: picked vintages only"}).json()
    assert req["funds"] == 4
    g = client.get("/api/trading/state").json()["glide"]
    r = next(x for x in g["requests"] if x["id"] == req["id"])
    assert r["vintages"] == [2035, 2040] and r["scope_label"] == "All funds, vintages 2035, 2040"
    he = login(client, "Elena Rossi", "leadership", "investment_committee", email="elena@example.com")
    assert client.post(f"/api/trading/glide-path/requests/{req['id']}/decide", headers=he,
                       json={"decision": "approve", "reason": "UAT: approve picked vintages"}).status_code == 200
    funds = {f["id"]: f for f in client.get("/api/trading/state").json()["funds"]}
    adjusted = sorted(k for k, f in funds.items() if f.get("glide_adjusted"))
    assert adjusted == ["MTRS-2035", "MTRS-2040", "MTRT-2035", "MTRT-2040"]
    # tilts and other bulk settings accept the same list
    hp = login(client, "Maya Chen", "portfolio_manager", "approver", email="maya@example.com")
    r = client.put("/api/trading/settings", headers=hp, json={"reason": "UAT: EM tilt on two CIT vintages",
                   "tilts": [{"asset_class": "emerging_eq", "fund": "vehicle:cit", "vintages": [2055, 2065], "bps": 25}]})
    assert r.status_code == 200
    t = client.get("/api/trading/state").json()["settings"]["tilts"][0]
    assert t["vintages"] == [2055, 2065] and "vintage_from" not in t
