"""Policy workspace: the Investment Policy Statement (versioned) and named glide paths (doc 07, doc 17 §9).

IPS: anyone in a drafting workspace proposes a new version (the full text plus a summary of the change). It
takes effect once an Investment Committee member and the Chief Compliance Officer approve it, two different
people and neither of them the drafter. Every version stays readable with a redline against the one before.
The rule engine reads the policy file (policy-as-code), so a text change that alters a limit also needs a
policy file change; the approval screen asks the drafter to say whether it does.

Glide paths: the IPS glide path ("ips") is the default and can't be edited here. Anyone in a drafting
workspace can propose a new named path, a new version of a path, or a change to which path a fund follows.
Each takes effect when an Investment Committee member other than the requester approves it. The IPS bands sit
around each fund's own path. Every step is a governance ledger record with dr_type "policy_change".
"""
from __future__ import annotations

import difflib
import json
import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, select

from .. import REPO_ROOT
from ..trading import glidepaths as GP
from . import auth
from .oversight import governance_record
from .store import Base, now

router = APIRouter()

VIEW_ROLES = ("portfolio_manager", "risk", "analyst", "manager_selection", "leadership", "compliance", "audit", "admin")
DRAFT_ROLES = ("portfolio_manager", "compliance", "leadership", "risk")
IC = "investment_committee"
CCO = "chief_compliance_officer"
IPS_SEED = REPO_ROOT / "policies" / "ips" / "meridian-target-retirement-series-ips.md"


class IpsVersion(Base):
    __tablename__ = "ips_versions"
    version = Column(Integer, primary_key=True)
    status = Column(String(16), nullable=False, index=True)   # pending | approved | superseded | rejected | withdrawn
    text = Column(Text, nullable=False)
    body = Column(JSON, nullable=False)                         # summary, drafted_by, approvals, decisions, rules_change
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


def _store():
    from .main import store
    return store()


def _who(user: dict) -> dict:
    return {"name": user.get("name"), "email": user.get("email", "")}


def _ts() -> str:
    return datetime.now(UTC).isoformat()


def _reason(body: dict, n: int = 10) -> str:
    r = str(body.get("reason", "")).strip()
    if len(r) < n:
        raise HTTPException(400, f"Give a reason of at least {n} characters")
    return r


def _same(a: dict, user: dict) -> bool:
    return (a.get("email") or a.get("name") or "").lower() in {(user.get("email") or "").lower(), (user.get("name") or "").lower()} - {""}


def _record(s, user: dict, step: str, summary: str, output: dict, rationale: str = "", scope=None) -> str:
    return governance_record(s, step=step, actor=_who(user), summary=summary, output=output, rationale=rationale,
                             scope=scope or [], dr_type="policy_change")


# ---------------------------------------------------------------------------------------------- page
@router.get("/policy")
def page(request: Request):
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login")
    auth.require_role(user, *VIEW_ROLES)
    from importlib.resources import files
    html = (files("meridian.app") / "policy.html").read_text()
    roles = user["roles"]
    boot = {"user": {"name": user["name"], "email": user.get("email", ""), "roles": roles}, "csrf": user["csrf"],
            "can_draft": any(r in roles for r in DRAFT_ROLES), "is_ic": IC in roles, "is_cco": CCO in roles}
    from .shell import wrap
    return HTMLResponse(wrap(html.replace("/*BOOT*/null", json.dumps(boot).replace("</", "<\\/")), user, "policy"))


# ---------------------------------------------------------------------------------------------- IPS
def _seed_ips(s) -> None:
    if s.execute(select(IpsVersion).limit(1)).scalar() is not None:
        return
    text = IPS_SEED.read_text() if IPS_SEED.exists() else "# Investment Policy Statement\n"
    s.add(IpsVersion(version=1, status="approved", text=text, body={
        "summary": "Initial version, loaded from the policy repository (policies/ips)", "drafted_by": {"name": "Meridian", "email": ""},
        "drafted_at": _ts(), "approvals": [], "seeded": True, "rules_change": False, "effective_at": _ts()}))
    s.flush()


