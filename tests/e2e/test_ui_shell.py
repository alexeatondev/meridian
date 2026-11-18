"""UAT-UX: shared app bar, My work, Help, in-page confirmations, messages, keyboard and session expiry (2026-11-11)."""
from playwright.sync_api import expect

from conftest import trade_create, trade_preview, trade_setup


def test_ux_01_app_bar_on_every_screen_filtered_by_role(sign_in, app_url):
    """UX-1: the same app bar on every screen; links follow the person's access; the current screen is marked."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    bar = page.locator(".mbar")
    expect(bar.locator("nav")).to_have_text("ConsoleTradingPolicyRegulations")
    expect(bar.locator("nav a[aria-current=page]")).to_have_text("Console")
    for path, label in (("/trading", "Trading"), ("/policy", "Policy"), ("/regulations", "Regulations")):
        page.goto(app_url + path)
        expect(page.locator(".mbar nav a[aria-current=page]")).to_have_text(label)
        assert page.locator("text=Back to console").count() == 0
    page.context.clear_cookies()
    page.goto(app_url + "/login")
    page.fill("input[name=name]", "Sam Patel")
    page.check("input[name=roles][value=admin]")
    page.click("button[type=submit]")
    page.wait_for_url("**/admin")
    expect(page.locator(".mbar nav a[aria-current=page]")).to_have_text("User access")
    page = sign_in("Grace Liu", "audit")
    page.goto(app_url + "/trading")
    expect(page.locator("#who")).to_contain_text("Read-only")


def test_ux_02_my_work_opens_the_item(sign_in, app_url):
    """UX-2: My work lists a draft trade list for a PM and opens it on Trading → Trades."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Cashflows')")
    page.select_option("#cfFund", "MTRS-2060")
    page.fill("#cfAmt", "1000000")
    page.click("#cfAdd")
    expect(page.locator("#mtoasts")).to_contain_text("Cashflow added")
    trade_setup(page, "invest", strat="neutral")
    trade_preview(page)
    trade_create(page, "UAT: draft for the My work check")
    expect(page.locator("#mtoasts")).to_contain_text("draft created")
    tl = page.evaluate("S.tl")
    page.goto(app_url + "/runs/latest")
    page.wait_for_function("document.getElementById('mworkN').textContent !== '·'")
    page.click("#mwork")
    item = page.locator("#mworkPop a.mi", has_text=f"Approve {tl}")
    expect(item).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#mworkPop")).to_have_count(0)
    page.click("#mwork")
    item.click()
    page.wait_for_url("**/trading")
    expect(page.locator(".tabs button.active")).to_have_text("Trade lists")
    expect(page.locator("#tlDetail")).to_contain_text(tl)
    # tidy up: cancel through the in-page confirmation (Go back first leaves it unchanged)
    page.click("#taCancel")
    dlg = page.locator("dialog.mdlg[open]")
    expect(dlg).to_contain_text(f"Cancel trade list {tl}?")
    ok = dlg.locator("button[value=ok]")
    expect(ok).to_be_disabled()
    dlg.locator("textarea").fill("short")
    expect(ok).to_be_disabled()
    dlg.locator("button[value=cancel]").click()
    expect(page.locator("dialog.mdlg")).to_have_count(0)
    page.click("#taCancel")
    page.locator("dialog.mdlg textarea").fill("UAT: cancelled after the My work check")
    page.locator("dialog.mdlg button[value=ok]").click()
    expect(page.locator("#mtoasts")).to_contain_text("Trade list cancelled")


def test_ux_03_messages_reason_counter_and_keyboard(sign_in, app_url):
    """UX-3: errors stay until dismissed; reason fields count characters; tabs work with the arrow keys; skip link."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    trade_setup(page, "rebalance", strat="neutral")
    trade_preview(page)
    page.fill("#ntReason", "abc")
    expect(page.locator("#ntReason + .mcount")).to_have_text("3/10 characters minimum")
    page.fill("#ntReason", "")
    page.click("#ntCreate")
    err = page.locator("#mtoasts .mtoast.error")
    expect(err).to_have_count(1)
    page.wait_for_timeout(5000)
    expect(err).to_have_count(1)                       # still there after info messages would have cleared
    err.locator(".mx").click()
    expect(err).to_have_count(0)
    tabs = page.locator(".tabs[role=tablist] button[role=tab]")
    expect(tabs.first).to_have_attribute("aria-selected", "true")
    page.focus(".tabs button.active")
    page.keyboard.press("ArrowRight")
    expect(page.locator(".tabs button.active")).to_have_text("Trade lists")
    page.keyboard.press("End")
    expect(page.locator(".tabs button.active")).to_have_text("Routing & settings")
    page.keyboard.press("Home")
    expect(page.locator(".tabs button.active")).to_have_text("New trade")
    page.goto(app_url + "/trading")
    page.keyboard.press("Tab")
    expect(page.locator(".mskip")).to_be_focused()


def test_ux_04_help_and_session_expiry(sign_in, app_url):
    """UX-4: Help opens the guide at the screen's section; an expired session offers Sign in instead of failing silently."""
    page = sign_in("Nina Alvarez", "compliance")
    page.goto(app_url + "/regulations")
    page.click(".mbar a:has-text('Help')")
    page.wait_for_url("**/help#12-*")
    expect(page.locator(f'h2[id="{page.url.split("#")[1]}"]')).to_be_visible()
    page.fill("#hq", "obligation")
    assert page.locator("#hlinks a:visible").count() >= 1
    page.go_back()
    page.wait_for_url("**/regulations")
    page.context.clear_cookies()
    page.click(".tabs button:text-is('Obligations')")
    page.evaluate("fetch('/api/regulations/state')")
    dlg = page.locator("dialog.mdlg[open]")
    expect(dlg).to_contain_text("Your session has expired")
    dlg.locator("button[value=ok]").click()
    page.wait_for_url("**/login")
