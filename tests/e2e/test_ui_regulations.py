"""UAT-REG: Regulations & obligations screen and the new trading steps (rebalance, fills)."""
from playwright.sync_api import expect

R = "UAT: browser test reason"


def _toast(page, text):
    expect(page.locator("#mtoasts")).to_contain_text(text, timeout=8000)


def test_reg_01_tag_fund_and_work_obligation(sign_in, app_url):
    page = sign_in("Nina Alvarez", "compliance")
    page.goto(app_url + "/regulations")
    page.wait_for_selector("[data-sel]")
    page.click("#veh button:text-is('Mutual funds')")
    page.check("[data-sel='MTRS-2045']")
    page.select_option("#rgReg", "ICA40")
    page.fill("#rgReason", R)
    page.click("#rgAdd")
    _toast(page, "ACT 40 added to 1 funds")
    row = page.locator("[data-fund='MTRS-2045']")
    expect(row).to_contain_text("ACT 40")
    row.click()
    expect(page.locator("#fundDetail")).to_contain_text("ICA-12D1-UNAFF")
    expect(page.locator("#fundDetail")).to_contain_text("Unfilled")
    assert page.locator("#rgRemove").count() == 0                      # analyst: no remove button
    page.click(".tabs button:text-is('Obligations')")
    page.locator("#tasks [data-task]", has_text="Form N-CEN").first.click()
    page.fill("#tkEvidence", "EDGAR accession 0001-26-000999")
    page.click("[data-act=complete]")
    _toast(page, "next occurrence created")
    page.click(".tabs button:text-is('Regulation library')")
    expect(page.locator("#library")).to_contain_text("International (ex-US)")
    expect(page.locator("#library")).to_contain_text("UCITS")


def test_reg_02_ucits_blocks_trade_list(sign_in, app_url):
    page = sign_in("Nina Alvarez", "compliance")
    page.goto(app_url + "/regulations")
    page.wait_for_selector("[data-sel]")
    page.check("[data-sel='MTRT-2060']")
    page.select_option("#rgReg", "UCITS")
    page.fill("#rgReason", R)
    page.click("#rgAdd")
    _toast(page, "added to 1 funds")
    page = sign_in("Maya Chen", "portfolio_manager")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Trades')")
    page.select_option("#rbStrat", "neutral")
    page.select_option("#rbFunds", "MTRT-2060")
    page.fill("#rbReason", R)
    page.click("#rbGo")
    _toast(page, "orders for 1 funds")
    det = page.locator("#tlDetail")
    expect(det).to_contain_text("UCITS-55-SINGLE")
    expect(det).to_contain_text("Blocked by errors or a compliance FAIL")


def test_trd_14_rebalance_export_and_fills(sign_in, app_url):
    page = sign_in("Maya Chen", "portfolio_manager")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Trades')")
    page.select_option("#rbStrat", "neutral")
    page.select_option("#rbFunds", "MTRS-2055")
    page.fill("#rbReason", R)
    page.click("#rbGo")
    _toast(page, "orders for 1 funds")
    page.check("#taChk")
    page.fill("#taReason", R)
    page.click("#taGo")
    _toast(page, "approved")
    with page.expect_download():
        page.click("#taCrd")
    page.wait_for_selector("#flAll")
    page.click("#flAll")
    _toast(page, "status filled")
    expect(page.locator("#tlDetail")).to_contain_text("Filled and booked")
    page.click(".tabs button:text-is('Funds & securities')")
    expect(page.locator("[data-fund='MTRS-2055']")).to_contain_text("Booked from")