def _ips_out(v: IpsVersion, text: bool = False) -> dict:
    d = {"version": v.version, "status": v.status, **v.body}
    if text:
        d["text"] = v.text
    return d


def redline(old: str, new: str) -> list[dict]:
    """Line-level diff; changed lines also carry a word-level diff. ops: eq | del | ins | chg (+ words)."""
    a, b = old.splitlines(), new.splitlines()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            out += [{"op": "eq", "text": x} for x in a[i1:i2]]
        elif op == "delete":
            out += [{"op": "del", "text": x} for x in a[i1:i2]]
        elif op == "insert":
            out += [{"op": "ins", "text": x} for x in b[j1:j2]]
        else:
            olds, news = a[i1:i2], b[j1:j2]
            for k in range(max(len(olds), len(news))):
                o, n = (olds[k] if k < len(olds) else None), (news[k] if k < len(news) else None)
                if o is None:
                    out.append({"op": "ins", "text": n})
                elif n is None:
                    out.append({"op": "del", "text": o})
                else:
                    ow, nw = re.findall(r"\S+|\s+", o), re.findall(r"\S+|\s+", n)
                    words = []
                    for wop, a1, a2, b1, b2 in difflib.SequenceMatcher(None, ow, nw, autojunk=False).get_opcodes():
                        if wop == "equal":
                            words.append(["eq", "".join(ow[a1:a2])])
                        else:
                            if a2 > a1:
                                words.append(["del", "".join(ow[a1:a2])])
                            if b2 > b1:
                                words.append(["ins", "".join(nw[b1:b2])])
                    out.append({"op": "chg", "words": words})
    return out


@router.get("/api/policy/ips")
def ips_list(request: Request):
    user = auth.require_user(request)
    auth.require_role(user, *VIEW_ROLES)
    with _store().Session.begin() as s:
        _seed_ips(s)
        vs = list(s.execute(select(IpsVersion).order_by(IpsVersion.version.desc())).scalars())
        cur = next((v for v in vs if v.status == "approved"), None)
        return {"versions": [_ips_out(v) for v in vs], "current": cur.version if cur else None,
                "pending": next((v.version for v in vs if v.status == "pending"), None)}


@router.get("/api/policy/ips/{version}")
def ips_get(request: Request, version: int, compare: int | None = None):
    user = auth.require_user(request)
    auth.require_role(user, *VIEW_ROLES)
    with _store().Session.begin() as s:
        _seed_ips(s)
        v = s.get(IpsVersion, version)
        if not v:
            raise HTTPException(404, "No such version")
        out = _ips_out(v, text=True)
        base = s.get(IpsVersion, compare) if compare else (
            s.execute(select(IpsVersion).where(IpsVersion.version < version, IpsVersion.status.in_(("approved", "superseded")))
                      .order_by(IpsVersion.version.desc()).limit(1)).scalar())
        if base:
            out["compare_to"] = base.version
            out["redline"] = redline(base.text, v.text)
            out["changed_lines"] = sum(1 for x in out["redline"] if x["op"] != "eq")
        return out


@router.post("/api/policy/ips/preview")
def ips_preview(request: Request, body: dict = Body(...)):
    """Redline of a draft against the current version, before it is proposed."""
    user = auth.require_user(request)
    auth.require_role(user, *VIEW_ROLES)
    with _store().Session.begin() as s:
        _seed_ips(s)
        cur = s.execute(select(IpsVersion).where(IpsVersion.status == "approved")).scalar()
        rl = redline(cur.text if cur else "", str(body.get("text", "")))
        return {"compare_to": cur.version if cur else None, "redline": rl, "changed_lines": sum(1 for x in rl if x["op"] != "eq")}


