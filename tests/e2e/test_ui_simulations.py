"""SIM-1..4: Simulations page (cashflow typed in, across funds or per vintage), exit a position across funds,
management style from the console and Trading."""
from playwright.sync_api import expect

from conftest import open_tab, trade_create, trade_preview, trade_setup, trading_tab


def test_sim_1_cashflow_simulation(sign_in, app_url):
    """SIM-1: $100m across all funds by assets, then $100m to the 2030 vintage only; nothing saved."""
    page = sign_in("Priya Raman", "analyst")
    page.goto(app_url + "/simulations")
    expect(page.locator("header h1")).to_have_text("Simulations")
    expect(page.locator(".mbar nav a[aria-current=page]")).to_have_text("Simulations")
    page.wait_for_selector("#simRun")
    expect(page.locator("#simTot")).to_have_text("$100.0m")
    page.click("#simRun")
    out = page.locator("#simOut")
    expect(out).to_contain_text("Simulated trades: $100.0m in")
    expect(out).to_contain_text("By fund")
    # per vintage: only 2030, split between its mutual fund and CIT
    page.click("[data-simsplit='vintage']")
    page.fill("[data-simva='2030']", "100")
    expect(page.locator("#simTot")).to_have_text("$100.0m")
    page.click("#simRun")
    expect(out).to_contain_text("in 2 funds")
    expect(out).to_contain_text("MTRS-2030")
    expect(out).to_contain_text("MTRT-2030")
    # links to the other simulations
    expect(page.locator("[data-simgo='stress']")).to_contain_text("Stress tests")
    # nothing was saved
    page.goto(app_url + "/trading")
    trading_tab(page, "Trade lists")
    expect(page.locator("#trades")).not_to_contain_text("SIMULATION")


def test_sim_2_exit_across_funds(sign_in, app_url):
    """SIM-2: exit one security in every CIT that holds it, in one trade list."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    trade_setup(page, "exit")
    page.select_option("#exScope", "vehicle:cit")
    page.click("[data-exvset='far']")
    page.fill("#exQ", "MER-EM-CIT")
    page.click("[data-exadd='MER-EM-CIT']")
    expect(page.locator("#trade")).to_contain_text("To exit")
    trade_preview(page)
    imp = page.locator("#trade")
    expect(imp).to_contain_text("Flagged for exit when you save")
    expect(page.locator("[data-impf^='nt|']")).to_have_count(5)          # MTRT-2050..2070, one list
    expect(page.locator("[data-impf='nt|MTRT-2050']")).to_have_count(1)
    expect(page.locator("[data-impf='nt|MTRS-2050']")).to_have_count(0)
    trade_create(page, "UAT: exit EM equity fund in far-dated CITs")
    expect(page.locator("#tlDetail h2").first).to_contain_text("EX-")


def test_sim_3_style_from_console_and_trading(sign_in, app_url):
    """SIM-3: a PM changes a fund's management style from the console and from Trading without hunting for it."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    open_tab(page, "Funds & vintages")
    page.click("button[data-styedit='*']")
    sel = page.locator("dialog [data-msty='MTRS-2040']")
    want, label = ("passive", "Passive") if sel.input_value() == "active" else ("active", "Active")
    sel.select_option(want)
    page.fill("dialog textarea", "UAT: 2040 management style changed")
    page.click("dialog [value=ok]")
    expect(page.locator("#mtoasts")).to_contain_text("Management style saved for 1 fund")
    expect(page.locator("[data-styedit='MTRS-2040']").first).to_contain_text(label)
    page.goto(app_url + "/trading")
    trading_tab(page, "Funds & securities")
    page.click("[data-fund='MTRS-2045']")
    page.click("#fundDetail [data-trsty='MTRS-2045']")
    sel = page.locator("dialog [data-msty='MTRS-2045']")
    want, label = ("passive", "Passive") if sel.input_value() == "hybrid" else ("hybrid", "Hybrid")
    sel.select_option(want)
    page.fill("dialog textarea", "UAT: hybrid core plus sleeves")
    page.click("dialog [value=ok]")
    expect(page.locator("#mtoasts")).to_contain_text("Management style saved")
    expect(page.locator("#fundDetail [data-trsty='MTRS-2045']")).to_contain_text(label)


def test_sim_4_tilt_preview_nets_to_zero(sign_in, app_url):
    """SIM-4: a security tilt previews as asset-class changes that net to zero."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    trading_tab(page, "Tilts")
    page.wait_for_selector(".tg input[data-tg]")
    a = page.locator("[data-tg^='MTRS-2040|']").nth(0).get_attribute("data-tg")
    page.fill(f"[data-tg='{a}']", "1")
    page.click("#tgPrev")
    expect(page.locator("#tgOut")).to_contain_text("Change by asset class")
    expect(page.locator("[data-tgpnet='MTRS-2040']")).to_have_text("✓ 0.00")
