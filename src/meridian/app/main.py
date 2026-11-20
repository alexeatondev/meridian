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
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)

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
from .admin import router as _admin_router

app.include_router(_admin_router)
from .oversight import router as _oversight_router  # noqa: E402

app.include_router(_oversight_router)
from .trading import router as _trading_router  # noqa: E402

app.include_router(_trading_router)
from .regulations import router as _regulations_router  # noqa: E402

app.include_router(_regulations_router)
from .policy_admin import router as _policy_router  # noqa: E402

app.include_router(_policy_router)
from .shell import router as _shell_router  # noqa: E402

app.include_router(_shell_router)


def _revoked_after(email: str):
    try:
        return store().revoked_after(email)
    except Exception:            # never lock everyone out because the check itself failed
        return None


auth.REVOKED_AFTER = _revoked_after


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


def _brand_css() -> str:
    from ..branding import theme_css
    return theme_css()


def _page(title: str, body: str, status: int = 200, wide: bool = False) -> HTMLResponse:
    """Pages outside the app shell (sign-in, signed out, no role): the brand's app bar and a centred card."""
    import html as _h
    from ..branding import active, logo_path
    t = active()
    product, company = _h.escape(t.get("product") or "Meridian"), _h.escape(t.get("company") or "")
    mark = '<img src="/brand/logo" alt="">' if logo_path(t) else '<i aria-hidden="true"></i>'
    return HTMLResponse(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · {product}</title><style>
body{{font-family:system-ui,sans-serif;background:var(--bg,#f4f3f0);color:var(--text,#111);margin:0;min-height:100vh;display:flex;flex-direction:column}}
.pbar{{background:var(--appbar-bg,#14233b);color:var(--appbar-text,#fff);height:56px;display:flex;align-items:center;padding:0 24px;gap:10px}}
.pbar .pm{{display:flex;align-items:center;gap:9px;font-weight:700;font-size:16px;letter-spacing:.2px}}
.pbar .pm i{{display:inline-block;width:24px;height:24px;border-radius:var(--radius-sm,6px);background:var(--appbar-mark,linear-gradient(135deg,#7aa7e6,#2f6bc1))}}
.pbar .pm img{{height:26px;width:auto;display:block}}.pbar .pc{{font-weight:400;font-size:12px;color:var(--appbar-muted,#c9d3e3);border-left:1px solid rgba(255,255,255,.3);padding-left:9px}}
main{{flex:1;display:grid;place-items:center;padding:32px 16px}}
.card{{background:var(--surface,#fff);border:1px solid var(--line,#e2e0da);border-top:4px solid var(--accent,#1f4e8c);border-radius:var(--radius-lg,12px);padding:30px 32px;max-width:{'560' if wide else '440'}px;width:100%;box-sizing:border-box;box-shadow:0 2px 10px rgba(0,0,0,.05)}}
h1{{font-size:22px;margin:0 0 8px;color:var(--heading,var(--text,#111))}}p{{line-height:1.5}}
label{{display:block;margin:10px 0 4px;font-size:13px}}input[type=text]{{width:100%;padding:9px;border:1px solid var(--line-strong,#ccc);border-radius:var(--radius-sm,8px);box-sizing:border-box;font:inherit}}
.btn{{display:inline-block;margin-top:16px;background:var(--accent,#1f4e8c);color:var(--accent-ink,#fff);border:1px solid var(--accent,#1f4e8c);padding:11px 18px;border-radius:var(--radius-sm,8px);font-weight:600;text-decoration:none;cursor:pointer;font:inherit;font-weight:600}}
.btn:hover{{background:var(--accent-hover,var(--accent,#1f4e8c))}}.btn:focus-visible,a:focus-visible,input:focus-visible{{outline:2px solid var(--focus,#2f6bc1);outline-offset:2px}}
.btn.full{{display:block;width:100%;text-align:center;box-sizing:border-box}}
.muted{{color:var(--muted,#666);font-size:13px}}.note{{border-top:1px solid var(--line,#e2e0da);margin-top:22px;padding-top:14px}}
.roles label{{display:flex;gap:8px;align-items:center;margin:4px 0}}footer{{text-align:center;padding:14px;font-size:12px;color:var(--muted,#666)}}
</style>{_brand_css()}</head><body><header class="pbar" role="banner"><span class="pm">{mark}{product}</span>{f'<span class="pc">{company}</span>' if company else ''}</header>
<main id="main"><div class="card">{body}</div></main><footer>{product} · shadow mode: nothing is traded automatically</footer></body></html>""", status_code=status)


# ------------------------------------------------------------------ auth routes
@app.get("/healthz")
def healthz():
    return {"ok": True, "version": __version__}


@app.get("/login")
def login(request: Request):
    from ..branding import active
    product = (active().get("product") or "Meridian")
    if auth.mode() == "dev":
        boxes = "".join(f'<label><input type="checkbox" name="roles" value="{k}"> {v}</label>' for k, v in auth.ROLES.items())
        return _page("Sign in (dev)", f"""<h1>Sign in to {product}</h1><p class="muted">Development sign-in for local testing only. On AWS, sign-in uses Amazon Cognito.</p>
<form method="post" action="/dev-login"><label for="dn">Name</label><input id="dn" type="text" name="name" value="Dev" required>
<label for="de">Email (optional)</label><input id="de" type="text" name="email" value=""><div class="roles">{boxes}</div>
<button class="btn full" type="submit">Sign in</button></form>""")
    if request.query_params.get("go") != "1":
        return _page("Sign in", f"""<h1>Sign in to {product}</h1>
<p>Agentic portfolio management for the target-date series: proposals, risk, compliance and trading in one place.</p>
<a class="btn full" href="/login?go=1" id="signin">Sign in</a>
<div class="note muted">You'll sign in with your work email and password on the secure sign-in page, then come straight back here. Forgot your password? Use <b>Forgot your password?</b> on the next page.<br><br>
For authorized users only. Every decision you record is kept in the audit ledger with your name.</div>""")
    state = secrets.token_urlsafe(24)
    resp = RedirectResponse(auth.login_url(state))
    resp.set_cookie("meridian_oauth_state", state, max_age=600, httponly=True, secure=_secure(), samesite="lax")
    return resp


@app.post("/dev-login")
async def dev_login(request: Request):
    if auth.mode() != "dev":
        raise HTTPException(404)
    form = await request.form()
    user = {"sub": "dev-" + str(form.get("name")), "name": str(form.get("name") or "Dev"),
            "email": str(form.get("email") or "").strip().lower(),
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
    return _page("Signed out", '<h1>You\'re signed out</h1><p class="muted">Close the browser tab, or sign in again to continue.</p><a class="btn full" href="/login?go=1">Sign in again</a>')


# ------------------------------------------------------------------ console
@app.get("/")
def home(request: Request):
    user = auth.current_user(request)
    if user and user.get("roles") == ["admin"]:
        return RedirectResponse("/admin")
    return RedirectResponse("/runs/latest")


@app.get("/runs/{run_id}")
def console(request: Request, run_id: str):
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login")
    if not any(r in auth.CONSOLE_ROLE for r in user.get("roles", [])):
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
            "console_roles": sorted({auth.CONSOLE_ROLE[r] for r in user["roles"] if r in auth.CONSOLE_ROLE},
                                    key=list(auth.CONSOLE_ROLE.values()).index),
            "role_ids": {auth.CONSOLE_ROLE[r]: r for r in user["roles"] if r in auth.CONSOLE_ROLE},
            "permissions": [r for r in user["roles"] if r in auth.PERMISSIONS],
            "is_approver": auth.APPROVER in user["roles"],
            "csrf": user["csrf"], "runs": st.list_runs()[:24], "run_id": rid}
    from .oversight import list_cases, previous_summary
    live["prev"] = previous_summary(st, run)
    live["exceptions"] = list_cases()
    live["governance"] = [r for r in st.ledger("governance") if r.get("dr_type") == "exception"][-300:]
    try:
        from .trading import PREPARE_ROLES, console_products
        products = console_products()
        live["can_glide_request"] = any(r in user["roles"] for r in PREPARE_ROLES)
        live["can_glide_decide"] = "investment_committee" in user["roles"]
    except Exception:  # product-line detail is optional; the console works without it
        products = None
    from .shell import wrap
    return HTMLResponse(wrap(console_html(run.results, ledger, {"ok": ok, "message": msg}, run.board_memo,
                                          run.compliance_report, st.change_requests(), pol, live, products=products),
                             user, "console"))


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
    auth.require_approver(user, role)
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
    auth.require_approver(user, role)
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
    from .oversight import open_from_run
    opened = open_from_run(rid, store().get_run(rid).results)
    return {"run_id": rid, "ledger": msg, "exceptions_opened": opened}


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
    """Policy overrides for the next agent run, plus the Investment Committee's approved glide-path adjustments
    (`glide_adjustments`), which the agent-run workflow writes into the policy file."""
    _machine(request)
    ov = dict(store().overrides())
    from .trading import glide_export
    ga = glide_export()
    if ga["vintages"]:
        ov["glide_adjustments"] = ga
    return ov
