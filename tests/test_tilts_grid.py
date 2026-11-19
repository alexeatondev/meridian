"""Tilts table: security tilts per fund in % of the fund, previewed and saved together (doc 17 item 5)."""
import pytest
from fastapi.testclient import TestClient

R = "UAT: reason long enough"


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


def _two_held(g, fid):
    held = [i for i, c in g["cells"][fid].items() if c["target"] > 0.02]
    return held[0], held[1]


def test_tilts_table_preview_save_and_clear(client):
    hp = login(client, "Maya Chen", "portfolio_manager")
    g = client.get("/api/trading/tilts-grid").json()
    assert g["can_edit"] and len(g["funds"]) == 18 and g["rows"]
    a, b = _two_held(g, "MTRS-2040")
    c, _ = _two_held(g, "MTRT-2050")
    cells = [{"fund_id": "MTRS-2040", "instrument": a, "pct": 0.5}, {"fund_id": "MTRS-2040", "instrument": b, "pct": -0.25},
             {"fund_id": "MTRT-2050", "instrument": c, "pct": 0.3}]
    pv = client.post("/api/trading/tilts-grid/preview", headers=hp, json={"cells": cells}).json()["funds"]
    f40 = next(f for f in pv if f["fund_id"] == "MTRS-2040")
    assert f40["after"][a] - f40["before"][a] > 0.004 and f40["after"][b] < f40["before"][b]
    assert sum(f40["after"].values()) == pytest.approx(1.0)
    assert client.get("/api/trading/tilts-grid").json()["cells"]["MTRS-2040"][a]["own_bps"] is None   # preview saves nothing
    r = client.put("/api/trading/tilts-grid", headers=hp, json={"cells": cells, "reason": R})
    assert r.status_code == 200 and r.json() == {"ok": True, "dr_id": r.json()["dr_id"], "set": 3, "cleared": 0, "funds": 2}
    g = client.get("/api/trading/tilts-grid").json()
    assert g["cells"]["MTRS-2040"][a]["own_bps"] == 50 and g["cells"]["MTRS-2040"][b]["bps"] == -25
    assert g["cells"]["MTRT-2050"][c]["own_bps"] == 30
    # the fund page and every allocation table see the tilt
    det = client.get("/api/trading/funds/MTRS-2040").json()
    assert next(x for x in det["rows"] if x["instrument"] == a)["tilt_bps"] == 50
    # clearing a cell removes only that fund's own tilt; re-saving the same values changes nothing
    r = client.put("/api/trading/tilts-grid", headers=hp, json={"cells": [{"fund_id": "MTRS-2040", "instrument": a, "pct": None}], "reason": R})
    assert r.json()["cleared"] == 1
    g = client.get("/api/trading/tilts-grid").json()
    assert g["cells"]["MTRS-2040"][a]["own_bps"] is None and g["cells"]["MTRS-2040"][b]["own_bps"] == -25
    assert client.put("/api/trading/tilts-grid", headers=hp, json={"cells": cells[1:2], "reason": R}).status_code == 400


def test_tilts_table_rules(client):
    hp = login(client, "Maya Chen", "portfolio_manager")
    g = client.get("/api/trading/tilts-grid").json()
    a, _ = _two_held(g, "MTRS-2040")
    bad = client.post("/api/trading/tilts-grid/preview", headers=hp, json={"cells": [{"fund_id": "MTRS-2040", "instrument": a, "pct": 6}]})
    assert bad.status_code == 400 and "-5%" in bad.json()["detail"]
    mf_only = next(i for i in g["cells"]["MTRS-2040"] if i not in g["cells"]["MTRT-2040"])
    bad = client.post("/api/trading/tilts-grid/preview", headers=hp, json={"cells": [{"fund_id": "MTRT-2040", "instrument": mf_only, "pct": 0.1}]})
    assert bad.status_code == 400 and "universe" in bad.json()["detail"]
    # a wider-scope tilt shows as the tilt in force; the table's own value overrides it for that fund only
    client.put("/api/trading/settings", headers=hp, json={"tilts": [{"fund": "*", "instrument": a, "bps": 20}], "reason": R})
    g = client.get("/api/trading/tilts-grid").json()
    assert g["cells"]["MTRS-2040"][a]["own_bps"] is None and g["cells"]["MTRS-2040"][a]["bps"] == 20
    client.put("/api/trading/tilts-grid", headers=hp, json={"cells": [{"fund_id": "MTRS-2040", "instrument": a, "pct": -0.1}], "reason": R})
    g = client.get("/api/trading/tilts-grid").json()
    assert g["cells"]["MTRS-2040"][a]["bps"] == -10 and g["cells"]["MTRS-2045"][a]["bps"] == 20
    ha = login(client, "Priya Raman", "analyst")
    assert client.get("/api/trading/tilts-grid").json()["can_edit"] is False
    assert client.put("/api/trading/tilts-grid", headers=ha, json={"cells": [{"fund_id": "MTRS-2040", "instrument": a, "pct": 0.1}], "reason": R}).status_code == 403
