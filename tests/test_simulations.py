"""Simulations: a cashflow typed in (no real cashflow), spread across funds, with tilts and exits applied;
and exiting a position across many funds in one trade list."""
from test_trading import client, login  # noqa: F401  (fixtures)


def _held(c, h, fid, inst):
    return next((r["value"] for r in c.get(f"/api/trading/funds/{fid}", headers=h).json()["rows"] if r["instrument"] == inst), 0)


def test_simulate_by_assets_per_vintage_and_per_fund(client):  # noqa: F811
    h = login(client, "Ana Lopez", "analyst")
    n_tl = len(client.get("/api/trading/state", headers=h).json()["trade_lists"])
    r = client.post("/api/simulate/cashflows", json={"amount": 100e6, "split": "nav", "strategy": "neutral"}, headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "preview" and abs(d["net_flow"] - 100e6) < 1 and len(d["funds"]) == len(d["flows"]) > 10
    st = client.get("/api/trading/state", headers=h).json()
    nav = {f["id"]: f["cash"] + f["invested"] for f in st["funds"]}
    tot = sum(nav.values())
    for f, v in d["flows"].items():
        assert abs(v - 100e6 * nav[f] / tot) < 1
    assert all(o["side"] == "BUY" for f in d["funds"] for o in f["orders"])
    assert len(st["trade_lists"]) == n_tl                                   # nothing saved
    # one vintage only: split between its MF and CIT by assets
    d = client.post("/api/simulate/cashflows", json={"split": "vintage", "by_vintage": {"2030": 100e6}}, headers=h).json()
    assert sorted(d["flows"]) == ["MTRS-2030", "MTRT-2030"] and abs(d["net_flow"] - 100e6) < 1
    # per fund, a redemption
    d = client.post("/api/simulate/cashflows", json={"split": "fund", "by_fund": {"MTRS-2040": -5e6}}, headers=h).json()
    assert list(d["flows"]) == ["MTRS-2040"] and all(o["side"] == "SELL" for o in d["funds"][0]["orders"])
    # scope + vintages
    d = client.post("/api/simulate/cashflows", json={"amount": 10e6, "split": "equal", "fund": "vehicle:cit", "vintages": [2050, 2055]}, headers=h).json()
    assert sorted(d["flows"]) == ["MTRT-2050", "MTRT-2055"] and abs(d["flows"]["MTRT-2050"] - 5e6) < 1
    assert client.post("/api/simulate/cashflows", json={"amount": 0}, headers=h).status_code == 400
    assert client.post("/api/simulate/cashflows", json={"split": "fund", "by_fund": {"MTRS-2040": -1e12}}, headers=h).status_code == 400


def test_simulation_applies_exits_and_exclusions(client):  # noqa: F811
    h = login(client, "Maya Chen", "portfolio_manager")
    body = {"split": "fund", "by_fund": {"MTRS-2040": 50e6}, "strategy": "neutral"}
    before = client.post("/api/simulate/cashflows", json=body, headers=h).json()
    bought = {o["instrument"] for o in before["funds"][0]["orders"]}
    inst = sorted(bought - {"CASH"})[0]
    assert client.put("/api/trading/lineup", json={"instrument": inst, "action": "exclude", "fund": "MTRS-2040",
                                                   "reason": "Test exclusion for simulation"}, headers=h).status_code == 200
    after = client.post("/api/simulate/cashflows", json=body, headers=h).json()
    assert inst not in {o["instrument"] for o in after["funds"][0]["orders"]}


def test_exit_across_funds(client):  # noqa: F811
    h = login(client, "Maya Chen", "portfolio_manager")
    st = client.get("/api/trading/state", headers=h).json()
    holders = [f["id"] for f in st["funds"] if f["held"].get("MER-USLC-MF", 0) > 0 and f["vehicle"] == "mutual_fund"]
    assert len(holders) > 3
    body = {"fund": "vehicle:mutual_fund", "instruments": ["MER-USLC-MF"], "trade_date": "2026-11-23"}
    p = client.post("/api/trading/exits", json={**body, "dry_run": True}, headers=h).json()
    assert sorted(f["fund_id"] for f in p["funds"]) == sorted(holders)
    assert all(len(f["orders"]) == 1 and f["orders"][0]["side"] == "SELL" for f in p["funds"])
    assert len(p["flagged"]) == len(holders)
    # an analyst can't exit something not flagged
    a = login(client, "Ana Lopez", "analyst")
    r = client.post("/api/trading/exits", json={**body, "dry_run": True}, headers=a)
    assert r.status_code == 400
    h = login(client, "Maya Chen", "portfolio_manager")
    b = client.post("/api/trading/exits", json={**body, "reason": "Replacing the US large-cap fund everywhere"}, headers=h).json()
    assert b["id"].startswith("EX-") and len(b["funds"]) == len(holders) and b["order_count"] == len(holders)
    rows = client.get(f"/api/trading/funds/{holders[0]}", headers=h).json()["rows"]
    assert next(r for r in rows if r["instrument"] == "MER-USLC-MF")["exiting"]
    # now flagged: the analyst can prepare the exit, for chosen vintages only
    a = login(client, "Ana Lopez", "analyst")
    p = client.post("/api/trading/exits", json={**body, "vintages": [2040], "dry_run": True}, headers=a).json()
    assert [f["fund_id"] for f in p["funds"]] == ["MTRS-2040"] and not p["skipped"]
