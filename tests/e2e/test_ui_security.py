"""SEC-1, SEC-2: security log on User access; security headers on every page (NIST SP 800-53, doc 19)."""
from playwright.sync_api import expect


def test_sec_01_security_log(sign_in, app_url):
    """An admin reviews sign-ins and refused requests on User access → Security log (AU-6)."""
    p = sign_in("Priya Raman", "analyst")
    p.goto(app_url + "/admin")                       # refused: analysts don't open User access
    p = sign_in("Sam Patel", "admin", "audit")
    p.goto(app_url + "/admin")
    p.click(".tabs button:text-is('Security log')")
    expect(p.locator("#secTable")).to_contain_text("signin.success")
    expect(p.locator("#secTable")).to_contain_text("Priya Raman")
    p.select_option("#secKind", "access.denied")
    p.click("#secGo")
    expect(p.locator("#secTable")).to_contain_text("access.denied")
    expect(p.locator("#secTable")).not_to_contain_text("signin.success")
    expect(p.locator("#secCsv")).to_have_attribute("href", "/api/admin/security-log?kind=access.denied&email=&days=30&format=csv")
    # users list shows the last sign-in
    p.click(".tabs button:text-is('Users')")
    expect(p.locator("#users th:text-is('Last sign-in')")).to_have_count(1)


def test_sec_02_headers_and_pages_still_work_under_the_csp(sign_in, app_url):
    """The Content Security Policy doesn't break any screen (no console CSP errors)."""
    p = sign_in("Maya Chen", "portfolio_manager", "approver")
    errors = []
    p.on("console", lambda m: errors.append(m.text) if "Content Security Policy" in m.text else None)
    r = p.goto(app_url + "/trading")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    p.wait_for_selector(".tabs button")
    for path in ("/runs/latest", "/simulations", "/policy", "/regulations", "/help"):
        p.goto(app_url + path)
        p.wait_for_load_state("networkidle")
    assert not errors, errors
