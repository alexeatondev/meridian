"""Sign-in pages carry the brand: the app's own sign-in, signed-out and no-role pages, and the CSS applied to
the Amazon Cognito sign-in pages (hosted UI, classic) by the CDK stack."""
import re

from test_app import client  # noqa: F401  (fixture)

from meridian import branding

ALLOWED = {"background-customizable", "banner-customizable", "errorMessage-customizable", "idpButton-customizable",
           "idpButton-customizable:hover", "idpDescription-customizable", "inputField-customizable",
           "inputField-customizable:focus", "label-customizable", "legalText-customizable", "logo-customizable",
           "passwordCheck-valid-customizable", "passwordCheck-notValid-customizable", "redirect-customizable",
           "socialButton-customizable", "submitButton-customizable", "submitButton-customizable:hover",
           "textDescription-customizable"}


def test_cognito_css_for_every_theme_fits_cognitos_rules():
    for key, t in branding.themes().items():
        css = branding.cognito_css(dict(t, key=key))
        assert len(css.encode()) <= 3000, key
        sels = set(re.findall(r"^\.(\S+) \{", css, re.M))
        assert sels and sels <= ALLOWED, (key, sels - ALLOWED)
        assert not re.search(r"@import|@media|@supports|@page|javascript", css, re.I)
    p = branding.cognito_css(dict(branding.themes()["principal"], key="principal"))
    assert ".banner-customizable { padding: 22px 0px 22px 0px; background-color: #002855; }" in p
    assert ".submitButton-customizable {" in p and "background-color: #002855" in p


def test_app_signin_pages_are_branded(client, monkeypatch):  # noqa: F811
    r = client.get("/login")                                  # dev sign-in
    assert r.status_code == 200 and 'class="pbar"' in r.text and 'id="meridian-brand"' in r.text and "Sign in to Meridian" in r.text
    monkeypatch.setenv("MERIDIAN_AUTH", "cognito")
    from meridian.app import auth
    monkeypatch.setattr(auth, "login_url", lambda state: "https://example.auth/oauth2/authorize?state=" + state)
    r = client.get("/login", follow_redirects=False)          # hosted: a branded page first, then Cognito
    assert r.status_code == 200 and 'id="signin"' in r.text and 'href="/login?go=1"' in r.text and 'class="pbar"' in r.text
    r = client.get("/login?go=1", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"].startswith("https://example.auth/")
    r = client.get("/signed-out")
    assert 'class="pbar"' in r.text and "signed out" in r.text
