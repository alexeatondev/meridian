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
    page.evaluate("document.querySelectorAll('#toast,.toast,#mtoasts').forEach(t=>t.style.display='none')")
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


def top(page, sel):
    page.locator(sel).first.evaluate("e => e.scrollIntoView({block:'start'})")
    page.wait_for_timeout(250)


def ttab(page, label):
    page.click(f".tabs button:text-is('{label}')")
    page.wait_for_selector(f".tabs button.active:text-is('{label}')")
    page.wait_for_timeout(300)


def strat(page, key):
    page.click(f"label.tile:has(input[name=ntStrat][value='{key}'])")


def scroll_to(page, text):
    page.locator(f"text={text}").first.scroll_into_view_if_needed()
    page.wait_for_timeout(250)


def test_console_pm(page, app_url):
    p = go(page, app_url, "Maya Chen", "portfolio_manager")
    p.wait_for_selector("#nav button")
    shot(p, "pm-01-home")
    tab(p, "Funds & vintages")
    shot(p, "pm-08-products")
    p.click("[data-pf='MTRT-2050']")
    p.wait_for_timeout(400)
    shot(p, "pm-09-product-detail")
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
    p.click("[data-posv='2050']")
    p.wait_for_timeout(400)
    shot(p, "pm-10-positioning-vintage")
    tab(p, "Changes since last run")
    shot(p, "pm-06-changes")
    tab(p, "Risk budget")
    shot(p, "pm-07-risk-budget")
    p.select_option("#rbV", "2050")
    p.fill("#rbTe", "0.30")
    p.dispatch_event("#rbTe", "input")
    top(p, "#rbPrev")
    shot(p, "pm-11-risk-budget-preview")
    tab(p, "Approvals")
    shot(p, "pm-12-approvals")
    tab(p, "Glide path")
    shot(p, "pm-13-glide-path")
    p.select_option("#gpScope", "vehicle:cit")
    p.select_option("[data-gpi='0'][data-gpk='asset_class']", "us_core_bond")
    p.select_option("[data-gpi='0'][data-gpk='from']", "us_large_cap")
    p.fill("[data-gpi='0'][data-gpk='pp']", "0.5")
    p.dispatch_event("[data-gpi='0'][data-gpk='pp']", "change")
    p.click("#gpPrev")
    p.wait_for_selector("#gpSubmit")
    p.fill("#gpReason", R)
    top(p, "#gpOut")
    shot(p, "pm-14-glide-request")
    p.click("#gpSubmit")
    p.wait_for_timeout(1200)


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
    if p.locator("#ltq").count():
        p.fill("#ltq", "Treasury")
        p.wait_for_timeout(500)
        shot(p, "risk-04-lookthrough")
        if p.locator("#ltSug [data-i]").count():
            p.keyboard.press("ArrowDown")
            p.keyboard.press("Enter")
            p.wait_for_timeout(600)
            shot(p, "risk-06-lookthrough-selected")
    tab(p, "Risk history")
    shot(p, "risk-05-history")
    p = go(page, app_url, "Priya Raman", "analyst")
    p.wait_for_selector("#nav button")
    tab(p, "Capital market assumptions")
    shot(p, "res-01-cma")
    tab(p, "Agent votes")
    shot(p, "res-02-votes")
    p.click("[data-agsel='max_sharpe_tilt']")
    p.wait_for_timeout(400)
    shot(p, "res-03-agent-detail")
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
    tab(p, "Glide path")
    if p.locator("[data-gpdec='approve']").count():
        top(p, "[data-gpdec='approve']")
        shot(p, "lead-03-glide-decide")
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
    p.wait_for_selector("[data-task]")
    shot(p, "trd-21-new-trade")
    ttab(p, "Funds & securities")
    p.wait_for_selector("[data-fund]")
    shot(p, "trd-01-funds")
    p.click("[data-fund='MTRS-2040']")
    p.wait_for_selector("#fundDetail h2")
    scroll_to(p, "MTRS-2040 · ")
    shot(p, "trd-02-fund-detail")
    p.locator("#fdTrade").scroll_into_view_if_needed()
    shot(p, "trd-03-fund-trade-buttons")
    for body in ({"trade_date": "2026-11-10", "fund_id": "MTRS-2050", "amount": 12500000, "type": "subscription",
                  "source": "SS&C (formerly DST)", "reference": "TA batch 1"},
                 {"trade_date": "2026-11-10", "fund_id": "MTRS-2030", "amount": 8000000, "type": "redemption",
                  "source": "SS&C (formerly DST)", "reference": "TA batch 1"},
                 {"trade_date": "2026-11-10", "fund_id": "MTRT-2050", "amount": 6000000, "type": "subscription",
                  "source": "State Street", "reference": "Plan contribution"}):
        assert api(p, "POST", "/api/trading/cashflows", body)[0] == 200
    p.reload()
    ttab(p, "Cashflows")
    shot(p, "trd-04-cashflows")
    # 1 invest cashflows at previous close
    ttab(p, "New trade")
    p.click("[data-task='invest']")
    strat(p, "previous_close")
    p.wait_for_timeout(300)
    top(p, "#trade .card:nth-of-type(2)")
    shot(p, "trd-22-invest-setup")
    p.click("#ntPrev")
    p.wait_for_selector("#ntCreate")
    top(p, "#trade .card:nth-of-type(3)")
    shot(p, "trd-23-impact")
    top(p, "#trade .mixrow")
    p.evaluate("window.scrollBy(0,-90)")
    shot(p, "trd-24-impact-fund")
    p.fill("#ntReason", R)
    top(p, "#trade .card:nth-of-type(4)")
    shot(p, "trd-25-create-draft")
    p.click("#ntCreate")
    p.wait_for_selector(".tabs button.active:text-is('Trade lists')")
    p.wait_for_selector("#tlDetail h2")
    p.evaluate("window.scrollTo(0,0)")
    p.wait_for_timeout(600)
    shot(p, "trd-05-trade-list")
    p.click("#tlv button:text-is('Orders')")
    top(p, "#tlDetail details, #tlDetail table")
    shot(p, "trd-06-orders")
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
    p.click("#tlv button:text-is('Impact: now vs after')")
    p.locator("#taChk").scroll_into_view_if_needed()
    p.check("#taChk")
    p.fill("#taReason", R)
    shot(p, "trd-09-approve")
    p.click("#taGo")
    p.wait_for_selector("#taCrd")
    p.locator("#taCrd").scroll_into_view_if_needed()
    shot(p, "trd-10-charles-river")
    # 2 trade a security to a weight (from the fund page)
    ttab(p, "Funds & securities")
    p.click("[data-fund='MTRS-2040']")
    p.wait_for_selector("#fdTrade")
    p.click("#fdTrade")
    p.wait_for_selector("#ntQ")
    p.fill("#ntQ", "Treasury")
    p.wait_for_timeout(300)
    top(p, "#ntQ")
    p.evaluate("window.scrollBy(0,-60)")
    shot(p, "trd-26-security-search")
    held = p.evaluate("S.nt.fd.rows.filter(r=>r.value>0 && r.type!=='cash' && !r.excluded).sort((a,b)=>b.value-a.value)")
    big, small = held[0], held[1]
    p.fill("#ntQ", big["instrument"])
    p.click(f"[data-add='{big['instrument']}']")
    p.select_option("[data-oact='0']", "weight")
    p.fill("[data-oval='0']", str(round(big["weight"] * 100 - 1.0, 2)))
    p.dispatch_event("[data-oval='0']", "change")
    p.fill("#ntQ", small["instrument"])
    p.click(f"[data-add='{small['instrument']}']")
    p.fill("[data-oval='1']", "20000000")
    p.dispatch_event("[data-oval='1']", "change")
    top(p, "text=Orders in this ticket")
    p.evaluate("window.scrollBy(0,-40)")
    shot(p, "trd-27-security-ticket")
    p.click("#ntPrev")
    p.wait_for_selector("#ntCreate")
    top(p, "#trade .card:nth-of-type(3)")
    shot(p, "trd-28-security-impact")
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
    ttab(p, "Funds & securities")
    p.wait_for_selector("[data-fund]")
    p.locator("#posUpload").scroll_into_view_if_needed()
    shot(p, "trd-13-positions-upload")
    ttab(p, "New trade")
    p.click("[data-task='rebalance']")
    strat(p, "neutral")
    p.select_option("#ntFunds", "MTRT-2060")
    top(p, "#trade .card:nth-of-type(2)")
    shot(p, "trd-14-rebalance")
    p.click("#ntPrev")
    p.wait_for_selector("#ntCreate")
    top(p, "#trade .card:nth-of-type(3)")
    shot(p, "trd-15-rebalance-blocked")
    p.click("[data-task='rebalance']")
    p.select_option("#ntFunds", "MTRS-2055")
    p.click("#ntPrev")
    p.wait_for_selector("#ntCreate")
    p.fill("#ntReason", R)
    p.click("#ntCreate")
    p.wait_for_selector(".tabs button.active:text-is('Trade lists')")
    p.wait_for_selector("#taGo:not([disabled])")
    p.locator("#taChk").scroll_into_view_if_needed()
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


