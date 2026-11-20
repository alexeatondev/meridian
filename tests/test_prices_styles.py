"""Daily prices -> cumulative returns (home performance table), and management style per fund."""
import json
from datetime import date, timedelta

from test_trading import client, login  # noqa: F401  (fixtures)

from meridian import hierarchy, prices


def _series(start: str, days: int, daily: float) -> dict:
    d0, out, px = date.fromisoformat(start), {}, 100.0
    for k in range(days):
        d = d0 + timedelta(days=k)
        if d.weekday() < 5:
            out[d.isoformat()] = round(px, 6)
            px *= 1 + daily
    return out


def test_parse_daily_and_period_returns():
    raw = json.dumps({"chart": {"result": [{"timestamp": [1762981200, 1763067600],   # 2025-11-12/13 16:00 ET
                                            "indicators": {"adjclose": [{"adjclose": [10.0, 11.0]}]}}]}}).encode()
    assert prices.parse_daily(raw) == {"2025-11-12": 10.0, "2025-11-13": 11.0}
    s = {"2025-11-14": 100.0, "2025-12-31": 110.0, "2026-09-30": 120.0, "2026-10-31": 125.0, "2026-11-13": 126.0,
         "2026-11-20": 132.0}
    r = prices.returns(s, "2026-11-20")
    assert abs(r["1W"] - (132 / 126 - 1)) < 1e-12          # close on or before 2026-11-13
    assert abs(r["MTD"] - (132 / 125 - 1)) < 1e-12         # last close of October
    assert abs(r["QTD"] - (132 / 120 - 1)) < 1e-12         # last close of Q3
    assert abs(r["YTD"] - (132 / 110 - 1)) < 1e-12
    assert abs(r["1Y"] - (132 / 100 - 1)) < 1e-12
    assert prices.returns({"2026-11-01": 1.0, "2026-11-20": 2.0}, "2026-11-20")["1Y"] is None   # history too short


def test_proxy_tickers():
    assert prices.price_ticker({"id": "VNQ", "type": "etf", "asset_class": "global_reits"}) == ("VNQ", False)
    assert prices.price_ticker({"id": "MER-USLC-MF", "type": "mutual_fund", "asset_class": "us_large_cap"}) == ("VOO", True)
    assert prices.price_ticker({"id": "x", "type": "cash", "asset_class": "cash"}) == ("BIL", True)


def test_ingest_and_performance(client):  # noqa: F811
    h = login(client, "Maya Chen", "portfolio_manager")
    assert client.get("/api/performance", headers=h).json()["as_of"] is None
    syms = prices.tickers(json.loads(json.dumps(__import__("meridian.app.trading", fromlist=["model"]).model().raw["instruments"])))
    body = {"source": "test", "series": {t: _series("2025-10-01", 420, 0.0005) for t in syms}}
    assert client.post("/api/ingest/prices", json=body).status_code == 401
    r = client.post("/api/ingest/prices", json=body, headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200, r.text
    p = client.get("/api/performance", headers=h).json()
    assert p["as_of"] and p["periods"] == ["1W", "MTD", "QTD", "YTD", "1Y"]
    f = p["funds"][0]
    assert all(f["returns"][k] is not None and f["returns"][k] > 0 for k in p["periods"])
    assert any(s["proxy"] for s in p["securities"]) and any(not s["proxy"] for s in p["securities"])
    assert p["missing"] == []


def test_fund_styles(client):  # noqa: F811
    a = login(client, "Ana Lopez", "analyst")
    assert client.put("/api/trading/fund-styles", json={"funds": {"MTRS-2040": "active"}, "reason": "Set by analyst test"},
                      headers=a).status_code == 403
    h = login(client, "Maya Chen", "portfolio_manager")
    assert client.get("/api/trading/fund-styles", headers=h).json()["funds"]["MTRS-2040"] is None
    assert client.put("/api/trading/fund-styles", json={"funds": {"MTRS-2040": "bogus"}, "reason": "A valid reason here"},
                      headers=h).status_code == 400
    r = client.put("/api/trading/fund-styles", json={"funds": {"MTRS-2040": "active", "MTRT-2040": "hybrid"},
                                                     "reason": "Sleeves managed actively from Q1"}, headers=h)
    assert r.status_code == 200 and r.json()["changed"] == 2
    st = client.get("/api/trading/fund-styles", headers=h).json()["funds"]
    assert st["MTRS-2040"]["style"] == "active" and st["MTRT-2040"]["style"] == "hybrid"
    assert client.put("/api/trading/fund-styles", json={"funds": {"MTRS-2040": "active"}, "reason": "Same again, no change"},
                      headers=h).status_code == 400
    fs = {f["id"]: f for f in client.get("/api/trading/state", headers=h).json()["funds"]}
    assert fs["MTRS-2040"]["style"] == "active" and fs["MTRS-2050"]["style"] is None


def test_market_mix_sums_to_one_per_parent():
    mk = hierarchy.market()["nodes"]
    for a, b in (("equity_us", "equity_intl"), ("intl_developed_eq", "emerging_eq"), ("us_large_cap", "us_small_mid_cap")):
        assert abs(mk[a]["share"] + mk[b]["share"] - 1) < 1e-9
    ids = set()
    def walk(ns):
        for n in ns:
            ids.add(n.get("id") or n.get("asset")); walk(n.get("children") or [])
    walk(hierarchy.load()["tree"])
    assert set(mk) <= ids
