"""User access screen: API rules, access log, session revocation, and the Cognito adapter (with a fake client)."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_AUTH", "dev")
    monkeypatch.setenv("MERIDIAN_DB_URL", f"sqlite:///{tmp_path}/app.db")
    import meridian.app.main as m
    m._store = None
    return TestClient(m.app)


def login(c, name, *roles, email=""):
    c.cookies.clear()
    r = c.post("/dev-login", data={"name": name, "email": email, "roles": list(roles)}, follow_redirects=False)
    assert r.status_code == 303
    from meridian.app import auth
    return {"X-CSRF-Token": auth._serializer().loads(c.cookies.get(auth.SESSION_COOKIE))["csrf"]}


R = "UAT: onboarding per access request #1"


def seed_admin(c):
    """The first admin in the local directory (as an admin would be created through Cognito on AWS)."""
    from meridian.app.main import store
    from meridian.app.store import DevUser
    with store().Session.begin() as s:
        s.add(DevUser(email="sam@example.com", name="Sam Patel", roles=["admin"]))
    return login(c, "Sam Patel", "admin", email="sam@example.com")


def test_only_admins_can_change_access(client):
    h = login(client, "Maya Chen", "portfolio_manager", "approver")
    assert client.get("/api/admin/users").status_code == 403
    assert client.post("/api/admin/users", json={}, headers=h).status_code == 403
    h = login(client, "Grace Liu", "audit")
    assert client.get("/api/admin/users").status_code == 200           # read-only access review
    assert client.post("/api/admin/users", json={"email": "x@example.com"}, headers=h).status_code == 403
    assert client.get("/admin").status_code == 200


def test_create_edit_disable_delete_with_access_log(client):
    h = seed_admin(client)
    new = {"email": "Elena.Rossi@Example.com", "name": "Elena Rossi", "roles": ["leadership"], "reason": R}
    assert client.post("/api/admin/users", json=new | {"reason": "short"}, headers=h).status_code == 400
    assert client.post("/api/admin/users", json=new | {"roles": ["investment_committee"]}, headers=h).status_code == 400
    assert client.post("/api/admin/users", json=new | {"roles": ["superuser"]}, headers=h).status_code == 400
    assert client.post("/api/admin/users", json=new, headers=h).status_code == 200
    assert client.post("/api/admin/users", json=new, headers=h).status_code == 409        # duplicate
    users = {u["email"]: u for u in client.get("/api/admin/users").json()["users"]}
    assert users["elena.rossi@example.com"]["roles"] == ["leadership"]

    # switch the Investment Committee permission on, then rename
    r = client.put("/api/admin/users/elena.rossi@example.com", json={"roles": ["leadership", "investment_committee"],
                                                                     "name": "Elena M. Rossi", "reason": R}, headers=h)
    assert r.status_code == 200 and "signed out" in r.json()["message"]
    u = {u["email"]: u for u in client.get("/api/admin/users").json()["users"]}["elena.rossi@example.com"]
    assert u["roles"] == ["leadership", "investment_committee"] and u["name"] == "Elena M. Rossi"

    # delete only after disable, with the email typed back
    assert client.request("DELETE", "/api/admin/users/elena.rossi@example.com", json={"reason": R, "confirm": "elena.rossi@example.com"},
                          headers=h).status_code == 400
    assert client.post("/api/admin/users/elena.rossi@example.com/disable", json={"reason": R}, headers=h).status_code == 200
    assert client.request("DELETE", "/api/admin/users/elena.rossi@example.com", json={"reason": R, "confirm": "nope"},
                          headers=h).status_code == 400
    assert client.request("DELETE", "/api/admin/users/elena.rossi@example.com", json={"reason": R, "confirm": "elena.rossi@example.com"},
                          headers=h).status_code == 200

    log = client.get("/api/admin/access-log").json()["events"]
    assert [e["action"] for e in log][::-1] == ["create", "rename", "set_access", "disable", "delete"]
    assert all(e["actor"]["name"] == "Sam Patel" and e["reason"] == R for e in log)
    assert log[2]["before"] == {"roles": ["leadership"]} and log[2]["after"]["roles"][-1] == "investment_committee"


def test_access_log_is_append_only(client):
    seed_admin(client)
    from sqlalchemy import text
    from sqlalchemy.exc import DatabaseError

    from meridian.app.main import store
    store().log_access({"name": "x"}, "create", "a@example.com", None, None, R)
    with pytest.raises(DatabaseError, match="append-only"):
        with store().engine.begin() as c:
            c.execute(text("DELETE FROM access_events"))


def test_admin_lockout_guards(client):
    h = seed_admin(client)
    me = "sam@example.com"
    assert client.put(f"/api/admin/users/{me}", json={"roles": ["audit"], "reason": R}, headers=h).status_code == 400
    assert client.post(f"/api/admin/users/{me}/disable", json={"reason": R}, headers=h).status_code == 400
    client.post("/api/admin/users", json={"email": "jo@example.com", "name": "Jo", "roles": ["admin"], "reason": R}, headers=h)
    # a second admin may remove the first admin's role, but not the last one standing
    h2 = login(client, "Jo", "admin", email="jo@example.com")
    assert client.put(f"/api/admin/users/{me}", json={"roles": ["audit"], "reason": R}, headers=h2).status_code == 200
    assert client.post("/api/admin/users/jo@example.com/disable", json={"reason": R}, headers=h2).status_code == 400


def test_access_change_signs_the_person_out(client):
    h = seed_admin(client)
    client.post("/api/admin/users", json={"email": "maya@example.com", "name": "Maya Chen", "roles": ["portfolio_manager"],
                                          "reason": R}, headers=h)
    maya = TestClient(client.app)
    login(maya, "Maya Chen", "portfolio_manager", email="maya@example.com")
    assert maya.get("/api/me").status_code == 200
    client.put("/api/admin/users/maya@example.com", json={"roles": ["analyst"], "reason": R}, headers=h)
    assert maya.get("/api/me").status_code == 401                       # old session no longer accepted
    login(maya, "Maya Chen", "analyst", email="maya@example.com")
    assert maya.get("/api/me").status_code == 200                       # a new sign-in works


def test_separation_of_duties_warnings(client):
    h = seed_admin(client)
    w = client.post("/api/admin/check", json={"roles": ["portfolio_manager", "investment_committee"]}, headers=h).json()["warnings"]
    assert any("Separation of duties" in x for x in w) and any("without the Leadership workspace" in x for x in w)
    client.post("/api/admin/users", json={"email": "rh@example.com", "name": "Robert Hayes",
                                          "roles": ["compliance", "chief_compliance_officer"], "reason": R}, headers=h)
    w = client.post("/api/admin/check", json={"roles": ["compliance", "chief_compliance_officer"], "email": "x@example.com"},
                    headers=h).json()["warnings"]
    assert any("already holds the CCO permission (Robert Hayes)" in x for x in w)


# ---------------------------------------------------------------- Cognito adapter, with a fake client
class FakeCognito:
    class exceptions:
        class ResourceNotFoundException(Exception):
            pass

    def __init__(self):
        self.users = {"u1": {"Username": "u1", "Enabled": True, "UserStatus": "CONFIRMED", "UserCreateDate": dt.datetime(2026, 11, 9),
                             "Attributes": [{"Name": "email", "Value": "a@example.com"}, {"Name": "name", "Value": "Alex"}]}}
        self.groups = {"u1": {"leadership", "portfolio_manager"}}
        self.calls = []

    def list_users(self, UserPoolId, Limit=60, PaginationToken=None, Filter=None):
        us = list(self.users.values())
        if Filter:
            want = Filter.split('"')[1]
            us = [u for u in us if any(a["Value"] == want for a in u["Attributes"])]
        return {"Users": us}

    def list_users_in_group(self, UserPoolId, GroupName, Limit=60, NextToken=None):
        return {"Users": [self.users[k] for k, g in self.groups.items() if GroupName in g]}

    def admin_list_groups_for_user(self, UserPoolId, Username):
        return {"Groups": [{"GroupName": g} for g in sorted(self.groups[Username])]}

    def admin_add_user_to_group(self, UserPoolId, Username, GroupName):
        self.calls.append(("add", GroupName)); self.groups[Username].add(GroupName)

    def admin_remove_user_from_group(self, UserPoolId, Username, GroupName):
        self.calls.append(("remove", GroupName)); self.groups[Username].discard(GroupName)


def test_cognito_adapter_lists_and_changes_only_the_difference():
    from meridian.app.directory import CognitoDirectory
    d = CognitoDirectory.__new__(CognitoDirectory)
    d.pool, d.c = "pool", FakeCognito()
    users = d.list_users()
    assert users[0]["email"] == "a@example.com" and sorted(users[0]["roles"]) == ["leadership", "portfolio_manager"]
    d.set_roles("a@example.com", ["leadership", "investment_committee"])
    assert sorted(d.c.calls) == [("add", "investment_committee"), ("remove", "portfolio_manager")]
    assert sorted(d.get("a@example.com")["roles"]) == ["investment_committee", "leadership"]


def test_approver_permission_is_switched_on_and_off_and_logged(client):
    """Approver is a permission like the others: granted and removed in User access, each change in the access log."""
    h = seed_admin(client)
    assert client.post("/api/admin/users", json={"email": "maya@example.com", "name": "Maya Chen",
                       "roles": ["portfolio_manager"], "reason": R}, headers=h).status_code == 200
    w = client.post("/api/admin/check", json={"roles": ["portfolio_manager"]}, headers=h).json()["warnings"]
    assert any("No Approver permission" in x for x in w)
    w = client.post("/api/admin/check", json={"roles": ["analyst", "approver"]}, headers=h).json()["warnings"]
    assert any("Approver permission without" in x for x in w)
    for roles, reason in ((["portfolio_manager", "approver"], "UAT: grant Approver to Maya per IC minute 12"),
                          (["portfolio_manager"], "UAT: remove Approver from Maya, moved to a review-only seat")):
        assert client.put("/api/admin/users/maya@example.com", json={"roles": roles, "reason": reason},
                          headers=h).status_code == 200
    ev = [e for e in client.get("/api/admin/access-log").json()["events"] if e["action"] == "set_access"][:2]
    removed, granted = ev                                      # newest first
    assert "approver" in granted["after"]["roles"] and "approver" not in granted["before"]["roles"]
    assert "approver" in removed["before"]["roles"] and "approver" not in removed["after"]["roles"]
    assert granted["actor"] and "IC minute 12" in granted["reason"]
    review = client.get("/api/admin/users").json()
    assert "approver" in review["permissions"]