@router.post("/api/policy/ips")
def ips_propose(request: Request, body: dict = Body(...)):
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *DRAFT_ROLES)
    text = str(body.get("text", ""))
    summary = str(body.get("summary", "")).strip()
    if len(summary) < 10:
        raise HTTPException(400, "Summarise the change in at least 10 characters")
    if len(text) > 400_000:
        raise HTTPException(400, "The text is too long (400,000 characters at most)")
    if "rules_change" not in body:
        raise HTTPException(400, "Say whether the change alters a limit or rule the engine checks")
    with _store().Session.begin() as s:
        _seed_ips(s)
        if s.execute(select(IpsVersion).where(IpsVersion.status == "pending")).scalar():
            raise HTTPException(409, "Another version is waiting for approval; approve, reject or withdraw it first")
        cur = s.execute(select(IpsVersion).where(IpsVersion.status == "approved")).scalar()
        if cur and cur.text.strip() == text.strip():
            raise HTTPException(400, "The text is the same as the current version")
        n = (s.execute(select(IpsVersion.version).order_by(IpsVersion.version.desc()).limit(1)).scalar() or 0) + 1
        rl = redline(cur.text if cur else "", text)
        changed = sum(1 for x in rl if x["op"] != "eq")
        b = {"summary": summary, "drafted_by": _who(user), "drafted_at": _ts(), "approvals": [],
             "rules_change": bool(body.get("rules_change")), "based_on": cur.version if cur else None, "changed_lines": changed}
        s.add(IpsVersion(version=n, status="pending", text=text, body=b))
        b["dr_id"] = _record(s, user, "ips.propose", f"IPS version {n} proposed: {summary}",
                             {"version": n, "based_on": b["based_on"], "changed_lines": changed, "rules_change": b["rules_change"],
                              "sha256": __import__("hashlib").sha256(text.encode()).hexdigest()}, summary)
    return {"ok": True, "version": n, "changed_lines": changed}


@router.post("/api/policy/ips/{version}/decide")
def ips_decide(request: Request, version: int, body: dict = Body(...)):
    """approve | reject (IC member or CCO, not the drafter) or withdraw (the drafter)."""
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    action = body.get("action")
    reason = _reason(body)
    roles = user["roles"]
    with _store().Session.begin() as s:
        v = s.get(IpsVersion, version)
        if not v or v.status != "pending":
            raise HTTPException(409, "That version isn't waiting for a decision")
        b = dict(v.body)
        if action == "withdraw":
            if not _same(b["drafted_by"], user):
                raise HTTPException(403, "Only the drafter can withdraw a draft")
            v.status = "withdrawn"
            b["decided"] = {"action": "withdraw", "by": _who(user), "at": _ts(), "reason": reason}
            b["dr_withdraw"] = _record(s, user, "ips.withdraw", f"IPS version {version} withdrawn", {"version": version}, reason)
            v.body = b
            return {"ok": True, "status": v.status}
        if action not in ("approve", "reject"):
            raise HTTPException(400, "action must be approve, reject or withdraw")
        as_ = body.get("as")
        if as_ not in ("ic", "cco"):
            raise HTTPException(400, "Say whether you're deciding as the Investment Committee (ic) or the CCO (cco)")
        if as_ == "ic" and IC not in roles:
            raise HTTPException(403, "Needs the Investment Committee permission")
        if as_ == "cco" and CCO not in roles:
            raise HTTPException(403, "Needs the Chief Compliance Officer permission")
        if _same(b["drafted_by"], user):
            raise HTTPException(403, "The drafter can't approve or reject their own draft")
        if any(a["as"] == as_ for a in b["approvals"]):
            raise HTTPException(409, f"The {'Investment Committee' if as_ == 'ic' else 'CCO'} approval is already recorded")
        if any(_same(a["by"], user) for a in b["approvals"]):
            raise HTTPException(403, "The two approvals must come from two different people")
        if action == "reject":
            v.status = "rejected"
            b["decided"] = {"action": "reject", "as": as_, "by": _who(user), "at": _ts(), "reason": reason}
            b["dr_reject"] = _record(s, user, "ips.reject", f"IPS version {version} rejected ({as_.upper()})",
                                     {"version": version, "as": as_}, reason)
            v.body = b
            return {"ok": True, "status": v.status}
        dr = _record(s, user, "ips.approve", f"IPS version {version} approved by the {'Investment Committee' if as_ == 'ic' else 'CCO'}",
                     {"version": version, "as": as_}, reason)
        b["approvals"] = b["approvals"] + [{"as": as_, "by": _who(user), "at": _ts(), "reason": reason, "dr_id": dr}]
        if {a["as"] for a in b["approvals"]} == {"ic", "cco"}:
            for old in s.execute(select(IpsVersion).where(IpsVersion.status == "approved")).scalars():
                old.status = "superseded"
                old.body = {**old.body, "superseded_by": version, "superseded_at": _ts()}
            v.status = "approved"
            b["effective_at"] = _ts()
            b["dr_effective"] = _record(s, user, "ips.effective", f"IPS version {version} is now the current IPS"
                                        + (" (a policy file change is needed for its rule changes)" if b.get("rules_change") else ""),
                                        {"version": version, "approvals": [{"as": a["as"], "by": a["by"]} for a in b["approvals"]],
                                         "rules_change": b.get("rules_change", False)})
        v.body = b
        return {"ok": True, "status": v.status, "approvals": len(b["approvals"])}


