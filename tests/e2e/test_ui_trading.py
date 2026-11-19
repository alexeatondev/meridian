"""UAT-TRD: Trading workspace (doc 17) driven in the browser."""
import csv
import re
import io

from playwright.sync_api import expect

from conftest import trade_create, trade_preview, trade_setup, trading_tab

R = "UAT: browser test reason"


def _toast(page, text):
    expect(page.locator("#mtoasts")).to_contain_text(text, timeout=8000)


def test_trd_01_vehicle_toggle_and_universe(sign_in, app_url):
    """TRD-1/2: vehicle toggle shows all, mutual funds or CITs; fund detail shows held, no-target and candidates."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.click("a[href='/trading']")
    trading_tab(page, "Funds & securities")
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
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
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
    trade_setup(page, "invest", strat="previous_close")
    trade_preview(page)
    imp = page.locator("#trade")
    expect(imp).to_contain_text("Impact: now vs after")
    expect(imp).to_contain_text("MTRT-2045")
    expect(imp).not_to_contain_text("MTRS-2045")
    trade_create(page, R)
    _toast(page, "draft created")
    det = page.locator("#tlDetail")
    page.click("#tlv button:text-is('Orders')")
    expect(det).to_contain_text("MTRT-2045")
    expect(det).to_contain_text("State Street")
    expect(det).not_to_contain_text("MTRS-2045")
    expect(det).to_contain_text("PASS")
    page.click("#tlv button:text-is('Impact: now vs after')")
    expect(det.locator(".mixrow").first).to_be_visible()
    expect(det).to_contain_text("Off target")
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
    page = sign_in("Jordan Ellis", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Routing & settings')")
    assert page.locator("[data-route=bond]").is_disabled()
    expect(page.locator("#rtWho")).to_contain_text("You do not hold the route permission")
    page = sign_in("Maya Chen", "portfolio_manager", "route_manager", "approver")
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
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
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
    # manual ticket from the fund page: buy the candidate ETF
    page.click("#fdTrade")
    page.fill("#ntQ", "IEFA")
    page.click("[data-add='IEFA']")
    page.fill("[data-oval='0']", "2000000")
    page.locator("[data-oval='0']").dispatch_event("change")
    expect(page.locator("#trade")).to_contain_text("Buy $2.0m")
    trade_preview(page)
    trade_create(page, R)
    _toast(page, "draft created with 1 orders")
    det = page.locator("#tlDetail")
    page.click("#tlv button:text-is('Orders')")
    expect(det).to_contain_text("IEFA")
    expect(det).to_contain_text("Internal trading desk")
    # exit trade list, then tranche it 25/75 over two days
    trading_tab(page, "Funds & securities")
    page.click("[data-fund='MTRS-2060']")
    page.click("#fdExit")
    expect(page.locator("#trade")).to_contain_text("MER-LISC-MF")
    trade_preview(page)
    trade_create(page, R)
    _toast(page, "draft created")
    page.click("#tlv button:text-is('Orders')")
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
    page = sign_in("Jordan Ellis", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    page.click(".tabs button:text-is('Glide path & bulk changes')")
    page.select_option("#bkScope", "vehicle:cit")
    expect(page.locator("#bkCount")).to_contain_text("9")
    page.fill("#bkReason", R)
    st, r = page.evaluate("""async () => { const r = await fetch('/api/trading/glide-path/requests', {method:'POST',
        headers:{'Content-Type':'application/json','X-CSRF-Token':BOOT.csrf}, body: JSON.stringify({kind:'table', reason:'UAT: table request',
        rows:[{fund_id:'MTRT-2050', deltas:{us_large_cap:1, us_core_bond:-1}}, {fund_id:'MTRT-2055', deltas:{us_large_cap:1, us_core_bond:-1}}]})});
        return [r.status, await r.json()] }""")
    assert st == 200 and r["funds"] == 2
    expect(page.locator("#gpOpenTable")).to_be_visible()
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
    expect(page.locator("#bulk")).to_contain_text("MTRT-2055")
    page.click(".tabs button:text-is('Funds & securities')")
    expect(page.locator("[data-fund='MTRT-2050']")).to_contain_text("Glide path adjusted")


def test_trd_20_new_trade_tasks_and_roles(sign_in, app_url):
    """TRD-20: New trade opens first with four task tiles; analysts prepare but can't rebalance; preview saves nothing."""
    page = sign_in("Priya Raman", "analyst")
    page.goto(app_url + "/trading")
    expect(page.locator(".tabs button.active")).to_have_text("New trade")
    expect(page.locator("[data-task]")).to_have_count(4)
    assert page.locator("[data-task='rebalance']").is_disabled()
    assert not page.locator("[data-task='security']").is_disabled()
    before = page.evaluate("S.st.trade_lists.length")
    trade_setup(page, "security", fund="MTRS-2050")
    expect(page.locator("[data-add]")).not_to_have_count(0)
    page.locator("[data-add]").first.click()
    page.select_option("[data-oact='0']", "weight")
    trade_preview(page)
    assert page.evaluate("S.st.trade_lists.length") == before        # dry run: nothing saved


