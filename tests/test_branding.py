"""Brand themes: every theme is complete and readable; the active theme reaches every page."""
import pytest
from fastapi.testclient import TestClient

from meridian import branding


def test_every_theme_passes_checks():
    assert branding.themes(), "no themes"
    for k, t in branding.themes().items():
        assert branding.check(t) == [], k


def test_check_catches_low_contrast_and_missing_tokens():
    t = {"colors": {"text": "#aaaaaa", "surface": "#ffffff"}}
    probs = branding.check(t)
    assert any("missing" in p for p in probs) and any("text on surface" in p for p in probs)
    assert branding.contrast("#000000", "#ffffff") == pytest.approx(21.0)


def test_switch_theme_with_env(monkeypatch):
    monkeypatch.setenv("MERIDIAN_BRAND", "meridian")
    assert branding.active()["key"] == "meridian" and "#1f4e8c" in branding.theme_css()
    monkeypatch.setenv("MERIDIAN_BRAND", "principal")
    css = branding.theme_css()
    assert "--accent:#002855" in css and "--appbar-bg:#002855" in css and "FS Elliot" in css
    assert "color-scheme:light" in css and "prefers-color-scheme:dark" not in css      # light only
    monkeypatch.setenv("MERIDIAN_BRAND", "no-such-company")
    assert branding.active()["key"] == "meridian"          # unknown theme falls back safely


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_AUTH", "dev")
    monkeypatch.setenv("MERIDIAN_DB_URL", f"sqlite:///{tmp_path}/app.db")
    monkeypatch.setenv("MERIDIAN_BRAND", "principal")
    import meridian.app.main as mm
    mm._store = None
    return TestClient(mm.app)


def test_pages_carry_the_theme_once(client):
    client.post("/dev-login", data={"name": "Maya Chen", "roles": ["portfolio_manager", "admin"]}, follow_redirects=False)
    for path in ("/trading", "/policy", "/regulations", "/admin", "/help"):
        html = client.get(path).text
        assert html.count('id="meridian-brand"') == 1, path
        assert 'data-brand="principal"' in html
    assert client.get("/brand/logo").status_code == 404                  # no logo shipped
    client.cookies.clear()
    assert 'data-brand="principal"' in client.get("/login").text