# ---------------------------------------------------------------------------------------------- glide paths
def _gp_state(s) -> dict:
    from .trading import TradingSetting
    row = s.get(TradingSetting, "glidepaths")
    return json.loads(json.dumps(row.body)) if row else {"paths": [], "assignments": {}, "requests": []}


def _gp_put(s, st: dict) -> None:
    from .trading import _put
    _put(s, "glidepaths", st)


def _ips_path() -> dict:
    from .trading import model
    p = model().policy
    return {"id": GP.IPS_ID, "name": "IPS glide path", "description": f"The glide path in the Investment Policy Statement ({p.id})",
            "version": str(p.raw.get("version", "")),
            "anchors": [list(map(float, r)) for r in p.raw["glide_path"]["anchors"]], "read_only": True,
            "policy_version": p.id}


def _active(path: dict) -> dict | None:
    return next((v for v in path["versions"] if v["status"] == "active"), None)


def path_by_id(st: dict, pid: str) -> dict | None:
    if pid == GP.IPS_ID:
        return _ips_path()
    p = next((x for x in st["paths"] if x["id"] == pid), None)
    if not p:
        return None
    a = _active(p)
    return {"id": p["id"], "name": p["name"], "description": p.get("description", ""),
            "version": a["version"] if a else None, "anchors": a["anchors"] if a else None}


def fund_path(s, fund_id: str) -> dict | None:
    """The glide path a fund follows: {id, name, version, anchors}. The IPS path unless one is assigned."""
    st = _gp_state(s)
    pid = (st.get("assignments") or {}).get(fund_id, GP.IPS_ID)
    p = path_by_id(st, pid)
    return p if p and p.get("anchors") else _ips_path()


@router.get("/api/policy/glide-paths")
def gp_list(request: Request):
    user = auth.require_user(request)
    auth.require_role(user, *VIEW_ROLES)
    from .trading import model
    m = model()
    groups, assets = m.policy.groups, m.policy.assets
    with _store().Session() as s:
        st = _gp_state(s)
    ips = _ips_path()
    paths = [{**ips, "status": "active", "versions": [{"version": ips["version"], "status": "active", "anchors": ips["anchors"],
                                                     "note": "Set in the policy file; changes go through the IPS"}]}]
    for p in st["paths"]:
        a = _active(p)
        paths.append({"id": p["id"], "name": p["name"], "description": p.get("description", ""), "read_only": False,
                      "status": "active" if a else "pending", "version": a["version"] if a else None,
                      "anchors": a["anchors"] if a else p["versions"][-1]["anchors"], "versions": p["versions"],
                      "created_by": p.get("created_by")})
    for p in paths:
        p["funds"] = sorted(f for f in m.funds if (st["assignments"].get(f, GP.IPS_ID)) == p["id"])
        p["equity_curve"] = GP.equity_curve(p["anchors"], assets, groups)
        p["vs_ips"] = GP.max_difference(p["anchors"], ips["anchors"], assets, groups) if p["id"] != GP.IPS_ID else None
    funds = [{"id": f.id, "vehicle": f.vehicle, "vintage": f.vintage, "roll_down": f.roll_down,
              "path": st["assignments"].get(f.id, GP.IPS_ID),
              "years_to_target": round(m.years_to_target(f.id), 2)} for f in sorted(m.funds.values(), key=lambda f: (f.vehicle, f.vintage))]
    from ..policy import load_universe
    u = load_universe()
    return {"assets": assets, "asset_names": {a: (u.get(a) or {}).get("name", a) for a in assets}, "groups": groups,
            "paths": paths, "funds": funds, "requests": st["requests"][::-1][:100], "assignments": st["assignments"]}


