"""UAT for the shared oversight features: "Why?" panels, changes since last run, exceptions, ledger search,
evidence download, and the fixes from UAT round 1. See docs UAT scripts, section OVS."""
import datetime as dt

from conftest import open_tab, switch_workspace, tabs


def expect_toast(p, text):
    p.wait_for_function("t => document.querySelector('#toast').innerText.includes(t)", arg=text, timeout=15000)


def test_ovs_01_why_panel_on_a_proposal(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager")
    open_tab(p, "Portfolios & proposals")
    p.click("[data-vt='2050']")
    p.click("button[data-why=proposal]")
    box = p.inner_text("#whyModal")
    assert "Why this proposal for 2050?" in box and "cio.ensemble" in box and "cro.risk-report" in box
    assert "Inputs shared by the whole run" in box
    p.keyboard.press("Escape")
    assert not p.is_visible("#whyModal")


def test_ovs_02_why_from_compliance_opens_ledger_record(sign_in):
    p = sign_in("Robert Hayes", "compliance", "chief_compliance_officer")
    open_tab(p, "Compliance")
    p.click("button[data-why=compliance][data-wv='2040']")
    assert "Compliance for 2040" in p.inner_text("#whyModal")
    p.locator("#whyModal [data-why-open]").first.click()
    p.wait_for_selector("#nav button.active:text-is('Decision ledger')")
    assert "Prev hash" in p.inner_text("#view")


def test_ovs_03_why_on_a_capital_market_assumption(sign_in):
    p = sign_in("Priya Raman", "analyst")
    open_tab(p, "Capital market assumptions")
    p.click("[data-cma='us_large_cap']")
    p.click("#cmaWhy button[data-why=cma]")
    assert "ac-us_large_cap.cma-judge" in p.inner_text("#whyModal")


def test_ovs_04_changes_since_last_run(sign_in):
    p = sign_in("Elena Rossi", "leadership")
    open_tab(p, "Changes since last run")
    v = p.inner_text("#view")
    assert "as of 2026-09-30" in v and "Macro regime" in v and "Largest weight moves" in v
    assert "Capital market assumptions that moved most" in v


def test_ovs_05_exception_lifecycle_with_separation_of_duties(sign_in):
    due = (dt.date.today() + dt.timedelta(days=10)).isoformat()
    p = sign_in("Nina Alvarez", "compliance")
    open_tab(p, "Exceptions")
    p.click("#excNew")
    p.fill("#enTitle", "UAT: EM debt above sleeve guideline")
    p.select_option("#enV", "2045")
    p.fill("#enOwner", "Maya Chen")
    p.fill("#enDue", due)
    p.fill("#enWhy", "UAT: found in manual guideline review")
    p.click("#enGo")
    expect_toast(p, "raised and recorded in the ledger")
    p.wait_for_selector("#nav button.active:text-is('Exceptions')")
    row = p.locator("#view tr[data-exc]", has_text="EM debt above sleeve guideline")
    assert "Maya Chen" in row.inner_text()

    # the owner (a PM) remediates
    p = sign_in("Maya Chen", "portfolio_manager")
    open_tab(p, "Exceptions")
    p.locator("#view tr[data-exc]", has_text="EM debt above sleeve guideline").click()
    p.fill("#excNote", "UAT: trimmed EM debt back inside the guideline")
    p.click("[data-excact=remediate]")
    expect_toast(p, "status remediated")

    # risk can't close; compliance (a different person from the opener) can
    p = sign_in("Daniel Okafor", "risk")
    open_tab(p, "Exceptions")
    p.select_option("#excF", "remediated")
    p.locator("#view tr[data-exc]", has_text="EM debt above sleeve guideline").click()
    assert p.query_selector("[data-excact=close]") is None
    p = sign_in("Robert Hayes", "compliance", "chief_compliance_officer")
    open_tab(p, "Exceptions")
    p.select_option("#excF", "remediated")
    p.locator("#view tr[data-exc]", has_text="EM debt above sleeve guideline").click()
    p.fill("#excNote", "UAT: verified the trade and the new weight")
    p.click("[data-excact=close]")
    expect_toast(p, "status closed")


def test_ovs_06_only_cco_accepts_and_acceptance_expires(sign_in, app_url):
    p = sign_in("Daniel Okafor", "risk")
    csrf = p.evaluate("LIVE.csrf")
    c = p.request.post(app_url + "/api/exceptions", headers={"X-CSRF-Token": csrf},
                       data={"title": "UAT: TE close to budget on 2070", "severity": "warn", "vintage": 2070,
                             "reason": "UAT: flagged in daily risk review"}).json()
    act = lambda pg, tok, body: pg.request.post(f"{app_url}/api/exceptions/{c['id']}/actions",
                                                headers={"X-CSRF-Token": tok}, data=body)
    until = (dt.date.today() + dt.timedelta(days=90)).isoformat()
    assert act(p, csrf, {"action": "accept", "until": until, "reason": "UAT: risk tries to accept"}).status == 403
    p = sign_in("Robert Hayes", "compliance", "chief_compliance_officer")
    tok = p.evaluate("LIVE.csrf")
    too_long = (dt.date.today() + dt.timedelta(days=400)).isoformat()
    assert act(p, tok, {"action": "accept", "until": too_long, "reason": "UAT: CCO accepts too long"}).status == 400
    r = act(p, tok, {"action": "accept", "until": until, "reason": "UAT: CCO accepts for one quarter"})
    assert r.status == 200 and r.json()["status"] == "accepted" and r.json()["accepted_until"] == until
    p.reload()
    p.wait_for_selector("#nav button")
    open_tab(p, "Decision ledger")
    p.click("#lsBox summary")
    p.select_option("#lsT", "exception")
    p.click("#lsGo")
    p.wait_for_selector("#lsOut table")
    out = p.inner_text("#lsOut")
    assert "exception.open" in out and "exception.accept" in out and "governance" in out


def test_ovs_07_ledger_search_csv_and_evidence(sign_in, app_url):
    p = sign_in("Grace Liu", "audit")
    open_tab(p, "Decision ledger")
    assert p.locator("a", has_text="Download evidence pack").count() == 1
    p.click("#lsBox summary")
    p.fill("#lsQ", "proposal awaiting")
    p.click("#lsGo")
    p.wait_for_selector("#lsOut table")
    assert "approval.pending" in p.inner_text("#lsOut")
    href = p.get_attribute("#lsCsv a", "href")
    r = p.request.get(app_url + href)
    assert r.status == 200 and r.text().startswith("run_id,") and "approval.pending" in r.text()
    p2 = sign_in("Maya Chen", "portfolio_manager")
    assert p2.request.get(app_url + "/api/ledger/search?q=x").status == 403


def test_ovs_08_round1_fixes(sign_in):
    p = sign_in("Elena Rossi", "leadership", "manager_selection", "compliance")
    assert "Leadership" in [o.inner_text() for o in p.query_selector_all("#role option")]
    switch_workspace(p, "mgr")
    open_tab(p, "Underlying funds")
    v = p.inner_text("#view")
    assert "Returns proxy" in v and "Holdings proxy" in v and "IVV" in v
    switch_workspace(p, "compliance")
    open_tab(p, "Compliance report")
    assert "record counts here can be lower" in p.inner_text("#view")
    open_tab(p, "Decision ledger")
    assert "verified verified" not in p.inner_text("#view")


def test_ovs_09_tabs_per_role(sign_in):
    p = sign_in("Maya Chen", "portfolio_manager")
    assert "Changes since last run" in tabs(p) and "Exceptions" in tabs(p)
    p = sign_in("Grace Liu", "audit")
    assert "Exceptions" in tabs(p)
