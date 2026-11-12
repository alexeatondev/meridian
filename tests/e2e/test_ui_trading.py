"""UAT-TRD: Trading workspace (doc 17) driven in the browser."""
import csv
import io

from playwright.sync_api import expect

R = "UAT: browser test reason"


def _toast(page, text):
    expect(page.locator("#mtoasts")).to_contain_text(text, timeout=8000)


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


def test_trd_03_route_permission_logged_and_roles(sign_in, app_url):
    """TRD-7/8: routes need the route permission and a reason and are logged; analysts can't change settings."""
    page = sign_in("Jordan Ellis", "portfolio_manager")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Routing & settings')")
    assert page.locator("[data-route=bond]").is_disabled()
    expect(page.locator("#rtWho")).to_contain_text("You do not hold the route permission")
    page = sign_in("Maya Chen", "portfolio_manager", "route_manager")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Routing & settings')")
    page.select_option("[data-route=bond]", "State Street")
    page.fill("#setReason", "short")
    page.click("#setSave")
    _toast(page, "at least 10")
    page.fill("#setReason", R)
    page.click("#setSave")
    _toast(page, "Saved and recorded: routes")
    expect(page.locator("#settings")).to_contain_text("routes.change")
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


def test_trd_04_tilt_exit_ticket_and_tranches(sign_in, app_url):
    """TRD-10 to TRD-13: tilt and exit flag, manual ticket, exit trade list, unequal tranches with checks."""
    page = sign_in("Maya Chen", "portfolio_manager")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Routing & settings')")
    page.select_option("#tiInst", "MER-EM-MF")
    page.select_option("#tiFund", "MTRS-2060")
    page.fill("#tiBps", "50")
    page.click("#tiAdd")
    page.select_option("#exitInst", "MER-LISC-MF")
    page.select_option("#exitFund", "MTRS-2060")
    page.click("#exitAdd")
    page.fill("#setReason", R)
    page.click("#setSave")
    _toast(page, "Saved and recorded: exits, tilts")
    page.click(".tabs button:text-is('Funds & securities')")
    page.click("[data-fund='MTRS-2060']")
    d = page.locator("#fundDetail")
    expect(d).to_contain_text("Tilt +50 bp")
    expect(d).to_contain_text("Exiting")
    # manual ticket: buy the candidate ETF
    page.select_option("[data-tki='0']", "IEFA")
    page.fill("[data-tka='0']", "2000000")
    page.fill("#tkReason", R)
    page.click("#tkGo")
    _toast(page, "ticket created")
    det = page.locator("#tlDetail")
    expect(det).to_contain_text("IEFA")
    expect(det).to_contain_text("Internal trading desk")
    # exit trade list, then tranche it 25/75 over two days
    page.click(".tabs button:text-is('Funds & securities')")
    page.click("[data-fund='MTRS-2060']")
    page.wait_for_selector("#tkExit")
    page.wait_for_timeout(400)
    page.fill("#tkReason", R)
    page.click("#tkExit")
    _toast(page, "exit trade list created")
    expect(det).to_contain_text("MER-LISC-MF")
    page.click("#tlv button:has-text('Tranches')")
    page.fill("[data-sp='0']", "25")
    page.fill("[data-sp='1']", "70")
    page.click("#trApply")
    _toast(page, "95.00%")
    page.fill("[data-sp='1']", "75")
    page.click("#trApply")
    page.click("#trSave")
    _toast(page, "Tranches saved: 1 orders across 2 dates")
    expect(det).to_contain_text("Bucket by date")
    expect(det).to_contain_text("1 of 2")
    expect(det).to_contain_text("25.00%")


def test_trd_17_bulk_glide_path_and_tilt(sign_in, app_url):
    """TRD-17/18: glide-path change for all CITs, approved by an IC member; asset-class tilt on all mutual funds."""
    page = sign_in("Jordan Ellis", "portfolio_manager")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Glide path & bulk changes')")
    page.select_option("#bkScope", "vehicle:cit")
    expect(page.locator("#bkCount")).to_contain_text("9")
    page.fill("#bkReason", R)
    page.select_option("[data-sha='0']", "us_large_cap")
    page.select_option("[data-shf='0']", "us_core_bond")
    page.fill("[data-shp='0']", "1")
    page.click("#gpPrev")
    expect(page.locator("#gpPreview")).to_contain_text("Within IPS bands")
    page.click("#gpReq")
    _toast(page, "sent to the Investment Committee")
    page.select_option("#bkScope", "vehicle:mutual_fund")
    page.fill("#bkReason", R)
    page.select_option("#bkTiKind", "asset_class")
    page.select_option("#bkTiItem", "emerging_eq")
    page.fill("#bkTiBps", "25")
    page.click("#bkTiGo")
    _toast(page, "Tilt applied to 9 funds")
    page = sign_in("Elena Rossi", "leadership", "investment_committee")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Glide path & bulk changes')")
    page.fill("#bkReason", R)
    page.locator("[data-gpd$=':approve']").first.click()
    _toast(page, "approved")
    expect(page.locator("#bulk")).to_contain_text("All CITs")
    page.click(".tabs button:text-is('Funds & securities')")
    expect(page.locator("[data-fund='MTRT-2050']")).to_contain_text("Glide path adjusted")
