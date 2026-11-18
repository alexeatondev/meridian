"""UAT-TRD-25/26 (calculation templates) and REG-7 (fiscal year ends), 2026-11-18."""
from playwright.sync_api import expect

from conftest import trade_create, trade_preview, trade_setup, trading_tab

R = "UAT: browser test reason"


def _toast(page, text):
    expect(page.locator("#mtoasts")).to_contain_text(text, timeout=8000)


def test_trd_25_calculation_tranches_a_trade_list(sign_in, app_url):
    """TRD-25: run the seeded 'Sell 20% a day' template over a draft list with sells: preview, apply, recorded."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    trading_tab(page, "Cashflows")
    page.select_option("#cfFund", "MTRS-2060")
    page.select_option("#cfType", "redemption")
    page.fill("#cfAmt", "25000000")
    page.click("#cfAdd")
    _toast(page, "Cashflow added")
    page.click("#veh button:text-is('Mutual funds')")
    trade_setup(page, "invest", strat="neutral")
    trade_preview(page)
    trade_create(page, R)
    page.click("#tlv button:has-text('Tranches')")
    expect(page.locator("#clTpl")).to_be_visible()
    page.select_option("#clTpl", label="Sell 20% a day (v1)")
    page.select_option("#clScope", "fund:MTRS-2060")
    page.click("#clPrev")
    out = page.locator("#clOut")
    expect(out).to_contain_text("Nothing is saved yet")
    expect(out.locator("td.n", has_text="5").first).to_be_visible()
    page.click("#clApply")
    _toast(page, "Sell 20% a day v1")
    det = page.locator("#tlDetail")
    expect(det).to_contain_text("Calculations used: Sell 20% a day v1")
    expect(det).to_contain_text("1 of 5")
    page.click("#veh button:text-is('All funds')")


def test_trd_26_template_needs_a_second_person(sign_in, app_url):
    """TRD-26: an analyst proposes a template; it isn't usable until a risk user with Approver approves it."""
    page = sign_in("Priya Raman", "analyst")
    page.goto(app_url + "/trading")
    trading_tab(page, "Routing & settings")
    card = page.locator("#cardCalcs")
    expect(card).to_contain_text("Sell 20% a day")
    page.fill("#cName", "Sell a third a day")
    page.select_option("#cKind", "even_split")
    page.fill("[data-cp=tranches]", "3")
    page.fill("#cReason", R)
    page.click("#cGo")
    _toast(page, "proposed and recorded")
    row = card.locator("tr", has_text="Sell a third a day")
    expect(row).to_contain_text("Not yet approved")
    assert row.locator("[data-cd]").count() == 0                      # analyst can't approve
    page = sign_in("Daniel Okafor", "risk", "approver")
    page.goto(app_url + "/trading")
    trading_tab(page, "Routing & settings")
    page.locator("#cardCalcs tr", has_text="Sell a third a day").locator("button:text-is('Approve')").click()
    page.fill("dialog.mdlg textarea", R)
    page.click("dialog.mdlg button[value=ok]")
    _toast(page, "approved and recorded")
    expect(page.locator("#cardCalcs tr", has_text="Sell a third a day")).to_contain_text("v1 · Sells: 3 equal tranches")


def test_reg_07_fiscal_year_end(sign_in, app_url):
    """REG-7: set a fund's fiscal year end; its annual obligations move to the fiscal period and it's logged."""
    page = sign_in("Nina Alvarez", "compliance")
    page.goto(app_url + "/regulations")
    page.wait_for_selector("[data-sel]")
    page.check("[data-sel='MTRS-2065']")
    page.select_option("#rgReg", "ICA40")
    page.fill("#rgReason", R)
    page.click("#rgAdd")
    _toast(page, "added to 1 funds")
    page.check("[data-sel='MTRS-2065']")
    page.select_option("#fyMonth", "09-30")
    page.fill("#fyReason", R)
    page.click("#fySet")
    _toast(page, "Fiscal year end updated for 1 funds")
    expect(page.locator("[data-fund='MTRS-2065']")).to_contain_text("September 30")
    page.click("[data-fund='MTRS-2065']")
    expect(page.locator("#fundDetail")).to_contain_text("September 30")
    expect(page.locator("#fundDetail")).to_contain_text("Sep")
    page.click(".tabs button:text-is('Change log')")
    expect(page.locator("#log")).to_contain_text("fund.fiscal_year_end")
