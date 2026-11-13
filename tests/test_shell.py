"""Shared UI shell (2026-11-11): app bar on every page, role-filtered navigation, My work inbox, in-app Help."""
import re

import pytest
from fastapi.testclient import TestClient

from meridian.app.shell import HELP_SECTION, help_anchor, nav_for

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


def test_nav_is_filtered_by_role():
    pm = [l["key"] for l in nav_for({"roles": ["portfolio_manager"]}, "trading")["links"]]
    assert pm == ["console", "trading", "regulations"]
    adm = nav_for({"roles": ["admin"]}, "admin")
    assert [l["key"] for l in adm["links"]] == ["console", "trading", "regulations", "admin"]
    lead = nav_for({"roles": ["leadership", "investment_committee"]}, "console")
    assert lead["user"]["roles"] == ["leadership"] and lead["user"]["permissions"] == ["Investment Committee"]


def test_every_page_carries_the_shell_without_duplicate_links(client):
    login(client, "Maya Chen", "portfolio_manager", "admin", "compliance", "approver")
    for path in ("/trading", "/regulations", "/admin"):
        html = client.get(path).text
        assert "window.MERIDIAN_NAV=" in html and 'id="mshell-css"' in html, path
        assert "Back to console" not in html and "=prompt(" not in html, path


def test_help_anchors_exist(client):
    login(client, "Maya Chen", "portfolio_manager", "approver")
    html = client.get("/help").text
    assert "<h2" in html and 'src="/help/img/' in html and "Image: `" not in html
    for page, num in HELP_SECTION.items():
        assert help_anchor(page).startswith(num + "-") and f'id="{help_anchor(page)}"' in html, page
    img = re.search(r'src="/help/img/([a-z0-9-]+\.png)"', html).group(1)
    assert client.get(f"/help/img/{img}").headers["content-type"] == "image/png"
    assert client.get("/help/img/..%2Fsecret.png").status_code == 404
    client.cookies.clear()
    assert client.get("/help", follow_redirects=False).status_code in (302, 307)


def test_my_work_lists_drafts_committee_requests_and_obligations(client):
    h = login(client, "Maya Chen", "portfolio_manager", "approver")
    assert client.get("/api/my-work").json()["count"] == 0
    client.post("/api/trading/cashflows", headers=h, json={"trade_date": "2026-11-10", "fund_id": "MTRS-2050",
                                                           "amount": 1e6, "type": "subscription"})
    tl = client.post("/api/trading/trade-lists", headers=h, json={"trade_date": "2026-11-10", "strategy": "neutral"}).json()["id"]
    work = client.get("/api/my-work").json()["items"]
    assert any(i["kind"] == "Trade list" and tl in i["title"] and i["go"]["tr_tl"] == tl for i in work)
    # a compliance user sees obligations due within two weeks for funds tagged with a regulation
    hc = login(client, "Nina Alvarez", "compliance")
    client.post("/api/regulations/tags", headers=hc, json={"reg_id": "ICA40", "fund_ids": ["MTRS-2050"], "reason": R})
    items = client.get("/api/my-work").json()["items"]
    assert all(i["kind"] in ("Obligation", "Exception") for i in items)
    assert all(i["go"].get("rg_tab") == "tasks" for i in items if i["kind"] == "Obligation")
    # analysts do not get approval items
    login(client, "Priya Raman", "analyst")
    assert not any(i["title"].startswith("Approve") for i in client.get("/api/my-work").json()["items"])
