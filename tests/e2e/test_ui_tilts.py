"""TRD-32: tilts table on Trading: tilt toward or away from holdings in many funds at once, preview, save."""
from playwright.sync_api import expect

from conftest import trading_tab


def test_trd_32_tilts_table(sign_in, app_url):
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    page.click("#veh button:text-is('Mutual funds')")
    trading_tab(page, "Tilts")
    page.wait_for_selector(".tg input[data-tg]")
    expect(page.locator(".tg th:has-text('MTRT')")).to_have_count(0)
    cells = page.locator("[data-tg^='MTRS-2040|']")
    a, b = cells.nth(0).get_attribute("data-tg"), cells.nth(1).get_attribute("data-tg")
    page.fill(f"[data-tg='{a}']", "0.5")
    page.fill(f"[data-tg='{b}']", "-0.25")
    page.fill(f"[data-tg^='MTRS-2060|'] >> nth=0", "0.3")
    expect(page.locator("#tgN")).to_have_text("3 security tilts changed")
    page.click("#tgPrev")
    out = page.locator("#tgOut")
    expect(out).to_contain_text("Preview: glide-path allocation")
    expect(out.locator("table").last.locator("th")).to_have_count(3)     # security + 2 funds changed
    expect(out).to_contain_text("Change by asset class")
    expect(out).to_contain_text("tilt 0.00→+0.50")
    page.click("#tgSave")
    page.fill("dialog textarea", "UAT: tilt via the table")
    page.click("dialog [value=ok]")
    expect(page.locator("#mtoasts")).to_contain_text("Tilts saved: 3 set, 0 cleared across 2 funds", timeout=8000)
    expect(page.locator(f"[data-tg='{a}']")).to_have_value("0.5")
    # analysts see the table read-only
    page = sign_in("Priya Raman", "analyst")
    page.goto(app_url + "/trading")
    trading_tab(page, "Tilts")
    page.wait_for_selector(".tg input[data-tg]")
    expect(page.locator("#tilts")).to_contain_text("Read-only")
    assert page.locator("#tgPrev").count() == 0


def test_trd_33_tilts_by_level(sign_in, app_url):
    """TRD-33: tilts entered at a level (1-5) instead of security by security: US equity +1pp in one fund (international
    gives it), a relative change in another; Meridian turns them into security tilts that still total 100%."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    page.click("#veh button:text-is('Mutual funds')")
    trading_tab(page, "Tilts")
    page.wait_for_selector(".tg input[data-tg]")
    page.click("[data-tgt='mode'][data-v='pp']")
    expect(page.locator(".tg tr[data-row] td.tg-sec:has-text('Equity')").first).to_be_visible()
    page.fill("[data-th='MTRS-2040|equity_us']", "1")
    expect(page.locator("[data-tgchk='MTRS-2040']")).to_contain_text("100%")
    page.click("[data-tgt='bal'][data-v='none']")
    expect(page.locator("[data-tgchk='MTRS-2040']")).to_contain_text("net +1.00")
    page.click("[data-tgt='bal'][data-v='parent']")
    page.click("[data-tgt='mode'][data-v='rel']")                     # switching mode clears the table
    expect(page.locator("[data-tgchk='MTRS-2040']")).to_have_count(0)
    page.fill("[data-th='MTRS-2050|emerging_eq']", "10")
    page.click("#tgPrev")
    out = page.locator("#tgOut")
    expect(out).to_contain_text("MTRS")
    expect(out).to_contain_text("MER-EM-MF")
    expect(page.locator("#tgSave")).to_contain_text("Save 2 tilt changes")   # EM up, developed down


def test_trd_34_security_lineup(sign_in, app_url):
    """TRD-34: add a security to several funds and vintages from Trading → Security line-up, preview, save."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    trading_tab(page, "Security line-up")
    page.fill("#luQ", "IEFA")
    page.click("[data-luinst='IEFA']")
    page.select_option("#luScope", "vehicle:mutual_fund")
    page.click("[data-luvset='far']")
    expect(page.locator("#lineup")).to_contain_text("5 funds")
    page.fill("#luPct", "25")
    page.click("#luPrev")
    out = page.locator("#luOut")
    expect(out).to_contain_text("IEFA set to 25% of International Developed Equity")
    expect(out).to_contain_text("100.0→75.0")
    page.click("#luSave")
    page.fill("dialog textarea", "UAT: IEFA liquidity sleeve in 2050-2070")
    page.click("dialog [value=ok]")
    expect(page.locator("#mtoasts")).to_contain_text("Saved: IEFA set to 25%", timeout=8000)
    expect(page.locator("tr[data-lusec='IEFA'] td.tg-ed").first).to_be_visible()
    # the console's glide-path table points here for level 5
    page.goto(app_url + "/runs/latest")
    page.click("#nav button:text-is('Glide path')")
    page.click("#gpLineup")
    expect(page.locator(".tabs button.active")).to_have_text("Security line-up")
