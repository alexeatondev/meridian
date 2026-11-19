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
    expect(page.locator("#tgN")).to_have_text("3 cells changed")
    page.click("#tgPrev")
    out = page.locator("#tgOut")
    expect(out).to_contain_text("Preview: glide-path allocation")
    expect(out.locator("th")).to_have_count(3)                           # security + 2 funds changed
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
