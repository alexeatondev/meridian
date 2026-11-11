"""Screenshots for the user guide (doc 06). Not part of the test suite.

Run:  MERIDIAN_OFFLINE=1 pytest tests/e2e/guide_screenshots.py -q
Writes PNGs to docs/img/guide/. Uses the same local app as the browser tests: development sign-in,
fictional people from the persona roster (doc 15), example data, nothing on AWS.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

OUT = Path(__file__).resolve().parents[2] / "docs" / "img" / "guide"
R = "Guide: example reason for the screenshot"
SHOTS: list[str] = []


@pytest.fixture(scope="module", autouse=True)
def _out():
    OUT.mkdir(parents=True, exist_ok=True)
    yield
    (OUT / "index.json").write_text(json.dumps(SHOTS, indent=1))


@pytest.fixture()
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1440, "height": 900}, "accept_downloads": True}


def shot(page, name: str, el: str | None = None, full: bool = False):
    page.wait_for_timeout(450)
    page.evaluate("document.querySelectorAll('#toast,.toast').forEach(t=>t.style.display='none')")
    path = OUT / f"{name}.png"
    if el:
        page.locator(el).first.screenshot(path=str(path))
    else:
        page.screenshot(path=str(path), full_page=full)
    SHOTS.append(name)


def go(page, app_url, name, *roles, email=""):
    page.context.clear_cookies()
    page.goto(app_url + "/login")
    page.fill("input[name=name]", name)
    if email:
        page.fill("input[name=email]", email)
    for r in roles:
        page.check(f"input[name=roles][value={r}]")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    return page


def tab(page, label):
    page.click(f"#nav button:text-is('{label}')")
    page.wait_for_selector(f"#nav button.active:text-is('{label}')")
    page.wait_for_timeout(300)


def api(page, method, url, body):
    return page.evaluate("""async ([m,u,b]) => { const r = await fetch(u, {method:m, headers:{'Content-Type':'application/json',
        'X-CSRF-Token': (typeof LIVE!=='undefined'&&LIVE ? LIVE.csrf : BOOT.csrf)}, body: JSON.stringify(b)}); return [r.status, await r.text()] }""",
                         [method, url, body])


def scroll_to(page, text):
    page.locator(f"text={text}").first.scroll_into_view_if_needed()
    page.wait_for_timeout(250)


def test_console_pm(page, app_url):
    p = go(page, app_url, "Maya Chen", "portfolio_manager")
    p.wait_for_selector("#nav button")
    shot(p, "pm-01-home")
    tab(p, "Portfolios & proposals")
    shot(p, "pm-02-proposal")
    p.locator(".why-btn").first.click()
    p.wait_for_selector(".modal .box, [role=dialog]")
    shot(p, "pm-03-why")
    p.keyboard.press("Escape")
    p.evaluate("document.querySelectorAll('.modal').forEach(m=>m.remove())")
    p.locator("#ack").scroll_into_view_if_needed()
    p.check("#ack")
    p.fill("#reason", R)
    shot(p, "pm-04-approve")
    tab(p, "Positioning")
    shot(p, "pm-05-positioning")
    tab(p, "Changes since last run")
    shot(p, "pm-06-changes")
    tab(p, "Risk budget")
    shot(p, "pm-07-risk-budget")


def test_console_risk_research_mgr(page, app_url):
    p = go(page, app_url, "Daniel Okafor", "risk")
    p.wait_for_selector("#nav button")
    tab(p, "Fund risk")
    shot(p, "risk-01-fund-risk")
    tab(p, "Factor risk")
    shot(p, "risk-02-factor")
    tab(p, "Stress tests")
    shot(p, "risk-03-stress")
    tab(p, "Look-through & search")
    p.fill("#ltq", "Treasury")
    p.keyboard.press("Enter")
    p.wait_for_timeout(800)
    shot(p, "risk-04-lookthrough")
    tab(p, "Risk history")
    shot(p, "risk-05-history")
    p = go(page, app_url, "Priya Raman", "analyst")
    p.wait_for_selector("#nav button")
    tab(p, "Capital market assumptions")
    shot(p, "res-01-cma")
    tab(p, "Agent votes")
    shot(p, "res-02-votes")
    p = go(page, app_url, "Marcus Webb", "manager_selection")
    p.wait_for_selector("#nav button")
    tab(p, "Underlying funds")
    shot(p, "mgr-01-funds")


def test_console_lead_comp_audit(page, app_url):
    p = go(page, app_url, "Elena Rossi", "leadership", "investment_committee")
    p.wait_for_selector("#nav button")
    shot(p, "lead-01-home")
    tab(p, "Board memo")
    shot(p, "lead-02-memo")
    p = go(page, app_url, "Nina Alvarez", "compliance")
    p.wait_for_selector("#nav button")
    tab(p, "Compliance")
    shot(p, "comp-01-compliance")
    st, _ = api(p, "POST", "/api/exceptions", {"title": "EM debt above sleeve guideline (example)", "severity": "warn",
                                               "vintage": 2050, "owner": "Maya Chen", "due": "2026-12-15",
                                               "details": "Example case for the user guide", "reason": R})
    assert st == 200
    p.reload()
    p.wait_for_selector("#nav button")
    tab(p, "Exceptions")
    shot(p, "comp-02-exceptions")
    p.locator("[data-exc], tr.click, .exc-row").first.click()
    p.wait_for_timeout(500)
    shot(p, "comp-03-exception-detail")
    tab(p, "Decision ledger")
    p.click("#lsBox summary")
    p.fill("#lsQ", "approve")
    p.keyboard.press("Enter")
    p.wait_for_timeout(800)
    shot(p, "comp-04-ledger-search")
    tab(p, "Compliance report")
    shot(p, "comp-05-report")
    p = go(page, app_url, "Grace Liu", "audit")
    p.wait_for_selector("#nav button")
    tab(p, "Decision ledger")
    shot(p, "aud-01-ledger")


def test_admin(page, app_url):
    from meridian.app.main import store
    from meridian.app.store import DevUser
    with store().Session.begin() as s:
        for e, n, r in (("sam.patel@example.com", "Sam Patel", ["admin"]),
                        ("maya.chen@example.com", "Maya Chen", ["portfolio_manager", "route_manager"]),
                        ("elena.rossi@example.com", "Elena Rossi", ["leadership", "investment_committee"]),
                        ("daniel.okafor@example.com", "Daniel Okafor", ["risk"])):
            if not s.get(DevUser, e):
                s.add(DevUser(email=e, name=n, roles=r))
    p = go(page, app_url, "Sam Patel", "admin", email="sam.patel@example.com")
    p.wait_for_selector("#users table")
    shot(p, "adm-01-users")
    p.click("#add")
    p.fill("#fEmail", "thomas.greene@example.com")
    p.fill("#fName", "Thomas Greene")
    p.check("#panel input[name=ws][value=leadership]")
    p.click("#panel label.opt:has(input[value=investment_committee]) .switch span")
    p.fill("#fReason", R)
    shot(p, "adm-02-add-user")
    p.click("#save")
    p.wait_for_timeout(800)
    p.click("text=Access review")
    shot(p, "adm-03-review")
    p.click("text=Access log")
    shot(p, "adm-04-log")


def test_trading(page, app_url):
    p = go(page, app_url, "Maya Chen", "portfolio_manager", "route_manager", email="maya.chen@example.com")
    p.goto(app_url + "/trading")
    p.wait_for_selector("[data-fund]")
    shot(p, "trd-01-funds")
    p.click("[data-fund='MTRS-2040']")
    p.wait_for_selector("#fundDetail h2")
    scroll_to(p, "MTRS-2040 · ")
    shot(p, "trd-02-fund-detail")
    p.locator("text=Trade individual securities").scroll_into_view_if_needed()
    shot(p, "trd-03-ticket")
    for body in ({"trade_date": "2026-11-10", "fund_id": "MTRS-2050", "amount": 12500000, "type": "subscription",
                  "source": "SS&C (formerly DST)", "reference": "TA batch 1"},
                 {"trade_date": "2026-11-10", "fund_id": "MTRS-2030", "amount": 8000000, "type": "redemption",
                  "source": "SS&C (formerly DST)", "reference": "TA batch 1"},
                 {"trade_date": "2026-11-10", "fund_id": "MTRT-2050", "amount": 6000000, "type": "subscription",
                  "source": "State Street", "reference": "Plan contribution"}):
        assert api(p, "POST", "/api/trading/cashflows", body)[0] == 200
    p.reload()
    p.click(".tabs button:text-is('Cashflows')")
    shot(p, "trd-04-cashflows")
    p.click(".tabs button:text-is('Trades')")
    p.select_option("#tgStrat", "previous_close")
    p.click("#tgGo")
    p.wait_for_selector("#tlDetail h2")
    p.wait_for_timeout(600)
    shot(p, "trd-05-trade-list")
    p.click("#tlv button:text-is('Current vs post-trade')")
    p.locator("#tlDetail details").first.scroll_into_view_if_needed()
    shot(p, "trd-06-preview")
    p.click("#tlv button:has-text('Tranches')")
    p.fill("[data-sp='0']", "40")
    p.fill("[data-sp='1']", "60")
    p.click("#trApply")
    p.click("#trSave")
    p.wait_for_timeout(900)
    p.locator("text=Bucket by date").first.evaluate("e => e.scrollIntoView({block:'start'})")
    shot(p, "trd-07-tranches")
    p.locator("#trSched").scroll_into_view_if_needed()
    shot(p, "trd-08-tranche-editor")
    p.click("#tlv button:text-is('Orders')")
    p.locator("#taChk").scroll_into_view_if_needed()
    p.check("#taChk")
    p.fill("#taReason", R)
    shot(p, "trd-09-approve")
    p.click("#taGo")
    p.wait_for_selector("#taCrd")
    p.locator("#taCrd").scroll_into_view_if_needed()
    shot(p, "trd-10-charles-river")
    p.click(".tabs button:text-is('Routing & settings')")
    p.wait_for_timeout(600)
    shot(p, "trd-11-settings")
    p.locator("#cardTilts").scroll_into_view_if_needed()
    shot(p, "trd-12-tilts-exits")


def test_regulations_and_new_trading(page, app_url):
    p = go(page, app_url, "Robert Hayes", "compliance", "chief_compliance_officer")
    p.goto(app_url + "/regulations")
    p.wait_for_selector("[data-sel]")
    for fid in ("MTRS-2040", "MTRS-2045", "MTRS-2050"):
        p.check(f"[data-sel='{fid}']")
    p.select_option("#rgReg", "ICA40")
    p.fill("#rgReason", R)
    shot(p, "reg-01-tag")
    p.click("#rgAdd")
    p.wait_for_timeout(900)
    p.check("[data-sel='MTRT-2050']")
    p.select_option("#rgReg", "ERISA")
    p.fill("#rgReason", R)
    p.click("#rgAdd")
    p.wait_for_timeout(900)
    p.check("[data-sel='MTRT-2060']")
    p.select_option("#rgReg", "UCITS")
    p.fill("#rgReason", R)
    p.click("#rgAdd")
    p.wait_for_timeout(900)
    p.locator("#funds .card").first.scroll_into_view_if_needed()
    p.evaluate("window.scrollTo(0,0)")
    shot(p, "reg-02-funds")
    p.click("[data-fund='MTRS-2050']")
    p.wait_for_selector("#fundDetail h2")
    p.locator("#fundDetail h2").evaluate("e => e.scrollIntoView({block:'start'})")
    shot(p, "reg-03-fund-detail")
    p.click(".tabs button:text-is('Obligations')")
    p.wait_for_timeout(500)
    shot(p, "reg-04-obligations")
    p.locator("#tasks [data-task]", has_text="Form N-CEN").first.click()
    p.wait_for_selector("#taskDetail h2")
    p.fill("#tkEvidence", "EDGAR accession 0001234567-27-000123")
    p.locator("#taskDetail h2").evaluate("e => e.scrollIntoView({block:'start'})")
    shot(p, "reg-05-task")
    p.click(".tabs button:text-is('Regulation library')")
    shot(p, "reg-06-library")

    p = go(page, app_url, "Maya Chen", "portfolio_manager", email="maya.chen@example.com")
    p.goto(app_url + "/trading")
    p.wait_for_selector("[data-fund]")
    p.locator("#posUpload").scroll_into_view_if_needed()
    shot(p, "trd-13-positions-upload")
    p.click(".tabs button:text-is('Trades')")
    p.select_option("#rbStrat", "neutral")
    p.select_option("#rbFunds", "MTRT-2060")
    p.fill("#rbReason", R)
    p.locator("#rbGo").scroll_into_view_if_needed()
    shot(p, "trd-14-rebalance")
    p.click("#rbGo")
    p.wait_for_selector("#tlDetail h2")
    p.locator("#tlDetail details").first.scroll_into_view_if_needed()
    shot(p, "trd-15-rebalance-blocked")
    p.select_option("#rbStrat", "neutral")
    p.select_option("#rbFunds", "MTRS-2055")
    p.fill("#rbReason", R)
    p.click("#rbGo")
    p.wait_for_selector("#taGo:not([disabled])")
    p.check("#taChk")
    p.fill("#taReason", R)
    p.click("#taGo")
    p.wait_for_selector("#taCrd")
    with p.expect_download():
        p.click("#taCrd")
    p.wait_for_selector("#flAll")
    p.click("#flAll")
    p.wait_for_timeout(1200)
    p.locator("text=Fills and booking").first.scroll_into_view_if_needed()
    shot(p, "trd-16-fills")
