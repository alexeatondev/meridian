"""Meridian hosted app (FastAPI).

Serves the role-adaptive Console from the database and the API behind every action. Every write goes
through the same deterministic code as the CLI (compliance engine, approvals, adjustments, change
requests) and lands in the hash-chained decision ledger.
"""
from __future__ import annotations

import hmac
import io
import json
import os
import secrets
import tarfile
import tempfile
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response

from .. import __version__
from ..ledger import verify
from ..policy import POLICY_PATH, load_policy
from . import auth
from .store import Store

app = FastAPI(title="Meridian", version=__version__, docs_url=None, redoc_url=None)
_store: Store | None = None


def store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


# ------------------------------------------------------------------ security middleware
@app.middleware("http")
async def guard(request: Request, call_next):
    expected = os.getenv("ORIGIN_VERIFY")           # shared secret set by CloudFront; blocks direct ALB access
    if expected and request.url.path != "/healthz" and not hmac.compare_digest(
            request.headers.get("x-origin-verify", ""), expected):
        return PlainTextResponse("Forbidden", status_code=403)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Cache-Control", "no-store")
    return resp


def _secure() -> bool:
    return os.getenv("APP_BASE_URL", "").startswith("https://")


def _set_session(resp: Response, user: dict) -> None:
    resp.set_cookie(auth.SESSION_COOKIE, auth.make_session(user), max_age=auth.SESSION_TTL, httponly=True,
                    secure=_secure(), samesite="lax")


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>body{{font-family:system-ui,sans-serif;background:#f4f3f0;color:#111;display:grid;place-items:center;min-height:100vh;margin:0}}
.card{{background:#fff;border:1px solid #e2e0da;border-radius:12px;padding:28px;max-width:440px;width:100%}}h1{{font-size:20px;margin:0 0 6px}}
label{{display:block;margin:10px 0 4px;font-size:13px}}input[type=text]{{width:100%;padding:8px;border:1px solid #ccc;border-radius:8px;box-sizing:border-box}}
.btn{{display:inline-block;margin-top:16px;background:#1f4e8c;color:#fff;border:0;padding:10px 16px;border-radius:8px;font-weight:600;text-decoration:none;cursor:pointer}}
.muted{{color:#666;font-size:13px}}</style></head><body><div class="card">{body}</div></body></html>""", status_code=status)


# ------------------------------------------------------------------ auth routes
@app.get("/healthz")
def healthz():
    return {"ok": True, "version": __version__}


@app.get("/login")
def login(request: Request):
    if auth.mode() == "dev":
        boxes = "".join(f'<label><input type="checkbox" name="roles" value="{k}"> {v}</label>' for k, v in auth.ROLES.items())
        return _page("Sign in (dev)", f"""<h1>Meridian — development sign-in</h1><p class="muted">Local testing only. On AWS, sign-in uses Amazon Cognito.</p>
<form method="post" action="/dev-login"><label>Name</label><input type="text" name="name" value="Dev" required>{boxes}
<button class="btn" type="submit">Sign in</button></form>""")
    state = secrets.token_urlsafe(24)
    resp = RedirectResponse(auth.login_url(state))
    resp.set_cookie("meridian_oauth_state", state, max_age=600, httponly=True, secure=_secure(), samesite="lax")
    return resp


@app.post("/dev-login")
async def dev_login(request: Request):
    if auth.mode() != "dev":
        raise HTTPException(404)
    form = await request.form()
    user = {"sub": "dev-" + str(form.get("name")), "name": str(form.get("name") or "Dev"), "email": "",
            "roles": [r for r in form.getlist("roles") if r in auth.ROLES]}
    resp = RedirectResponse("/", status_code=303)
    _set_session(resp, user)
    return resp


@app.get("/auth/callback")
def callback(request: Request, code: str = "", state: str = ""):
    if not code or not state or not hmac.compare_digest(state, request.cookies.get("meridian_oauth_state", "")):
        raise HTTPException(400, "Invalid sign-in state")
    user = auth.exchange_code(code)
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("meridian_oauth_state")
    _set_session(resp, user)
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse(auth.logout_url() if auth.mode() != "dev" else "/signed-out", status_code=303)
    resp.delete_cookie(auth.SESSION_COOKIE)
    return resp


@app.get("/signed-out")
def signed_out():
    return _page("Signed out", '<h1>Signed out</h1><a class="btn" href="/login">Sign in again</a>')


# ------------------------------------------------------------------ console
@app.get("/")
def home(request: Request):
    return RedirectResponse("/runs/latest")


@app.get("/runs/{run_id}")
def console(request: Request, run_id: str):
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login")
    if not user.get("roles"):
        return _page("No role", f"<h1>Welcome, {user['name']}</h1><p>Your account has no Meridian role yet. "
                                "Ask an administrator to add you to a group (e.g. portfolio_manager, risk, compliance).</p>"
                                '<a class="btn" href="/logout">Sign out</a>', 403)
    st = store()
    rid = st.latest_run_id() if run_id == "latest" else run_id
    if not rid:
        return _page("No runs", "<h1>No runs yet</h1><p class='muted'>Run the <b>agent-run</b> workflow on GitHub; "
                                "it publishes each run here automatically.</p>")
    run = st.get_run(rid)
    if run is None:
        raise HTTPException(404, "Run not found")
    ledger = st.ledger(rid)
    ok, msg = _verify_records(ledger)
    from ..ui.build import console_html
    pol = _effective_policy()
    live = {"user": {"name": user["name"], "email": user.get("email", ""), "roles": user["roles"]},
            "console_roles": sorted({auth.CONSOLE_ROLE[r] for r in user["roles"]}, key=list(auth.CONSOLE_ROLE.values()).index),
            "role_ids": {auth.CONSOLE_ROLE[r]: r for r in user["roles"]},
            "csrf": user["csrf"], "runs": st.list_runs()[:24], "run_id": rid}
    return HTMLResponse(console_html(run.results, ledger, {"ok": ok, "message": msg}, run.board_memo,
                                     run.compliance_report, st.change_requests(), pol, live))


def _verify_records(records: list[dict]) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "l.jsonl"
        p.write_text("".join(json.dumps(r, default=str) + "\n" for r in records))
        return verify(p)


def _effective_policy():
    with tempfile.TemporaryDirectory() as d:
        return load_policy(store().write_effective_policy(POLICY_PATH, Path(d) / "p.yaml"))


# ------------------------------------------------------------------ API: actions
def _actor(request: Request) -> dict:
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    return user


def _bad(e: BaseException):
    raise HTTPException(400, str(e) or "Invalid request")


@app.get("/api/me")
def me(request: Request):
    return auth.require_user(request) | {"csrf": None}


@app.get("/api/runs")
def runs(request: Request):
    auth.require_user(request)
    return store().list_runs()


@app.post("/api/runs/{run_id}/approvals")
def approve(request: Request, run_id: str, body: dict = Body(...)):
    user = _actor(request)
    role = body.get("role")
    auth.require_role(user, role) if role else None
    from ..approvals import record_decision
    try:
        with store().run_workspace(run_id) as wd:
            dr = record_decision(wd, int(body["vintage"]), role, user["name"], body["decision"], body.get("reason", ""))
    except (SystemExit, ValueError, KeyError) as e:
        _bad(e)
    return {"dr_id": dr}


@app.post("/api/runs/{run_id}/adjustments")
def adjust_ep(request: Request, run_id: str, body: dict = Body(...)):
    user = _actor(request)
    role = auth.require_role(user, "portfolio_manager", "analyst")
    from ..adjustments import adjust
    try:
        with store().run_workspace(run_id) as wd:
            out = adjust(wd, int(body["vintage"]), list(body["specs"]), user["name"], role, body.get("reason", ""))
    except (SystemExit, ValueError, KeyError) as e:
        _bad(e)
    return {k: out[k] for k in ("dr_id", "te", "risk_budget_used", "compliance_summary", "approvers")}


@app.post("/api/risk-budget/requests")
def rb_request(request: Request, body: dict = Body(...)):
    user = _actor(request)
    role = auth.require_role(user, "portfolio_manager", "risk")
    from .. import governance as gv
    try:
        with store().governance_workspace(POLICY_PATH) as (gov, pol):
            cr = gv.request_risk_budget_change(body["vintage"], float(body["te"]), user["name"], role,
                                               body.get("reason", ""), gov, pol)
    except (SystemExit, ValueError, KeyError) as e:
        _bad(e)
    return cr


@app.post("/api/risk-budget/requests/{cr_id}/decisions")
def rb_decide(request: Request, cr_id: str, body: dict = Body(...)):
    user = _actor(request)
    role = body.get("role")
    auth.require_role(user, role)
    from .. import governance as gv
    try:
        with store().governance_workspace(POLICY_PATH) as (gov, pol):
            cr = gv.approve_change(cr_id, user["name"], role, body.get("decision", "approve"), body.get("reason", ""), gov, pol)
    except (SystemExit, ValueError, KeyError) as e:
        _bad(e)
    return cr


@app.get("/api/runs/{run_id}/evidence")
def evidence(request: Request, run_id: str):
    user = auth.require_user(request)
    auth.require_role(user, "audit", "compliance", "admin")
    run = store().get_run(run_id)
    if not run:
        raise HTTPException(404)
    recs = store().ledger(run_id)
    ok, msg = _verify_records(recs)
    return JSONResponse({"run_id": run_id, "as_of": run.as_of, "integrity": {"ok": ok, "message": msg},
                         "policy_overrides": store().overrides(), "records": recs},
                        headers={"Content-Disposition": f'attachment; filename="{run_id}-evidence.json"'})


# ------------------------------------------------------------------ API: machine (GitHub workflows)
def _machine(request: Request) -> None:
    token = os.getenv("INGEST_TOKEN")
    got = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(got, token):
        raise HTTPException(401, "Invalid token")


@app.post("/api/ingest")
async def ingest(request: Request, bundle: UploadFile = File(...)):
    _machine(request)
    data = await bundle.read()
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            for m in tf.getmembers():
                if not m.isfile() or m.name.startswith("/") or ".." in Path(m.name).parts:
                    continue
                if Path(m.name).name in ("results.json", "ledger.jsonl", "board_memo.md", "compliance_report.md"):
                    (Path(d) / Path(m.name).name).write_bytes(tf.extractfile(m).read())
        ok, msg = verify(Path(d) / "ledger.jsonl")
        if not ok:
            raise HTTPException(400, f"Ledger integrity check failed: {msg}")
        try:
            rid = store().ingest_run(Path(d))
        except ValueError as e:
            raise HTTPException(409, str(e))
    return {"run_id": rid, "ledger": msg}


@app.get("/api/export/positions.csv")
def export_positions(request: Request):
    _machine(request)
    with tempfile.TemporaryDirectory() as d:
        return PlainTextResponse(store().positions_csv(Path(d) / "p.csv").read_text(), media_type="text/csv")


@app.get("/api/export/risk-history.csv")
def export_risk_history(request: Request):
    _machine(request)
    with tempfile.TemporaryDirectory() as d:
        return PlainTextResponse(store().risk_history_csv(Path(d) / "r.csv").read_text(), media_type="text/csv")


@app.get("/api/export/policy-overrides")
def export_overrides(request: Request):
    _machine(request)
    return store().overrides()
