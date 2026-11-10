"""UAT-PM: Portfolio Manager (persona: Maya Chen). See docs UAT scripts, section PM."""
from conftest import open_tab, tabs, toast_text

PM_TABS = ["Home", "Funds & vintages", "Positioning", "Portfolios & proposals", "Changes since last run", "Fund risk",
           "Risk budget", "Metrics", "Look-through & search", "Glide path", "Approvals", "Exceptions", "Agent votes"]


def test_pm_01_sees_only_pm_workspace(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager")
    assert [o.get_attribute("value") for o in p.query_selector_all("#role option")] == ["pm"]
    assert tabs(p) == PM_TABS
    assert "Maya Chen" in p.inner_text("#roleHelp")
    assert "Proposals awaiting you" in p.inner_text("#view")


def test_pm_02_approval_needs_acknowledgement_and_reason(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager")
    open_tab(p, "Portfolios & proposals")
    p.click("[data-vt='2040']")
    p.click("[data-decide=approve]")
    assert "Confirm you read" in toast_text(p)
    p.check("#ack")
    p.fill("#reason", "too short")
    p.click("[data-decide=approve]")
    assert "at least 10 characters" in toast_text(p)


def test_pm_03_review_and_approve_a_vintage(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager")
    open_tab(p, "Portfolios & proposals")
    p.click("[data-vt='2050']")
    view = p.inner_text("#view")
    for section in ("Why this proposal?", "What would make this wrong", "Dissent", "Compliance"):
        assert section in view
    p.check("#ack")
    p.fill("#reason", "Tilts are small, TE well inside budget, no FAILs.")
    p.click("[data-decide=approve]")
    assert "Decision recorded in the ledger" in toast_text(p)   # shown after the API call succeeds
    p.reload()
    p.wait_for_selector("#nav button")
    open_tab(p, "Approvals")
    row = p.locator("#view tr", has_text="2050").filter(has_text="portfolio_manager")
    assert "approve" in row.first.inner_text().lower()


def test_pm_04_adjust_weights_recomputes_risk_and_compliance(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager")
    open_tab(p, "Positioning")
    p.click("[data-vt='2045']")
    nodes = [o.get_attribute("value") for o in p.query_selector_all("#adjNode option")]
    target = next(n for n in nodes if "Short-dated" in n)
    funder = next(n for n in nodes if "Long-dated" in n)
    p.select_option("#adjNode", target)
    p.select_option("#adjMode", "relative")
    p.fill("#adjVal", "1")
    p.select_option("#adjFund", funder)
    p.click("#adjAdd")
    p.fill("#adjReason", "Shorten duration ahead of supply.")
    p.click("#adjSubmit")
    msg = toast_text(p, timeout=30000)
    assert msg.startswith("Recorded: TE") and "compliance" in msg


def test_pm_05_explain_largest_change(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager")
    open_tab(p, "Portfolios & proposals")
    p.click("[data-vt='2050']")
    view = p.inner_text("#view")
    assert "Active weights vs glide path" in view and "Ensemble chosen" in view
