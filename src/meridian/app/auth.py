"""Authentication and roles.

Production: Amazon Cognito (OAuth2 authorization-code flow, Managed Login). The user's Cognito groups
are their Meridian roles. ID tokens are verified against the user pool's JWKS.
Development: MERIDIAN_AUTH=dev shows a sign-in page where you pick a name and roles (never enabled on AWS).
Sessions are signed, HTTP-only cookies.
"""
from __future__ import annotations

import os
import secrets
import time
from functools import lru_cache
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

ROLES = {
    "portfolio_manager": "Portfolio Manager",
    "risk": "Risk Analytics",
    "analyst": "Research / Analyst",
    "manager_selection": "Manager Selection",
    "leadership": "Leadership / IC",
    "compliance": "Compliance",
    "audit": "Audit (read-only)",
    "admin": "Platform Admin",
}
# Permission flags: switched on or off per user on top of their workspace roles. They don't add a workspace;
# they allow recording decisions that need that authority (IPS §10.4 approval matrix).
PERMISSIONS = {
    "investment_committee": "Investment Committee member (approves glide-path changes and autonomy changes)",
    "chief_compliance_officer": "Chief Compliance Officer (approves exceptions; must be a named person)",
    "route_manager": "Trade route manager (may change where orders are routed; every change is logged)",
    "approver": "Approver (records approval decisions on proposals, risk-budget changes and trade lists; "
                "works with the Portfolio Manager or Risk workspace)",
}
APPROVER = "approver"
APPROVING_WORKSPACES = ("portfolio_manager", "risk")   # their decisions also need the Approver permission
ROLES.update(PERMISSIONS)
# Console workspace key for each role
CONSOLE_ROLE = {"portfolio_manager": "pm", "risk": "risk", "analyst": "research", "manager_selection": "mgr",
                "leadership": "lead", "compliance": "compliance", "audit": "audit", "admin": "audit"}
SESSION_COOKIE = "meridian_session"
SESSION_TTL = 8 * 3600


def mode() -> str:
    return os.getenv("MERIDIAN_AUTH", "cognito")


def _serializer() -> URLSafeTimedSerializer:
    key = os.getenv("SESSION_SECRET")
    if not key:
        if mode() != "dev":
            raise RuntimeError("SESSION_SECRET must be set")
        key = "dev-only-insecure-session-key"
    return URLSafeTimedSerializer(key, salt="meridian-session")


def make_session(user: dict) -> str:
    return _serializer().dumps({**user, "csrf": secrets.token_urlsafe(16), "iat": time.time()})


def current_user(request: Request) -> dict | None:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    try:
        u = _serializer().loads(raw, max_age=SESSION_TTL)
    except BadSignature:
        return None
    if REVOKED_AFTER is not None:               # set by the app: sessions issued before an access change are void
        t = REVOKED_AFTER(u.get("email", ""))
        if t is not None and u.get("iat", 0) <= t:
            return None
    return u


# Hook set by main.py: email -> timestamp after which earlier sessions are revoked (or None)
REVOKED_AFTER = None


def require_user(request: Request) -> dict:
    u = current_user(request)
    if not u:
        raise HTTPException(401, "Sign in required")
    return u


def require_role(user: dict, *roles: str) -> str:
    """Returns the first matching role the user holds, else 403."""
    for r in roles:
        if r in user.get("roles", []):
            return r
    raise HTTPException(403, f"Requires one of: {', '.join(roles)}")


def require_approver(user: dict, role: str | None = None) -> None:
    """Approval decisions recorded as Portfolio Manager or Risk need the Approver permission on top of the workspace."""
    if (role is None or role in APPROVING_WORKSPACES) and APPROVER not in user.get("roles", []):
        raise HTTPException(403, "Recording an approval needs the Approver permission "
                                 "(an admin switches it on in User access)")


def check_csrf(request: Request, user: dict) -> None:
    if request.headers.get("x-csrf-token") != user.get("csrf"):
        raise HTTPException(403, "CSRF check failed")


# ------------------------------------------------------------------ Cognito
def cognito_cfg() -> dict:
    return {"domain": os.environ["COGNITO_DOMAIN"].rstrip("/"),          # https://<prefix>.auth.<region>.amazoncognito.com
            "client_id": os.environ["COGNITO_CLIENT_ID"],
            "client_secret": os.getenv("COGNITO_CLIENT_SECRET", ""),
            "pool_id": os.environ["COGNITO_USER_POOL_ID"],
            "region": os.environ.get("COGNITO_REGION", os.environ.get("AWS_REGION", "us-east-2")),
            "redirect_uri": os.environ["APP_BASE_URL"].rstrip("/") + "/auth/callback"}


def login_url(state: str) -> str:
    c = cognito_cfg()
    return f"{c['domain']}/oauth2/authorize?" + urlencode({
        "response_type": "code", "client_id": c["client_id"], "redirect_uri": c["redirect_uri"],
        "scope": "openid email profile", "state": state})


def logout_url() -> str:
    c = cognito_cfg()
    return f"{c['domain']}/logout?" + urlencode({"client_id": c["client_id"],
                                                 "logout_uri": os.environ["APP_BASE_URL"].rstrip("/") + "/signed-out"})


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    c = cognito_cfg()
    return jwt.PyJWKClient(f"https://cognito-idp.{c['region']}.amazonaws.com/{c['pool_id']}/.well-known/jwks.json")


def exchange_code(code: str) -> dict:
    c = cognito_cfg()
    r = httpx.post(f"{c['domain']}/oauth2/token", timeout=15,
                   data={"grant_type": "authorization_code", "code": code, "redirect_uri": c["redirect_uri"],
                         "client_id": c["client_id"]},
                   auth=(c["client_id"], c["client_secret"]) if c["client_secret"] else None)
    if r.status_code != 200:
        raise HTTPException(401, "Sign-in failed")
    idt = r.json()["id_token"]
    key = _jwks_client().get_signing_key_from_jwt(idt).key
    claims = jwt.decode(idt, key, algorithms=["RS256"], audience=c["client_id"],
                        issuer=f"https://cognito-idp.{c['region']}.amazonaws.com/{c['pool_id']}")
    roles = [g for g in claims.get("cognito:groups", []) if g in ROLES]
    return {"sub": claims["sub"], "email": claims.get("email", ""),
            "name": claims.get("name") or claims.get("email") or claims.get("cognito:username"), "roles": roles}
