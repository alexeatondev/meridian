"""UAT-PM: Portfolio Manager (persona: Maya Chen). See docs UAT scripts, section PM."""
from playwright.sync_api import expect

from conftest import open_tab, tabs, toast_text

PM_TABS = ["Home", "Funds & vintages", "Positioning", "Proposals", "Changes since last run", "Fund risk",
           "Risk budget", "Metrics", "Look-through & search", "Glide path", "Approvals", "Exceptions", "Agent votes"]


def test_pm_01_sees_only_pm_workspace(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    assert [o.get_attribute("value") for o in p.query_selector_all("#role option")] == ["pm"]
    assert sorted(tabs(p)) == sorted(PM_TABS)  # grouped sidebar: order follows the section headings
    assert "Maya Chen" in p.inner_text(".mbar") and p.text_content("#nav .navh") == "Overview"
    view = p.inner_text("#view")
    assert "Needs your attention" in view and "proposals await your approval" in view and "The series at a glance" in view


def test_pm_02_approval_needs_acknowledgement_and_reason(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    open_tab(p, "Proposals")
    p.click("[data-vt='2040']")
    p.click("[data-decide=approve]")
    assert "Confirm you read" in toast_text(p)
    p.check("#ack")
    p.fill("#reason", "too short")
    p.click("[data-decide=approve]")
    assert "at least 10 characters" in toast_text(p)


def test_pm_03_review_and_approve_a_vintage(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    open_tab(p, "Proposals")
    p.click("[data-vt='2050']")
    view = p.inner_text("#view")
    for section in ("What is being approved", "Nothing is traded by this approval", "Why the agents recommend it",
                    "What would change the view", "Disagreement among the agents", "Compliance"):
        assert section in view
    p.check("#ack")
    p.fill("#reason", "Tilts are small, TE well inside budget, no FAILs.")
    p.click("[data-decide=approve]")
    assert "Decision recorded in the ledger" in toast_text(p)   # shown after the API call succeeds
    p.reload()
    p.wait_for_selector("#nav button")
    open_tab(p, "Approvals")
    row = p.locator("#view tr", has_text="2050").filter(has_text="Portfolio manager")
    assert "approve" in row.first.inner_text().lower() and "MTRT-2050" in row.first.inner_text()


def test_pm_04_adjust_weights_recomputes_risk_and_compliance(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    open_tab(p, "Positioning")
    p.click("[data-posmode='vintage']")
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
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    open_tab(p, "Proposals")
    p.click("[data-vt='2050']")
    view = p.inner_text("#view")
    assert "The weights" in view and "Tilts at a glance" in view and "chosen by the CIO agent using the" in view


def test_pm_06_reviewer_without_approver_permission(sign_in):
    """PM-6: a PM without the Approver permission reviews the proposal but sees no decision buttons."""
    p = sign_in("Jordan Ellis", "portfolio_manager")
    open_tab(p, "Proposals")
    expect(p.locator("#view")).to_contain_text("Approver")
    expect(p.locator("[data-decide]")).to_have_count(0)
    open_tab(p, "Approvals")
    expect(p.locator("#view")).to_contain_text("Nothing is waiting for your decision")
