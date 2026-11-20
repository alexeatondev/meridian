"""HP-1/HP-2: the PM home screen: positioning tables by management style (vs target, risk budget, vs market) and
cumulative returns from daily prices. ST-1: management style set per fund on Trading."""
from datetime import date, timedelta

import httpx
from playwright.sync_api import expect

from conftest import INGEST_TOKEN, trading_tab

SYMS = "AGG BIL BNDX EMB HYG IEFA PDBC VEA VGLT VNQ VOO VTIP VWO VXF".split()


def sample_prices(end: date | None = None, n: int = 400) -> dict:
    end = end or date.today()
    out = {}
    for j, t in enumerate(SYMS):
        px, s = 100.0, {}
        for k in range(n, -1, -1):
            d = end - timedelta(days=k)
            if d.weekday() < 5:
                s[d.isoformat()] = round(px, 4)
                px *= 1 + 0.0002 * (j - 6) + ((k * (j + 3)) % 7 - 3) * 0.0015
        out[t] = s
    return out


def post_prices(app_url):
    r = httpx.post(app_url + "/api/ingest/prices", json={"source": "UAT sample prices (synthetic)", "series": sample_prices()},
                   headers={"Authorization": f"Bearer {INGEST_TOKEN}"})
    assert r.status_code == 200, r.text


def test_st_01_management_style_and_home_tables(sign_in, app_url):
    post_prices(app_url)
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    expect(p.locator("h2:has-text('Positioning: passive and hybrid funds')")).to_be_visible()
    expect(p.locator("h2:has-text('Positioning: active funds')")).to_be_visible()
    expect(p.locator("#perfBody")).to_contain_text("Fund returns are hypothetical")
    expect(p.locator("#perfBody th:has-text('Year to date')").first).to_be_visible()
    expect(p.locator("#perfBody")).to_contain_text("proxy VOO")
    p.click("[data-hpshow='3']")
    expect(p.locator("td:has-text('Emerging markets')").first).to_be_visible()
    # set two funds' styles on Trading; they move to the active table
    p.goto(app_url + "/trading")
    trading_tab(p, "Funds & securities")
    p.select_option("[data-sty='MTRS-2040']", "active")
    p.select_option("[data-sty='MTRT-2040']", "hybrid")
    p.fill("#styReason", "UAT (run by Claude for Alex): 2040 sleeves managed actively")
    p.click("#stySave")
    expect(p.locator("#mtoasts")).to_contain_text("Management style saved for 2 funds")
    p.goto(app_url + "/")
    p.wait_for_selector("#nav button")
    act = p.locator(".card:has(h2:has-text('Positioning: active funds'))")
    expect(act).to_contain_text("MTRS-2040")
    expect(act).not_to_contain_text("MTRT-2040")