def test_bulk_changes(page, app_url):
    p = go(page, app_url, "Maya Chen", "portfolio_manager", email="maya.chen@example.com")
    p.goto(app_url + "/trading")
    p.click(".tabs button:text-is('Glide path & bulk changes')")
    p.select_option("#bkScope", "vehicle:cit")
    p.select_option("#bkTo", "2045")
    p.fill("#bkReason", R)
    p.select_option("[data-sha='0']", "us_large_cap")
    p.select_option("[data-shf='0']", "us_core_bond")
    p.fill("[data-shp='0']", "1.5")
    p.click("#gpPrev")
    p.wait_for_selector("#gpPreview table")
    shot(p, "trd-17-glide-path")
    p.locator("#gpPreview").scroll_into_view_if_needed()
    shot(p, "trd-18-glide-preview")
    p.click("#gpReq")
    p.wait_for_timeout(900)
    p = go(page, app_url, "Elena Rossi", "leadership", "investment_committee", email="elena.rossi@example.com")
    p.goto(app_url + "/trading")
    p.click(".tabs button:text-is('Glide path & bulk changes')")
    p.fill("#bkReason", R)
    p.locator("text=Waiting for the Investment Committee").scroll_into_view_if_needed()
    shot(p, "trd-19-glide-approve")
    p = go(page, app_url, "Maya Chen", "portfolio_manager", email="maya.chen@example.com")
    p.goto(app_url + "/trading")
    p.click(".tabs button:text-is('Glide path & bulk changes')")
    p.locator("#bkTiGo").scroll_into_view_if_needed()
    shot(p, "trd-20-bulk-tilts")


