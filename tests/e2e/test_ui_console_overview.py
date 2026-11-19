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
    p.click("[data-gpt='rows'][data-v='cit']")
    for v in ("2050", "2055"):
        p.fill(f"[data-gpr='cit:{v}'][data-gpa='us_core_bond']", "0.5")
        p.fill(f"[data-gpr='cit:{v}'][data-gpa='us_large_cap']", "-0.5")
    p.click("#gpPrev")
    p.wait_for_selector("#gpSubmit")
    assert "Preview: 2 funds change" in p.inner_text("#gpOut")
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


def test_gp_01_glide_path_table(sign_in):
    """GP-1: glide-path changes typed into a table (several vintages and asset classes at once), checked per row,
    previewed fund by fund in a table, sent as one request."""
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    open_tab(p, "Glide path")
    assert p.locator("#gpScope").count() == 0 and p.locator("[data-gpv]").count() == 0
    expect(p.locator(".gpt tr")).to_have_count(10)                      # header + 9 vintages
    p.fill("[data-gpr='vintage:2030'][data-gpa='cash']", "1")
    expect(p.locator("[data-gpnet='vintage:2030']")).to_have_text("+1.00")
    p.click("#gpPrev")
    assert "net to zero" in toast_text(p)
    p.fill("[data-gpr='vintage:2030'][data-gpa='us_core_bond']", "-1")
    expect(p.locator("[data-gpnet='vintage:2030']")).to_have_text("0.00")
    p.fill("[data-gpr='vintage:2060'][data-gpa='us_large_cap']", "0.75")
    p.fill("[data-gpr='vintage:2060'][data-gpa='intl_developed_eq']", "-0.75")
    p.click("#gpPrev")
    out = p.locator("#gpOut")
    expect(out).to_contain_text("Preview: 4 funds change")             # MF and CIT for 2030 and 2060
    for f in ("MTRS-2030", "MTRT-2030", "MTRS-2060", "MTRT-2060"):
        expect(out).to_contain_text(f)
    expect(out).not_to_contain_text("MTRS-2045")
    expect(out.locator("td.gpchg")).to_have_count(8)                     # 2 changed cells x 4 funds
    # weight mode: type the new weight; a change beyond the IPS band is shown in red and can't be submitted
    p.click("[data-gpt='mode'][data-v='weight']")
    p.click("[data-gpt='rows'][data-v='fund']")
    cur = float(p.get_attribute("[data-gpr='MTRS-2045'][data-gpa='cash']", "placeholder"))
    core = float(p.get_attribute("[data-gpr='MTRS-2045'][data-gpa='us_core_bond']", "placeholder"))
    p.fill("[data-gpr='MTRS-2045'][data-gpa='cash']", f"{cur + 4:.2f}")
    p.fill("[data-gpr='MTRS-2045'][data-gpa='us_core_bond']", f"{core - 4:.2f}")
    p.click("#gpPrev")
    expect(out.locator("td.gpbad").first).to_be_visible()
    expect(out).to_contain_text("FAIL")
    assert p.locator("#gpSubmit").count() == 0
