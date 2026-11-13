"""UAT: product lines, series summaries, clearer approvals, glide-path adjustments and ticker search
(product owner feedback, 2026-11-13)."""
from playwright.sync_api import expect

from conftest import open_tab, toast_text


def test_ux_01_funds_split_by_product_line(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    open_tab(p, "Funds & vintages")
    view = p.inner_text("#view")
    assert "Meridian Target Retirement Funds" in view and "Meridian Target Retirement Trust" in view
    assert "MTRS-2050" in view and "MTRT-2050" in view
    p.click("[data-pl='cit']")
    view = p.inner_text("#view")
    assert "MTRT-2050" in view and "MTRS-2050" not in view
    p.click("[data-pf='MTRT-2050']")
    assert "Glide path CIT" in p.inner_text("#view")


def test_ux_02_positioning_series_summary_and_fund_comparison(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    open_tab(p, "Positioning")
    view = p.inner_text("#view")
    assert "Series positioning" in view and "Series" in view and "Equity, held today" in view
    p.click("[data-posmeasure='drift']")
    assert "Held today minus proposed" in p.inner_text("#view")
    p.click("[data-posv='2050']")
    view = p.inner_text("#view")
    assert "2050 by fund: mutual fund and CIT" in view and "Mutual fund holds" in view and "CIT holds" in view


def test_ux_03_approval_queue_has_summaries(sign_in):
    p = sign_in("Daniel Okafor", "risk", "approver")
    open_tab(p, "Approvals")
    view = p.inner_text("#view")
    assert "Waiting for you" in view and "awaits your approval as Risk" in view
    assert "Largest tilts" in view and "Tracking error" in view and "Funds affected" in view
    assert "does not place trades" in view


def test_ux_04_risk_budget_series_summary_and_preview(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    open_tab(p, "Risk budget")
    view = p.inner_text("#view")
    assert "Risk budget used across the series" in view and "Where the budget goes, across the series" in view
    assert "Use less (or more) of the budget" in view and "Change the budget itself" in view
    p.select_option("#rbV", "2050")
    p.fill("#rbTe", "0.30")
    assert "over budget" in p.inner_text("#rbPrev")


def test_ux_05_agent_votes_in_plain_language(sign_in):
    p = sign_in("Priya Raman", "analyst")
    open_tab(p, "Agent votes")
    view = p.inner_text("#view")
    assert "How the agents decided" in view and "Scoreboard" in view and "Best risk-adjusted return" in view
    p.click("[data-agsel='max_sharpe_tilt']")
    assert "Reviews it received" in p.inner_text("#view")


def test_ux_06_ticker_search_pick_one(sign_in):
    p = sign_in("Daniel Okafor", "risk", "approver")
    open_tab(p, "Look-through & search")
    if "not loaded" in p.inner_text("#view"):
        return      # offline test data may have no look-through holdings
    before = p.evaluate("document.querySelector('.section-title').getBoundingClientRect().top")
    p.fill("#ltq", "a")
    p.wait_for_selector("#ltSug [data-i]")
    after = p.evaluate("document.querySelector('.section-title').getBoundingClientRect().top")
    assert abs(before - after) < 1, "typing must not move the page"
    p.keyboard.press("ArrowDown")
    p.keyboard.press("Enter")
    sel = p.inner_text(".selbar")
    assert "Selected" in sel and "Exposure by portfolio" in p.inner_text("#view")
    p.click("#ltClear")
    assert p.query_selector(".selbar") is None


def test_ux_07_glide_path_adjustment_request_and_committee_decision(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    open_tab(p, "Glide path")
    assert "Glide path today, by fund" in p.inner_text("#view")
    p.select_option("#gpScope", "vehicle:cit")
    p.select_option("[data-gpi='0'][data-gpk='asset_class']", "us_core_bond")
    p.select_option("[data-gpi='0'][data-gpk='from']", "us_large_cap")
    p.fill("[data-gpi='0'][data-gpk='pp']", "0.5")
    p.dispatch_event("[data-gpi='0'][data-gpk='pp']", "change")
    p.click("#gpPrev")
    p.wait_for_selector("#gpSubmit")
    assert "Preview: 9 funds" in p.inner_text("#gpOut")
    p.fill("#gpReason", "UAT: trim equity in the CITs for plan sponsors.")
    p.click("#gpSubmit")
    assert "sent to the Investment Committee" in toast_text(p)
    p.wait_for_timeout(1200)
    q = sign_in("Elena Rossi", "leadership", "investment_committee")
    open_tab(q, "Glide path")
    rid = q.get_attribute("[data-gpdec='approve']", "data-gpid")
    q.fill(f"#gpr-{rid}", "UAT: committee approves the CIT adjustment.")
    q.click(f"[data-gpdec='approve'][data-gpid='{rid}']")
    assert "approved" in toast_text(q)
    q.wait_for_timeout(1200)
    q.reload()
    q.wait_for_selector("#nav button")
    open_tab(q, "Glide path")
    view = q.inner_text("#view")
    assert rid in view and "Approved adjustments in force" in view and "adj." in view


def test_glide_path_vintage_picker(sign_in):
    """Glide path: pick vintages by clicking them (no From/To boxes); the count and the preview follow the picks."""
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    open_tab(p, "Glide path")
    assert p.locator("#gpVf").count() == 0 and p.locator("#gpVt").count() == 0
    p.select_option("#gpScope", "vehicle:cit")
    expect(p.locator("#gpVcount")).to_contain_text("All vintages selected · 9 funds")
    p.click("[data-gpvset='none']")
    expect(p.locator("#gpVcount")).to_contain_text("Pick at least one vintage")
    for v in ("2035", "2055", "2065"):
        p.click(f"[data-gpv='{v}']")
    expect(p.locator("#gpVcount")).to_contain_text("3 vintages selected · 3 funds")
    expect(p.locator("[data-gpv='2055']")).to_have_attribute("aria-pressed", "true")
    p.fill("[data-gpi='0'][data-gpk='pp']", "0.5")
    p.dispatch_event("[data-gpi='0'][data-gpk='pp']", "change")
    p.click("#gpPrev")
    expect(p.locator("#gpOut")).to_contain_text("3 funds")
    expect(p.locator("#gpOut")).to_contain_text("MTRT-2055")
    expect(p.locator("#gpOut")).not_to_contain_text("MTRT-2040")
