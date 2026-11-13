"""UAT-RISK: Risk Analytics (persona: Daniel Okafor). See docs UAT scripts, section RISK."""
from conftest import open_tab, switch_workspace, tabs, toast_text

RISK_TABS = ["Home", "Fund risk", "Factor risk", "Stress tests", "Risk history", "Look-through & search",
             "Risk budget", "Metrics", "Candidate risk", "Positioning", "Proposals", "Approvals",
             "Exceptions"]


def test_risk_01_workspace(sign_in):
    p = sign_in("Daniel Okafor", "risk", "approver")
    assert sorted(tabs(p)) == sorted(RISK_TABS)  # grouped sidebar: order follows the section headings


def test_risk_02_fund_risk_all_vintages(sign_in):
    p = sign_in("Daniel Okafor", "risk", "approver")
    open_tab(p, "Fund risk")
    view = p.inner_text("#view")
    assert "Fund-level risk — all vintages" in view
    for v in range(2030, 2075, 5):
        assert str(v) in view
    for col in ("Total risk", "Effective duration", "Credit spread duration"):
        assert col in view


def test_risk_03_closest_to_budget(sign_in):
    p = sign_in("Daniel Okafor", "risk", "approver")
    open_tab(p, "Risk budget")
    assert "%" in p.inner_text("#view") and "2070" in p.inner_text("#view")


def test_risk_04_custom_stress_scenario(sign_in):
    p = sign_in("Daniel Okafor", "risk", "approver")
    open_tab(p, "Stress tests")
    view = p.inner_text("#view")
    assert "Global financial crisis" in view and "Historical scenarios" in view
    before = p.inner_text("#cusOut")
    for factor, value in (("equity", "-20"), ("rates", "100")):
        sel = f"input[data-drv={factor}]"
        p.eval_on_selector(sel, "(e, v) => { e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); }", value)
    after = p.inner_text("#cusOut")
    assert after != before and "2050" in after


def test_risk_05_lookthrough_search(sign_in):
    p = sign_in("Daniel Okafor", "risk", "approver")
    open_tab(p, "Look-through & search")
    p.fill("#ltq", "Treasury")
    p.dispatch_event("#ltq", "input")
    p.wait_for_timeout(300)
    assert "Treasury" in p.inner_text("#view")


def test_risk_06_co_approve_after_pm(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    open_tab(p, "Proposals")
    p.click("[data-vt='2055']")
    p.check("#ack")
    p.fill("#reason", "PM approval before risk co-approval.")
    p.click("[data-decide=approve]")
    assert "Decision recorded" in toast_text(p)
    p = sign_in("Daniel Okafor", "risk", "approver")
    open_tab(p, "Proposals")
    p.click("[data-vt='2055']")
    p.check("#ack")
    p.fill("#reason", "TE inside budget; stress losses in line with glide path.")
    p.click("[data-decide=approve]")
    assert "Decision recorded" in toast_text(p)


def test_risk_07_segregation_of_duties_one_person_two_roles(sign_in):
    """One person holding PM and Risk can't decide the same vintage in both roles."""
    p = sign_in("Sam Both", "portfolio_manager", "risk", "approver")
    open_tab(p, "Proposals")
    p.click("[data-vt='2060']")
    p.check("#ack")
    p.fill("#reason", "Approving as PM first.")
    p.click("[data-decide=approve]")
    assert "Decision recorded" in toast_text(p)
    p.reload()
    p.wait_for_selector("#nav button")
    switch_workspace(p, "risk")
    open_tab(p, "Proposals")
    p.click("[data-vt='2060']")
    p.check("#ack")
    p.fill("#reason", "Now trying to approve as Risk too.")
    p.click("[data-decide=approve]")
    assert "Segregation of duties" in toast_text(p)