def test_navigation_and_feedback(page, app_url):
    """App bar, My work, Help, in-page dialogs and messages (UX update 2026-11-11)."""
    go(page, app_url, "Maya Chen", "portfolio_manager", "route_manager")
    page.goto(app_url + "/trading")
    page.wait_for_selector(".mbar")
    st, _ = api(page, "POST", "/api/trading/rebalance", {"strategy": "neutral", "trade_date": "2026-11-13", "fund_ids": ["MTRS-2045"], "reason": R})
    assert st == 200
    page.reload()
    page.wait_for_selector(".mbar")
    page.wait_for_function("document.getElementById('mworkN').textContent !== '·'")
    page.click("#mwork")
    page.wait_for_selector("#mworkPop")
    shot(page, "nav-01-my-work")
    page.locator("#mworkPop a.mi", has_text="Approve").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)
    shot(page, "nav-02-from-my-work")
    if page.locator("#taCancel").count():
        page.click("#taCancel")
        page.wait_for_selector("dialog.mdlg[open]")
        page.fill("dialog.mdlg textarea", "Duplicate of an earlier list")
        shot(page, "nav-03-dialog")
        page.keyboard.press("Escape")
    # an error message stays until dismissed; a success message clears itself
    page.evaluate("document.getElementById('mtoasts').style.display='';MUI.toast('Reason must be at least 10 characters','error'); MUI.toast('Saved and recorded in the ledger')")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "nav-04-messages.png"), clip={"x": 900, "y": 700, "width": 540, "height": 200})
    SHOTS.append("nav-04-messages")
    page.goto(app_url + "/help#10-trading-doc-17")
    page.wait_for_timeout(600)
    page.fill("#hq", "fills")
    shot(page, "nav-05-help")