@router.post("/api/policy/glide-paths/requests")
def gp_request(request: Request, body: dict = Body(...)):
    """kind: new_path {name, description, anchors} | new_version {path_id, anchors} | assign {path_id, funds}."""
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *DRAFT_ROLES)
    reason = _reason(body)
    from .trading import model
    m = model()
    kind = body.get("kind")
    with _store().Session.begin() as s:
        st = _gp_state(s)
        req = {"id": "GPR-" + uuid.uuid4().hex[:8].upper(), "kind": kind, "status": "pending", "requested_by": _who(user),
               "requested_at": _ts(), "reason": reason}
        if kind in ("new_path", "new_version"):
            try:
                anchors = GP.clean_anchors(body.get("anchors"), len(m.policy.assets))
            except ValueError as e:
                raise HTTPException(400, str(e)) from None
            req["anchors"] = anchors
            req["vs_ips"] = GP.max_difference(anchors, _ips_path()["anchors"], m.policy.assets, m.policy.groups)
            if kind == "new_path":
                name = str(body.get("name", "")).strip()
                if not 3 <= len(name) <= 60:
                    raise HTTPException(400, "Give the path a name of 3 to 60 characters")
                if any(p["name"].lower() == name.lower() for p in st["paths"]) or name.lower() == "ips glide path":
                    raise HTTPException(409, "A glide path with that name already exists")
                pid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or "path"
                while any(p["id"] == pid for p in st["paths"]) or pid == GP.IPS_ID:
                    pid += "-2"
                st["paths"].append({"id": pid, "name": name, "description": str(body.get("description", "")).strip()[:400],
                                    "created_by": _who(user), "created_at": _ts(),
                                    "versions": [{"version": 1, "status": "pending", "anchors": anchors, "request": req["id"],
                                                  "by": _who(user), "at": _ts(), "reason": reason}]})
                req.update(path_id=pid, version=1, label=f"New glide path {name}")
            else:
                p = next((x for x in st["paths"] if x["id"] == body.get("path_id")), None)
                if not p:
                    raise HTTPException(404 if body.get("path_id") != GP.IPS_ID else 400,
                                        "The IPS glide path changes through an IPS and policy file update" if body.get("path_id") == GP.IPS_ID
                                        else "No such glide path")
                if any(v["status"] == "pending" for v in p["versions"]):
                    raise HTTPException(409, f"{p['name']} already has a version waiting for approval")
                a = _active(p)
                if a and a["anchors"] == anchors:
                    raise HTTPException(400, "No change from the current version")
                n = max(v["version"] for v in p["versions"]) + 1
                p["versions"].append({"version": n, "status": "pending", "anchors": anchors, "request": req["id"],
                                      "by": _who(user), "at": _ts(), "reason": reason})
                req.update(path_id=p["id"], version=n, label=f"{p['name']} version {n}")
        elif kind == "assign":
            pid = body.get("path_id")
            p = path_by_id(st, pid)
            if not p or not p.get("anchors"):
                raise HTTPException(400, "Assign an approved glide path")
            funds = [f for f in (body.get("funds") or []) if f in m.funds]
            if not funds:
                raise HTTPException(400, "Choose at least one fund")
            funds = [f for f in funds if st["assignments"].get(f, GP.IPS_ID) != pid]
            if not funds:
                raise HTTPException(400, "Those funds already follow that path")
            busy = {f for r in st["requests"] if r["status"] == "pending" and r["kind"] == "assign" for f in r["funds"]}
            if busy & set(funds):
                raise HTTPException(409, f"Already waiting for a decision: {', '.join(sorted(busy & set(funds)))}")
            req.update(path_id=pid, funds=sorted(funds), before={f: st["assignments"].get(f, GP.IPS_ID) for f in funds},
                       label=f"{', '.join(sorted(funds))} to follow {p['name']}")
        else:
            raise HTTPException(400, "kind must be new_path, new_version or assign")
        st["requests"].append(req)
        req["dr_id"] = _record(s, user, "glide-path.request", f"Glide path request {req['id']}: {req['label']}",
                               {k: v for k, v in req.items() if k not in ("requested_by",)}, reason,
                               scope=req.get("funds") or [])
        st["requests"][-1] = req
        _gp_put(s, st)
    return {"ok": True, "request": req}


