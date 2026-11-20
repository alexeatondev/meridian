"""Security line-up (level 5): add a security to funds across vintages, take one out, exclude / include,
and add a new security to the security master."""
from test_trading import client, login  # noqa: F401  (fixtures)


def _ac_rows(c, h, fid, ac):
    return {r["instrument"]: r["t_neutral"] for r in c.get(f"/api/trading/funds/{fid}", headers=h).json()["rows"]
            if r["asset_class"] == ac}


def test_add_security_to_funds_and_vintages(client):  # noqa: F811
    h = login(client, "Maya Chen", "portfolio_manager")
    before = _ac_rows(client, h, "MTRS-2040", "intl_developed_eq")
    body = {"instrument": "IEFA", "action": "share", "share_pct": 25, "fund": "vehicle:mutual_fund", "vintages": [2040, 2045]}
    p = client.post("/api/trading/lineup/preview", json=body, headers=h).json()
    assert [f["fund_id"] for f in p["funds"]] == ["MTRS-2040", "MTRS-2045"]
    r = {x["instrument"]: x for x in p["funds"][0]["rows"]}
    assert r["IEFA"]["before"] == 0 and abs(r["IEFA"]["after"] - 0.25) < 1e-9 and abs(r["MER-INTL-MF"]["after"] - 0.75) < 1e-9
    assert client.put("/api/trading/lineup", json={**body, "reason": "short"}, headers=h).status_code == 400
    a = login(client, "Ana Lopez", "analyst")
    assert client.put("/api/trading/lineup", json={**body, "reason": "Analyst can't change it"}, headers=a).status_code == 403
    h = login(client, "Maya Chen", "portfolio_manager")
    assert client.put("/api/trading/lineup", json={**body, "reason": "IEFA as a liquidity sleeve"}, headers=h).status_code == 200
    after = _ac_rows(client, h, "MTRS-2040", "intl_developed_eq")
    tot = sum(before.values())
    assert abs(after["IEFA"] - tot * 0.25) < 1e-6 and abs(after["MER-INTL-MF"] - tot * 0.75) < 1e-6
    assert _ac_rows(client, h, "MTRS-2050", "intl_developed_eq").get("IEFA", 0) == 0     # vintage not chosen
    assert _ac_rows(client, h, "MTRT-2040", "intl_developed_eq").get("IEFA", 0) == 0     # CIT not in scope
    # a more specific entry wins for one fund
    assert client.put("/api/trading/lineup", json={"instrument": "IEFA", "action": "share", "share_pct": 50, "fund": "MTRS-2045",
                                                   "reason": "Bigger sleeve in 2045"}, headers=h).status_code == 200
    assert abs(_ac_rows(client, h, "MTRS-2045", "intl_developed_eq")["IEFA"] / sum(_ac_rows(client, h, "MTRS-2045", "intl_developed_eq").values()) - 0.5) < 1e-6
    g = client.get("/api/trading/lineup", headers=h).json()
    assert g["cells"]["MTRS-2040"]["IEFA"]["entry"]["fund"] == "vehicle:mutual_fund"


def test_take_out_exclude_include_and_new_security(client):  # noqa: F811
    h = login(client, "Maya Chen", "portfolio_manager")
    # the only security for an asset class can't be taken out
    r = client.post("/api/trading/lineup/preview", json={"instrument": "MER-USLC-MF", "action": "remove", "fund": "MTRS-2040"}, headers=h)
    assert r.status_code == 400 and "only security" in r.json()["detail"]
    # a new security, added to one CIT, then taken out (target 0 + exit), then included again
    sec = {"id": "vxus", "name": "Vanguard Total International Stock ETF", "type": "etf", "asset_class": "intl_developed_eq",
           "price": 72.5, "reason": "Candidate for the CIT line"}
    assert client.post("/api/trading/securities", json=sec, headers=h).json()["security"]["id"] == "VXUS"
    assert client.post("/api/trading/securities", json=sec, headers=h).status_code == 409
    assert client.put("/api/trading/lineup", json={"instrument": "VXUS", "action": "share", "share_pct": 10, "fund": "MTRT-2050",
                                                   "reason": "Pilot VXUS in one CIT"}, headers=h).status_code == 200
    assert _ac_rows(client, h, "MTRT-2050", "intl_developed_eq")["VXUS"] > 0
    assert client.put("/api/trading/lineup", json={"instrument": "VXUS", "action": "remove", "fund": "MTRT-2050",
                                                   "reason": "Pilot ended, sell it"}, headers=h).status_code == 200
    c = client.get("/api/trading/lineup", headers=h).json()["cells"]["MTRT-2050"]["VXUS"]
    assert c["share"] == 0 and c["exiting"]
    assert client.put("/api/trading/lineup", json={"instrument": "VXUS", "action": "include", "fund": "MTRT-2050",
                                                   "reason": "Back in the line-up"}, headers=h).status_code == 200
    c = client.get("/api/trading/lineup", headers=h).json()["cells"]["MTRT-2050"]["VXUS"]
    assert c["share"] > 0 and not c["exiting"]
    # exclude across all funds, then include again
    assert client.put("/api/trading/lineup", json={"instrument": "VNQ", "action": "exclude", "fund": "*",
                                                   "reason": "Hold VNQ pending review"}, headers=h).status_code == 200
    g = client.get("/api/trading/lineup", headers=h).json()["cells"]
    assert all(g[f]["VNQ"]["excluded"] for f in g if "VNQ" in g[f])
    assert client.put("/api/trading/lineup", json={"instrument": "VNQ", "action": "include", "fund": "*",
                                                   "reason": "Review finished, trade again"}, headers=h).status_code == 200
    assert client.put("/api/trading/lineup", json={"instrument": "VNQ", "action": "include", "fund": "*",
                                                   "reason": "Same again, no change"}, headers=h).status_code == 400
