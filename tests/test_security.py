"""Security controls (NIST SP 800-53 Rev 5 Moderate, doc 19): headers, inactivity timeout, security event log,
inactive accounts, identity in records and segregation of duties by user ID."""
import time

import pytest

from test_trading import client, login  # noqa: F401  (fixtures)
from meridian.app import auth


def test_security_headers_on_pages_and_api(client):  # noqa: F811
    login(client, "Maya Chen", "portfolio_manager")
    for path in ("/trading", "/api/trading/state", "/login", "/healthz"):
        r = client.get(path)
        h = r.headers
        assert h["x-frame-options"] == "DENY" and h["x-content-type-options"] == "nosniff", path
        csp = h["content-security-policy"]
        assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp and "default-src 'self'" in csp
        assert "permissions-policy" in h and h["cross-origin-opener-policy"] == "same-origin"
    # HSTS only when served over HTTPS
    assert "strict-transport-security" not in client.get("/login").headers


def test_hsts_when_https(client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("APP_BASE_URL", "https://example.cloudfront.net")
    assert client.get("/login").headers["strict-transport-security"].startswith("max-age=31536000")


def test_idle_timeout_and_absolute_limit(client, monkeypatch):  # noqa: F811
    login(client, "Maya Chen", "portfolio_manager", email="maya@example.com")
    raw = client.cookies.get(auth.SESSION_COOKIE)
    u = auth._serializer().loads(raw)
    assert client.get("/api/trading/state").status_code == 200
    # 31 minutes without activity: the session is refused and the event logged
    stale = auth._serializer().dumps({**u, "la": time.time() - 31 * 60})
    client.cookies.set(auth.SESSION_COOKIE, stale)
    assert client.get("/api/trading/state").status_code == 401
    # 29 minutes: still fine, and the response refreshes the last-activity time
    ok = auth._serializer().dumps({**u, "la": time.time() - 29 * 60})
    client.cookies.set(auth.SESSION_COOKIE, ok)
    r = client.get("/api/trading/state")
    assert r.status_code == 200 and auth.SESSION_COOKIE in r.headers.get("set-cookie", "")
    fresh = auth._serializer().loads(r.cookies.get(auth.SESSION_COOKIE) or client.cookies.get(auth.SESSION_COOKIE))
    assert time.time() - fresh["la"] < 5 and fresh["iat"] == u["iat"]          # absolute start never moves
    # background polling doesn't count as activity
    client.cookies.set(auth.SESSION_COOKIE, ok)
    assert auth.SESSION_COOKIE not in client.get("/api/my-work").headers.get("set-cookie", "")
    s = client.get("/api/session").json()
    assert 0 < s["idle_left"] <= 60 and s["idle_limit"] == 30 * 60
    # Stay signed in
    p = client.post("/api/session/ping", headers={"X-CSRF-Token": u["csrf"]})
    assert p.status_code == 200 and time.time() - auth._serializer().loads(p.cookies.get(auth.SESSION_COOKIE))["la"] < 5
    h = login(client, "Ana Admin", "admin")
    kinds = [e["kind"] for e in client.get("/api/admin/security-log", headers=h).json()["events"]]
    assert "session.idle" in kinds and "signin.success" in kinds
    idle = next(e for e in client.get("/api/admin/security-log", headers=h).json()["events"] if e["kind"] == "session.idle")
    assert idle["email"] == "maya@example.com"


def test_security_log_records_denials_and_is_restricted(client):  # noqa: F811
    login(client, "Priya Raman", "analyst", email="priya@example.com")
    assert client.get("/api/admin/users").status_code == 403                      # refused request
    assert client.post("/api/trading/cashflows", json={}, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert client.post("/api/ingest/prices", json={}, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/admin/security-log").status_code == 403               # analysts can't read it
    h = login(client, "Grace Liu", "audit")
    d = client.get("/api/admin/security-log", headers=h).json()
    kinds = {e["kind"] for e in d["events"]}
    assert {"signin.success", "access.denied", "csrf.failure", "token.invalid"} <= kinds
    denied = next(e for e in d["events"] if e["kind"] == "access.denied" and e["path"] == "/api/admin/users")
    assert denied["email"] == "priya@example.com" and denied["path"] == "/api/admin/users" and denied["method"] == "GET"
    only = client.get("/api/admin/security-log?kind=csrf", headers=h).json()["events"]
    assert only and all(e["kind"].startswith("csrf") for e in only)
    csv = client.get("/api/admin/security-log?format=csv", headers=h)
    assert csv.status_code == 200 and csv.text.startswith("at,kind,outcome,email")


def test_security_log_is_append_only(client):  # noqa: F811
    login(client, "Maya Chen", "portfolio_manager")
    import meridian.app.main as mm
    from sqlalchemy import text
    with pytest.raises(Exception):
        with mm.store().engine.begin() as c:
            c.execute(text("UPDATE security_events SET kind='x'"))
    with pytest.raises(Exception):
        with mm.store().engine.begin() as c:
            c.execute(text("DELETE FROM security_events"))


def test_users_show_last_signin_and_inactive_flag(client):  # noqa: F811
    login(client, "Maya Chen", "portfolio_manager", email="maya@example.com")
    h = login(client, "Sam Patel", "admin", email="sam@example.com")
    users = {u["email"]: u for u in client.get("/api/admin/users", headers=h).json()["users"]}
    for u in users.values():
        assert "last_signin" in u and "inactive" in u


def test_same_person_prefers_the_user_id():
    u = {"sub": "abc-123", "email": "maya@example.com", "name": "Maya Chen"}
    assert auth.same_person({"id": "abc-123", "name": "Someone else"}, u)
    assert not auth.same_person({"id": "zzz", "name": "Maya Chen", "email": "maya@example.com"}, u)   # id wins
    assert auth.same_person({"email": "MAYA@example.com"}, u)                                          # older records
    assert auth.same_person({"name": "Maya Chen"}, u)
    assert not auth.same_person({"name": "Maya Chen"}, {"sub": "x", "name": "Other"})
    assert auth.who(u) == {"id": "abc-123", "name": "Maya Chen", "email": "maya@example.com"}


def test_records_carry_the_user_id(client):  # noqa: F811
    h = login(client, "Maya Chen", "portfolio_manager", email="maya@example.com")
    r = client.put("/api/trading/fund-styles", json={"funds": {"MTRS-2040": "active"}, "reason": "Security test reason"}, headers=h)
    assert r.status_code == 200
    import meridian.app.main as mm
    rec = [x for x in mm.store().ledger("governance") if x["step"] == "settings.change"][-1]
    assert rec["actor"]["user_id"] == "dev-Maya Chen" and rec["actor"]["id"] == "Maya Chen"
    assert rec["actor"]["email"] == "maya@example.com"


def test_settings_entries_cannot_claim_another_author(client):  # noqa: F811
    """A browser can't attribute a tilt or exit to someone else: authors are stamped by the server (AU-10)."""
    h = login(client, "Maya Chen", "portfolio_manager", email="maya@example.com")
    forged = {"name": "Robert Hayes", "email": "cco@example.com"}
    body = {"tilts": [{"instrument": "VNQ", "fund": "MTRS-2040", "bps": 25, "by": forged, "at": "2020-01-01"}],
            "reason": "Security test for authorship"}
    assert client.put("/api/trading/settings", json=body, headers=h).status_code == 200
    t = client.get("/api/trading/state", headers=h).json()["settings"]["tilts"][0]
    assert t["by"]["email"] == "maya@example.com" and not t["at"].startswith("2020")
    # saving the same entry again keeps its original author and time
    h2 = login(client, "Jordan Ellis", "portfolio_manager", email="jordan@example.com")
    st = client.get("/api/trading/state", headers=h2).json()["settings"]
    r = client.put("/api/trading/settings", json={"tilts": st["tilts"], "buffer_bps": 40, "reason": "Change buffer only"}, headers=h2)
    assert r.status_code == 200
    t2 = client.get("/api/trading/state", headers=h2).json()["settings"]["tilts"][0]
    assert t2["by"]["email"] == "maya@example.com" and t2["at"] == t["at"]