def test_trd_21_trade_to_weight_shows_now_vs_after(sign_in, app_url):
    """TRD-21: trade one security to a target weight (cash warning when buys exceed cash); impact shows now, after, target and glide path by asset class."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    trade_setup(page, "security", fund="MTRS-2040")
    held = page.evaluate("S.nt.fd.rows.filter(r=>r.value>0 && r.type!=='cash' && !r.excluded).sort((a,b)=>b.value-a.value)[0]")
    page.fill("#ntQ", held["instrument"])
    page.click(f"[data-add='{held['instrument']}']")
    page.select_option("[data-oact='0']", "weight")
    page.fill("[data-oval='0']", str(round(held["weight"] * 100 + 5.0, 2)))
    page.locator("[data-oval='0']").dispatch_event("change")
    expect(page.locator("#ntCashWarn")).to_contain_text("Not enough cash")
    new_w = round(held["weight"] * 100 - 1.0, 2)
    page.fill("[data-oval='0']", str(new_w))
    page.locator("[data-oval='0']").dispatch_event("change")
    expect(page.locator("#trade")).to_contain_text(f"{new_w:.2f}%")
    trade_preview(page)
    imp = page.locator("#trade")
    for text in ("Off target", "Now", "After", "Target", "Glide path", "Compliance"):
        expect(imp).to_contain_text(text)
    expect(imp.locator(".mixrow").first).to_be_visible()
    order = page.evaluate("S.nt.prev.funds[0].orders[0]")
    assert order["instrument"] == held["instrument"] and order["side"] == "SELL"


def test_trd_22_rebalance_toward_glide_path_reduces_gap(sign_in, app_url):
    """TRD-22: rebalance toward the glide path (neutral) closes the gap: off target after ≤ before, per fund."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    trade_setup(page, "rebalance", strat="neutral")
    page.select_option("#ntFunds", "MTRS-2070")
    trade_preview(page)
    f = page.evaluate("S.nt.prev.funds[0]")
    assert f["fund_id"] == "MTRS-2070"
    assert f["impact"]["gap_to_target_after"] <= f["impact"]["gap_to_target_before"] + 1e-9
    expect(page.locator("#trade")).to_contain_text("Off target")


def test_trd_23_goal_shortcuts(sign_in, app_url):
    """TRD-23: 'Start from your goal' sets up the right task and strategy (glide path, night close, strategic)."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    page.locator("tr", has_text="Get back to the glide path").locator("[data-goal]").click()
    expect(page.locator("[data-task='rebalance']")).to_have_class(re.compile(r"\bon\b"))
    expect(page.locator("input[name=ntStrat][value='neutral']")).to_be_checked()
    page.click("[data-task='invest']")
    page.goto(app_url + "/trading")
    page.evaluate("S.nt.task=null; vTrade()")
    page.locator("tr", has_text="stay as positioned last night").locator("[data-goal]").click()
    expect(page.locator("input[name=ntStrat][value='previous_close']")).to_be_checked()


def test_trd_24_bulk_vintage_picker(sign_in, app_url):
    """TRD-24: Glide path & bulk changes picks vintages by clicking; an empty pick is refused, never 'all funds'."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    trading_tab(page, "Glide path & bulk changes")
    page.select_option("#bkScope", "vehicle:mutual_fund")
    expect(page.locator("#bkCount")).to_contain_text("Applies to 9 funds · all vintages")
    page.click("[data-bkvset='far']")
    expect(page.locator("#bkCount")).to_contain_text("Applies to 5 funds · 5 vintages")
    page.click("[data-bkv='2060']")
    expect(page.locator("#bkCount")).to_contain_text("Applies to 4 funds · 4 vintages")
    page.click("[data-bkvset='none']")
    expect(page.locator("#bkCount")).to_contain_text("Pick at least one vintage")
    page.select_option("#bkScope", "MTRS-2040")
    expect(page.locator("#bkVwrap")).to_be_hidden()
    expect(page.locator("#bkCount")).to_contain_text("Applies to 1 fund")
