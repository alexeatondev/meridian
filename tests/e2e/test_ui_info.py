"""UX-9: info bubbles explain metrics, columns and buttons, with a simplified formula where there is one."""
from playwright.sync_api import expect

from conftest import open_tab, trading_tab


def test_ux_09_info_bubbles(sign_in, app_url):
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    th = p.locator("th:has(.minfo[data-minfo='tracking_error'])").first
    expect(th).to_have_text("Tracking error")                          # the label's text is unchanged
    b = th.locator(".minfo")
    expect(b).to_have_attribute("aria-label", "What is Tracking error (active risk)?")
    b.click()
    pop = p.locator(".minfo-pop")
    expect(pop).to_contain_text("Tracking error (active risk)")
    expect(pop).to_contain_text("How it's calculated")
    expect(b).to_have_attribute("aria-expanded", "true")
    p.keyboard.press("Escape")
    expect(pop).to_have_count(0)
    expect(b).to_be_focused()
    # tiles, and controls marked with data-info
    p.locator(".kpi .l:has-text('Highest risk-budget use') .minfo").click()
    expect(p.locator(".minfo-pop")).to_contain_text("tracking error ÷ risk budget")
    p.mouse.click(5, 300)                                                  # a click elsewhere closes it
    expect(p.locator(".minfo-pop")).to_have_count(0)
    open_tab(p, "Glide path")
    p.locator("[data-info='balance_mode'] .minfo").click()
    expect(p.locator(".minfo-pop")).to_contain_text("Within its level")
    # buttons: the bubble sits next to the button, not inside it
    p.goto(app_url + "/trading")
    trading_tab(p, "Funds & securities")
    expect(p.locator("th:has-text('NAV') .minfo").first).to_be_visible()
    p.locator("th:has-text('Management') .minfo").first.click()
    expect(p.locator(".minfo-pop")).to_contain_text("Active funds select securities")