@router.post("/api/policy/glide-paths/requests/{rid}/decide")
def gp_decide(request: Request, rid: str, body: dict = Body(...)):
    """approve | reject: an Investment Committee member other than the requester. withdraw: the requester."""
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    action = body.get("action")
    reason = _reason(body)
    with _store().Session.begin() as s:
        st = _gp_state(s)
        req = next((r for r in st["requests"] if r["id"] == rid), None)
        if not req or req["status"] != "pending":
            raise HTTPException(409, "That request isn't waiting for a decision")
        if action == "withdraw":
            if not _same(req["requested_by"], user):
                raise HTTPException(403, "Only the requester can withdraw a request")
        elif action in ("approve", "reject"):
            if IC not in user["roles"]:
                raise HTTPException(403, "Needs the Investment Committee permission")
            if _same(req["requested_by"], user):
                raise HTTPException(403, "The requester can't decide their own request")
        else:
            raise HTTPException(400, "action must be approve, reject or withdraw")
        status = {"approve": "approved", "reject": "rejected", "withdraw": "withdrawn"}[action]
        req.update(status=status, decided_by=_who(user), decided_at=_ts(), decision_reason=reason)
        path = next((p for p in st["paths"] if p["id"] == req.get("path_id")), None)
        if req["kind"] in ("new_path", "new_version") and path:
            ver = next(v for v in path["versions"] if v["version"] == req["version"])
            if status == "approved":
                for v in path["versions"]:
                    if v["status"] == "active":
                        v["status"] = "superseded"
                ver.update(status="active", approved_by=_who(user), approved_at=_ts())
            else:
                ver["status"] = status
                if req["kind"] == "new_path":            # nothing approved yet: the path never existed
                    st["paths"] = [p for p in st["paths"] if p["id"] != path["id"]]
        if req["kind"] == "assign" and status == "approved":
            if req["path_id"] != GP.IPS_ID and not (path and _active(path)):
                raise HTTPException(409, "That glide path has no approved version any more")
            for f in req["funds"]:
                if req["path_id"] == GP.IPS_ID:
                    st["assignments"].pop(f, None)
                else:
                    st["assignments"][f] = req["path_id"]
        req["decision_dr_id"] = _record(s, user, f"glide-path.{action}", f"Glide path request {rid} {status}: {req['label']}",
                                        {"request": rid, "kind": req["kind"], "status": status, "path_id": req.get("path_id"),
                                         "version": req.get("version"), "funds": req.get("funds")}, reason,
                                        scope=req.get("funds") or [])
        _gp_put(s, st)
    return {"ok": True, "status": status}


@router.get("/api/policy/ledger")
def ledger(request: Request):
    user = auth.require_user(request)
    auth.require_role(user, *VIEW_ROLES)
    return {"records": [r for r in _store().ledger("governance") if r.get("dr_type") == "policy_change"][-200:]}
