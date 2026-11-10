"""UAT-TRD: Trading workspace (doc 17) driven in the browser."""
import csv
import io

from playwright.sync_api import expect

R = "UAT: browser test reason"


def _toast(page, text):
    expect(page.locator("#toast")).to_contain_text(text, timeout=8000)


def test_trd_01_vehicle_toggle_and_universe(sign_in, app_url):
    """TRD-1/2: vehicle toggle shows all, mutual funds or CITs; fund detail shows held, no-target and candidates."""
    page = sign_in("Maya Chen", "portfolio_manager")
    page.click("a[href='/trading']")
    page.wait_for_selector("[data-fund]")
    assert page.locator("[data-fund]").count() == 18
    page.click("#veh button:text-is('CITs')")
    assert page.locator("[data-fund]").count() == 9 and page.locator("[data-fund='MTRT-2050']").count() == 1
    page.click("#veh button:text-is('Mutual funds')")
    assert page.locator("[data-fund^='MTRT']").count() == 0
    page.click("[data-fund='MTRS-2040']")
    d = page.locator("#fundDetail")
    expect(d).to_contain_text("Held · no target")
    expect(d).to_contain_text("Not held · candidate")
    expect(d).to_contain_text("IEFA")
    page.click("#veh button:text-is('All funds')")


def test_trd_02_cashflow_to_charles_river(sign_in, app_url):
    """TRD-3 to TRD-6: enter a cashflow, generate a CIT-only trade list, preview, approve, export."""
    page = sign_in("Maya Chen", "portfolio_manager")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Cashflows')")
    page.select_option("#cfFund", "MTRT-2045")
    page.fill("#cfAmt", "7500000")
    page.select_option("#cfSrc", "State Street")
    page.click("#cfAdd")
    _toast(page, "Cashflow added")
    page.select_option("#cfFund", "MTRS-2045")
    page.select_option("#cfType", "redemption")
    page.fill("#cfAmt", "4000000")
    page.click("#cfAdd")
    _toast(page, "Cashflow added")
    page.click("#veh button:text-is('CITs')")
    page.click(".tabs button:text-is('Trades')")
    page.select_option("#tgStrat", "previous_close")
    page.click("#tgGo")
    _toast(page, "orders for 1 funds")
    det = page.locator("#tlDetail")
    expect(det).to_contain_text("MTRT-2045")
    expect(det).to_contain_text("State Street")
    expect(det).not_to_contain_text("MTRS-2045")
    expect(det).to_contain_text("PASS")
    page.click("#tlv button:text-is('Current vs post-trade')")
    expect(det).to_contain_text("Post vs target")
    page.click("#taGo")
    _toast(page, "Confirm you reviewed")
    page.check("#taChk")
    page.fill("#taReason", R)
    page.click("#taGo")
    _toast(page, "approved")
    with page.expect_download() as dl:
        page.click("#taCrd")
    text = open(dl.value.path()).read()
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows and {r["Account"] for r in rows} == {"CIT2045"} and {r["Side"] for r in rows} == {"BUY"}
    assert {r["Destination"] for r in rows} <= {"State Street", "Internal trading desk"}
    page.click("#veh button:text-is('All funds')")


def test_trd_03_settings_logged_and_roles(sign_in, app_url):
    """TRD-7/8: route change needs a reason and is logged; analysts prepare but can't approve or change settings."""
    page = sign_in("Maya Chen", "portfolio_manager")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Routing & settings')")
    page.select_option("[data-route=bond]", "State Street")
    page.fill("#setReason", "short")
    page.click("#setSave")
    _toast(page, "at least 10")
    page.fill("#setReason", R)
    page.click("#setSave")
    _toast(page, "Saved and recorded: routes")
    expect(page.locator("#settings")).to_contain_text("settings.change")
    page.select_option("[data-route=bond]", "Internal trading desk")
    page.fill("#setReason", R + " (revert)")
    page.click("#setSave")
    _toast(page, "Saved and recorded")
    page = sign_in("Priya Raman", "analyst")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Routing & settings')")
    assert page.locator("#setSave").count() == 0
    assert page.locator("[data-route=etf]").is_disabled()
    page.click(".tabs button:text-is('Cashflows')")
    assert page.locator("#cfAdd").count() == 1
