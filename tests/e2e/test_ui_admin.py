"""UAT-ADM: User access screen (persona: Sam Patel, platform admin). See docs UAT scripts, section ADM."""


def expect_toast(p, text: str):
    p.wait_for_function("t => document.querySelector('#toast').innerText.includes(t)", arg=text, timeout=15000)

R = "UAT: new committee member per IC minute 2026-11"


def _seed_admin():
    from meridian.app.main import store
    from meridian.app.store import DevUser
    with store().Session.begin() as s:
        if not s.get(DevUser, "sam.patel@example.com"):
            s.add(DevUser(email="sam.patel@example.com", name="Sam Patel", roles=["admin"]))


def _toggle(p, perm):
    """Click the visible switch, as a person would."""
    p.click(f"#panel label.opt:has(input[value={perm}]) .switch span")


def _admin(page, app_url):
    _seed_admin()
    page.context.clear_cookies()
    page.goto(app_url + "/login")
    page.fill("input[name=name]", "Sam Patel")
    page.fill("input[name=email]", "sam.patel@example.com")
    page.check("input[name=roles][value=admin]")
    page.click("button[type=submit]")
    page.wait_for_url("**/admin")
    page.wait_for_selector("#users table")
    return page


def test_adm_10_admin_lands_on_user_access(page, app_url):
    p = _admin(page, app_url)
    assert "Sam Patel" in p.inner_text("#users") and "Add user" in p.inner_text("#users")


def test_adm_11_add_user_toggle_permission_and_see_log(page, app_url):
    p = _admin(page, app_url)
    p.click("#add")
    p.fill("#fEmail", "thomas.greene@example.com")
    p.fill("#fName", "Thomas Greene")
    _toggle(p, "investment_committee")
    p.wait_for_function("document.querySelector('#warns').innerText.includes('without the Leadership workspace')")
    p.check("#panel input[name=ws][value=leadership]")
    p.wait_for_function("!document.querySelector('#warns').innerText.includes('Leadership workspace')")
    p.fill("#fReason", R)
    p.click("#save")
    expect_toast(p, "Invited thomas.greene@example.com")
    row = p.locator("#users tbody tr", has_text="thomas.greene@example.com")
    assert "Investment Committee member" in row.inner_text() and "Invited" in row.inner_text()

    # switch the permission off again
    row.locator("button", has_text="Edit").click()
    _toggle(p, "investment_committee")
    p.fill("#fReason", "UAT: stepped down from the committee")
    p.click("#save")
    expect_toast(p, "signed out")
    assert "Investment Committee" not in p.locator("#users tbody tr", has_text="thomas.greene@example.com").inner_text()

    p.click(".tabs button[data-tab=log]")
    p.wait_for_selector("#log table")
    log = p.inner_text("#log")
    assert "set_access" in log and "create" in log and "stepped down" in log


def test_adm_12_reason_required_and_self_lockout(page, app_url):
    p = _admin(page, app_url)
    p.locator("#users tbody tr", has_text="sam.patel@example.com").locator("button", has_text="Edit").click()
    assert p.query_selector("#disable") is None                     # can't disable yourself
    p.uncheck("#panel input[name=ws][value=admin]")
    p.fill("#fReason", "UAT: trying to remove my own admin")
    p.click("#save")
    expect_toast(p, "can't remove your own admin role")
    p.check("#panel input[name=ws][value=admin]")
    p.fill("#fReason", "short")
    p.fill("#fName", "Sam R. Patel")
    p.click("#save")
    expect_toast(p, "at least 10 characters")


def test_adm_13_access_review_matrix(page, app_url):
    p = _admin(page, app_url)
    p.click(".tabs button[data-tab=review]")
    assert "Access review" in p.inner_text("#review") and "●" in p.inner_text("#review")
    with p.expect_download() as d:
        p.click("#csv")
    assert d.value.suggested_filename.startswith("meridian-access-review-")


def test_adm_14_audit_sees_read_only_screen(sign_in, app_url):
    p = sign_in("Grace Liu", "audit")
    assert "User access" in p.inner_text("#roleHelp")
    p.goto(app_url + "/admin")
    p.wait_for_selector("#users table")
    assert "Read-only" in p.inner_text("#users") and p.query_selector("#add") is None
    assert p.query_selector("[data-edit]") is None


def test_adm_15_pm_cannot_open_user_access(sign_in, app_url):
    p = sign_in("Maya Chen", "portfolio_manager")
    assert "User access" not in p.inner_text("#roleHelp")
    r = p.request.get(app_url + "/admin")
    assert r.status == 403
