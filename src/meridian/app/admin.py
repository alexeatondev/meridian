"""User access & administration: API and screen (admins only).

Rules enforced here, whatever the client sends:
- Every change needs a reason (≥ 10 characters) and is written to the append-only access log.
- An admin can't remove their own admin role, disable or delete themselves; at least one enabled admin remains.
- Accounts are deleted only after being disabled, and only with the email typed back as confirmation.
- Any change to a person's roles, permissions or status signs them out of Meridian immediately.
- Separation-of-duties conflicts are returned as warnings (shown before saving), not silently allowed.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import auth
from .directory import _norm_roles, directory

router = APIRouter()
EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
WORKSPACES = [r for r in auth.ROLES if r not in auth.PERMISSIONS]
PROPOSERS = {"portfolio_manager", "analyst"}


def _store():
    from .main import store
    return store()


def _admin(request: Request, write: bool = False) -> dict:
    user = auth.require_user(request)
    auth.require_role(user, "admin")
    if write:
        auth.check_csrf(request, user)
    return user


def _reason(body: dict) -> str:
    r = str(body.get("reason", "")).strip()
    if len(r) < 10:
        raise HTTPException(400, "Give a reason of at least 10 characters; it is kept in the access log")
    return r


def _email(v) -> str:
    e = str(v or "").strip().lower()
    if not EMAIL.match(e):
        raise HTTPException(400, "Enter a valid email address")
    return e


def _name(v) -> str:
    n = str(v or "").strip()
    if not 1 <= len(n) <= 200:
        raise HTTPException(400, "Enter the person's full name")
    return n


def warnings(roles: list[str], users: list[dict] | None = None, email: str = "") -> list[str]:
    w = []
    rs = set(roles)
    if not rs & set(WORKSPACES):
        w.append("No workspace role: this person can sign in but will see nothing.")
    if rs & PROPOSERS and rs & {"investment_committee", "chief_compliance_officer"}:
        w.append("Separation of duties: this person can propose changes (PM or analyst) and also approve them "
                 "as Investment Committee or CCO. The app will still stop them deciding the same item twice.")
    if "investment_committee" in rs and "leadership" not in rs:
        w.append("Investment Committee permission without the Leadership workspace: they can't see committee screens.")
    if "chief_compliance_officer" in rs and "compliance" not in rs:
        w.append("CCO permission without the Compliance workspace: they can't see compliance screens.")
    if "chief_compliance_officer" in rs and users is not None:
        others = [u["name"] or u["email"] for u in users
                  if u["email"] != email and u["enabled"] and "chief_compliance_officer" in u["roles"]]
        if others:
            w.append(f"Another enabled user already holds the CCO permission ({', '.join(others)}). "
                     "The CCO should be one named person.")
    if rs >= {"portfolio_manager", "risk"}:
        w.append("Holds both Portfolio Manager and Risk: fine for testing, but the two approvals for a vintage "
                 "must come from different people.")
    return w


def _guard_admins(users: list[dict], email: str, new_roles: list[str] | None, enabled: bool | None) -> None:
    def keeps(u):
        roles = new_roles if u["email"] == email and new_roles is not None else u["roles"]
        on = enabled if u["email"] == email and enabled is not None else u["enabled"]
        return on and "admin" in roles
    if not any(keeps(u) for u in users):
        raise HTTPException(400, "At least one enabled admin must remain")


def _change(request: Request, actor: dict, action: str, email: str, before, after, reason: str, revoke=True):
    st = _store()
    st.log_access(actor, action, email, before, after, reason)
    if revoke:
        st.revoke_sessions(email)


# ------------------------------------------------------------------ API
@router.get("/api/admin/users")
def list_users(request: Request):
    user = auth.require_user(request)
    auth.require_role(user, "admin", "audit", "compliance")      # audit and compliance: read-only access reviews
    users = directory(_store()).list_users()
    for u in users:
        u["warnings"] = warnings(u["roles"], users, u["email"])
    return {"users": users, "roles": {k: v for k, v in auth.ROLES.items() if k not in auth.PERMISSIONS},
            "permissions": auth.PERMISSIONS}


@router.post("/api/admin/check")
def check(request: Request, body: dict = Body(...)):
    """Warnings for a proposed set of roles, before saving."""
    _admin(request)
    roles = _norm_roles(body.get("roles", []))
    return {"warnings": warnings(roles, directory(_store()).list_users(), str(body.get("email", "")).lower())}


@router.post("/api/admin/users")
def create_user(request: Request, body: dict = Body(...)):
    me = _admin(request, write=True)
    email, name, roles, reason = _email(body.get("email")), _name(body.get("name")), _norm_roles(body.get("roles", [])), _reason(body)
    if not set(roles) & set(WORKSPACES):
        raise HTTPException(400, "Choose at least one workspace role")
    d = directory(_store())
    d.create(email, name, roles)
    _change(request, me, "create", email, None, {"name": name, "roles": roles}, reason, revoke=False)
    return {"ok": True, "message": f"Invited {email}. They'll receive an email with a temporary password."}


@router.put("/api/admin/users/{email}")
def update_user(request: Request, email: str, body: dict = Body(...)):
    me = _admin(request, write=True)
    email, reason = _email(email), _reason(body)
    d = directory(_store())
    before = d.get(email)
    out = []
    if "name" in body and _name(body["name"]) != before["name"]:
        d.rename(email, _name(body["name"]))
        _change(request, me, "rename", email, {"name": before["name"]}, {"name": _name(body["name"])}, reason, revoke=False)
        out.append("name")
    if "roles" in body:
        roles = _norm_roles(body["roles"])
        if sorted(roles) != sorted(before["roles"]):
            if email == (me.get("email") or "").lower() and "admin" in before["roles"] and "admin" not in roles:
                raise HTTPException(400, "You can't remove your own admin role. Ask another admin.")
            _guard_admins(d.list_users(), email, roles, None)
            d.set_roles(email, roles)
            _change(request, me, "set_access", email, {"roles": before["roles"]}, {"roles": roles}, reason)
            out.append("access")
    if not out:
        return {"ok": True, "message": "No changes"}
    signed_out = " They've been signed out so the change applies at once." if "access" in out else ""
    return {"ok": True, "message": f"Updated {email} ({', '.join(out)}).{signed_out}"}


@router.post("/api/admin/users/{email}/{action}")
def user_action(request: Request, email: str, action: str, body: dict = Body(...)):
    me = _admin(request, write=True)
    email, reason = _email(email), _reason(body)
    if action not in ("disable", "enable", "resend-invite"):
        raise HTTPException(404)
    d = directory(_store())
    before = d.get(email)
    if action == "disable":
        if email == (me.get("email") or "").lower():
            raise HTTPException(400, "You can't disable your own account")
        _guard_admins(d.list_users(), email, None, False)
        d.set_enabled(email, False)
        _change(request, me, "disable", email, {"enabled": before["enabled"]}, {"enabled": False}, reason)
        return {"ok": True, "message": f"Disabled {email} and signed them out. Their history is kept."}
    if action == "enable":
        d.set_enabled(email, True)
        _change(request, me, "enable", email, {"enabled": before["enabled"]}, {"enabled": True}, reason)
        return {"ok": True, "message": f"Enabled {email}."}
    if before["status"] != "FORCE_CHANGE_PASSWORD":
        raise HTTPException(400, "They've already set a password; use 'Forgot your password?' on the sign-in page")
    d.resend_invite(email)
    _change(request, me, "resend_invite", email, None, None, reason, revoke=False)
    return {"ok": True, "message": f"Invitation re-sent to {email}."}


@router.delete("/api/admin/users/{email}")
def delete_user(request: Request, email: str, body: dict = Body(...)):
    me = _admin(request, write=True)
    email, reason = _email(email), _reason(body)
    if email == (me.get("email") or "").lower():
        raise HTTPException(400, "You can't delete your own account")
    if str(body.get("confirm", "")).strip().lower() != email:
        raise HTTPException(400, "Type the user's email address to confirm deletion")
    d = directory(_store())
    before = d.get(email)
    if before["enabled"]:
        raise HTTPException(400, "Disable the account first; only disabled accounts can be deleted")
    d.delete(email)
    _change(request, me, "delete", email, {k: before[k] for k in ("name", "roles", "status")}, None, reason)
    return {"ok": True, "message": f"Deleted {email}. Their past approvals stay in the ledger under their name."}


@router.get("/api/admin/access-log")
def access_log(request: Request):
    user = auth.require_user(request)
    auth.require_role(user, "admin", "audit", "compliance")
    return {"events": _store().access_events()}


# ------------------------------------------------------------------ screen
@router.get("/admin")
def admin_page(request: Request):
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login")
    auth.require_role(user, "admin", "audit", "compliance")
    from importlib.resources import files
    html = (files("meridian.app") / "admin.html").read_text()
    import json
    boot = {"user": {"name": user["name"], "email": user.get("email", ""), "roles": user["roles"]},
            "csrf": user["csrf"], "can_edit": "admin" in user["roles"]}
    return HTMLResponse(html.replace("/*BOOT*/null", json.dumps(boot).replace("</", "<\\/")))
