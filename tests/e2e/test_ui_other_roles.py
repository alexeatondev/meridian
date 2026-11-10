"""UAT for Research, Manager Selection, Leadership, Compliance, Audit and Admin, plus access checks.
Personas: Priya Raman, Marcus Webb, Elena Rossi, Robert Hayes, Grace Liu, Sam Patel. See docs UAT scripts."""
import pytest

from conftest import open_tab, tabs


# ---------------------------------------------------------------- Research
def test_res_01_workspace(sign_in):
    p = sign_in("Priya Raman", "analyst")
    assert tabs(p) == ["Home", "Positioning", "Metrics", "Factor risk", "Look-through & search",
                       "Capital market assumptions", "Agent votes", "Glide path"]


def test_res_02_cma_judge_reasoning(sign_in):
    p = sign_in("Priya Raman", "analyst")
    open_tab(p, "Capital market assumptions")
    assert "Judge − blend" in p.inner_text("#view")
    p.click("[data-cma='us_large_cap']")
    why = p.inner_text("#cmaWhy")
    assert "judge reasoning" in why and "Method weights" in why


def test_res_03_agent_votes(sign_in):
    p = sign_in("Priya Raman", "analyst")
    open_tab(p, "Agent votes")
    assert len(p.inner_text("#view")) > 200


# ---------------------------------------------------------------- Manager selection
def test_mgr_01_workspace(sign_in):
    p = sign_in("Marcus Webb", "manager_selection")
    assert tabs(p) == ["Home", "Funds & vintages", "Underlying funds", "Look-through & search", "Positioning"]


def test_mgr_02_issuer_search_and_fund_drilldown(sign_in):
    p = sign_in("Marcus Webb", "manager_selection")
    open_tab(p, "Look-through & search")
    view = p.inner_text("#view")
    assert "securities/issuers across 13 building blocks" in view and "holdings as of" in view
    p.fill("#ltq", "Apple")
    p.dispatch_event("#ltq", "input")
    p.wait_for_timeout(300)
    assert "Apple" in p.inner_text("#view") or "APPLE" in p.inner_text("#view")


def test_mgr_03_underlying_funds(sign_in):
    p = sign_in("Marcus Webb", "manager_selection")
    open_tab(p, "Underlying funds")
    assert len(p.inner_text("#view")) > 200


# ---------------------------------------------------------------- Leadership / IC
def test_lead_01_workspace(sign_in):
    p = sign_in("Elena Rossi", "leadership")
    assert tabs(p) == ["Home", "Funds & vintages", "Board memo", "Fund risk", "Stress tests", "Risk budget",
                       "Metrics", "Glide path", "Approvals"]


def test_lead_02_board_memo(sign_in):
    p = sign_in("Elena Rossi", "leadership")
    open_tab(p, "Board memo")
    memo = p.inner_text("#view")
    assert "Board Memo" in memo and "Compliance review" in memo and "SYNTHETIC" in memo


def test_lead_03_stress_losses(sign_in):
    p = sign_in("Elena Rossi", "leadership")
    open_tab(p, "Stress tests")
    assert "Global financial crisis" in p.inner_text("#view")


# ---------------------------------------------------------------- Compliance
def test_comp_01_workspace(sign_in):
    p = sign_in("Robert Hayes", "compliance")
    assert tabs(p) == ["Home", "Compliance", "Risk budget", "Look-through & search", "Compliance report",
                       "Decision ledger"]


def test_comp_02_rule_results(sign_in):
    p = sign_in("Robert Hayes", "compliance")
    open_tab(p, "Compliance")
    view = p.inner_text("#view")
    assert "Deterministic rule engine" in view and "POL-SUM" in view


def test_comp_03_aco_report_is_draft(sign_in):
    p = sign_in("Robert Hayes", "compliance")
    open_tab(p, "Compliance report")
    view = p.inner_text("#view")
    assert "DRAFT" in view and "Not an attestation" in view and "Record retention applied" in view


def test_comp_04_trace_an_approval_in_the_ledger(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager")
    open_tab(p, "Portfolios & proposals")
    p.click("[data-vt='2035']")
    p.check("#ack")
    p.fill("#reason", "Approval for the compliance trace test.")
    p.click("[data-decide=approve]")
    p.wait_for_selector("#toast", state="visible")
    p = sign_in("Robert Hayes", "compliance")
    open_tab(p, "Decision ledger")
    p.fill("#lf", "approval")
    p.wait_for_timeout(300)
    assert "approval.decision" in p.inner_text("#view")


# ---------------------------------------------------------------- Audit
def test_audit_01_read_only_workspace(sign_in):
    p = sign_in("Grace Liu", "audit")
    assert tabs(p) == ["Home", "Decision ledger", "Compliance", "Compliance report"]
    assert p.query_selector("[data-decide]") is None


def test_audit_02_ledger_verifies(sign_in):
    p = sign_in("Grace Liu", "audit")
    assert "✓ verified" in p.inner_text("#sidefoot")
    open_tab(p, "Decision ledger")
    assert "Hash-chained" in p.inner_text("#view")


def test_audit_03_evidence_export(sign_in, app_url):
    p = sign_in("Grace Liu", "audit")
    rid = p.input_value("#runSel")
    r = p.request.get(f"{app_url}/api/runs/{rid}/evidence")
    assert r.status == 200 and r.json()["integrity"]["ok"]


def test_audit_04_pm_cannot_export_evidence(sign_in, app_url):
    p = sign_in("Maya Chen", "portfolio_manager")
    rid = p.input_value("#runSel")
    assert p.request.get(f"{app_url}/api/runs/{rid}/evidence").status == 403


# ---------------------------------------------------------------- Admin and access
def test_admin_01_sees_audit_view_only(sign_in):
    p = sign_in("Sam Patel", "admin")
    assert [o.get_attribute("value") for o in p.query_selector_all("#role option")] == ["audit"]


def test_access_01_signed_out_goes_to_sign_in(page, app_url):
    page.context.clear_cookies()
    page.goto(app_url + "/runs/latest")
    assert "/login" in page.url


def test_access_02_user_without_role(page, app_url):
    page.context.clear_cookies()
    page.goto(app_url + "/login")
    page.fill("input[name=name]", "No Role")
    page.click("button[type=submit]")
    assert "no Meridian role" in page.inner_text("body")


def test_access_03_cannot_open_another_roles_workspace_by_url(sign_in, app_url):
    p = sign_in("Grace Liu", "audit")
    p.goto(app_url + "/runs/latest#pm")
    p.wait_for_selector("#nav button")
    assert [o.get_attribute("value") for o in p.query_selector_all("#role option")] == ["audit"]
    assert "Positioning" not in tabs(p)


# ---------------------------------------------------------------- Known defect (UAT finding F-1)
@pytest.mark.xfail(strict=True, reason="F-1: Leadership/Compliance approve as investment_committee / "
                                       "chief_compliance_officer, which no sign-in group grants")
def test_finding_f1_leadership_can_record_committee_decision(sign_in, app_url):
    p = sign_in("Elena Rossi", "leadership")
    rid = p.input_value("#runSel")
    csrf = p.evaluate("LIVE.csrf")
    r = p.request.post(f"{app_url}/api/runs/{rid}/approvals", headers={"X-CSRF-Token": csrf},
                       data={"vintage": 2030, "role": "investment_committee", "decision": "approve",
                             "reason": "Committee decision on the glide path."})
    assert r.status != 403
