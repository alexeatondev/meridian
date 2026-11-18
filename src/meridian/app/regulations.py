"""Regulations & obligations workspace (doc 18).

Compliance tags funds with regulations from regimes/fund_regulations.yaml (US and ex-US). A tag switches on
the regulation's controls (checked on every trade list and on current holdings) and creates its obligation
tasks (owner, due date, evidence). Completing a recurring task creates the next one. Overdue tasks open an
exception case once. Removing a tag needs the Chief Compliance Officer permission. Every step is a governance
ledger record with dr_type "regulation".
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import JSON, Column, DateTime, String, select

from .. import regulations as R
from . import auth
from .oversight import governance_record, open_case
from .store import Base, now

router = APIRouter()

VIEW_ROLES = ("compliance", "audit", "admin", "leadership", "portfolio_manager", "risk", "analyst")
TAG_ROLES = ("compliance",)                       # add a regulation (adds controls: allowed for Compliance)
REMOVE_PERMISSION = "chief_compliance_officer"    # removing a regulation lowers controls: CCO only
WORK_ROLES = ("compliance", "risk", "leadership", "portfolio_manager")


class FundRegulation(Base):
    __tablename__ = "fund_regulations"
    id = Column(String(80), primary_key=True)            # "<fund_id>|<reg_id>"
    status = Column(String(16), nullable=False, index=True)   # active | removed
    body = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


class ComplianceTask(Base):
    __tablename__ = "compliance_tasks"
    id = Column(String(40), primary_key=True)
    status = Column(String(20), nullable=False, index=True)   # open | in_progress | done | waived | cancelled
    body = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


class FundProfile(Base):
    """Per-fund settings for obligations: the fiscal year end (doc 18 §5)."""
    __tablename__ = "fund_profiles"
    fund_id = Column(String(40), primary_key=True)
    body = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


def _store():
    from .main import store
    return store()


def _who(user: dict) -> dict:
    return {"name": user.get("name"), "email": user.get("email", "")}


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> date:
    return date.today()


def _reason(body: dict, field: str = "reason", n: int = 10) -> str:
    r = str(body.get(field, "")).strip()
    if len(r) < n:
        raise HTTPException(400, f"Give a {'reason' if field == 'reason' else field} of at least {n} characters")
    return r


def _record(s, actor: dict, step: str, summary: str, output: dict, rationale: str = "", scope=None) -> str:
    return governance_record(s, step=step, actor=actor, summary=summary, output=output, rationale=rationale,
                             scope=scope or [], dr_type="regulation")


def _funds():
    from .trading import model
    return model().funds


def fye_for(s, fund_id: str) -> str:
    row = s.get(FundProfile, fund_id)
    return (row.body.get("fiscal_year_end") if row else None) or R.DEFAULT_FYE


def active_tags(s, fund_id: str | None = None) -> list[dict]:
    rows = s.execute(select(FundRegulation).where(FundRegulation.status == "active")).scalars()
    return [r.body for r in rows if fund_id is None or r.body["fund_id"] == fund_id]


def tags_for(fund_id: str) -> list[dict]:
    with _store().Session() as s:
        return active_tags(s, fund_id)


def controls_for(fund_id: str, rows: list[dict]) -> list[dict]:
    """Regulation controls for one fund, on the given (post-trade) rows. Used by the Trading screen."""
    from .trading import model
    tags = tags_for(fund_id)
    return R.evaluate_controls(rows, model().instruments, tags) if tags else []


def _new_task(s, fund_id: str, reg: dict, ob: dict, occ: dict, actor: dict) -> str:
    tid = "OBL-" + uuid.uuid4().hex[:10].upper()
    body = {"id": tid, "fund_id": fund_id, "reg_id": reg["id"], "regulation": reg.get("short", reg["name"]),
            "obligation_id": ob["id"], "title": ob["title"], "cite": ob.get("cite", ""), "frequency": ob["frequency"],
            "owner_role": ob.get("owner_role", "compliance"), "owner": "", "evidence_required": ob.get("evidence", ""),
            "note": ob.get("note", ""), "status": "open", "created_at": _ts(), "created_by": actor,
            "escalated": None, "history": [], **occ}
    s.add(ComplianceTask(id=tid, status="open", body=body))
    return tid


# ---------------------------------------------------------------------------------------------- page + state
@router.get("/regulations")
def page(request: Request):
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login")
    auth.require_role(user, *VIEW_ROLES)
    from importlib.resources import files
    html = (files("meridian.app") / "regulations.html").read_text()
    roles = user["roles"]
    boot = {"user": {"name": user["name"], "email": user.get("email", ""), "roles": roles}, "csrf": user["csrf"],
            "can_tag": any(r in roles for r in TAG_ROLES), "can_remove": REMOVE_PERMISSION in roles,
            "can_work": any(r in roles for r in WORK_ROLES), "is_cco": REMOVE_PERMISSION in roles}
    from .shell import wrap
    return HTMLResponse(wrap(html.replace("/*BOOT*/null", json.dumps(boot).replace("</", "<\\/")), user, "regulations"))


def _escalate_overdue(s, tasks: list[ComplianceTask]) -> None:
    """Open one exception case per overdue obligation (doc 06 §8 workflow)."""
    today = _today().isoformat()
    for t in tasks:
        b = t.body
        if b["status"] in ("open", "in_progress") and b["due"] < today and not b.get("escalated"):
            case = open_case(s, title=f"Overdue obligation: {b['title']} ({b['fund_id']}, {b['period']})"[:200],
                             severity="warn", actor={"name": "Meridian (obligation tracker)", "email": ""},
                             reason=f"{b['regulation']} obligation {b['obligation_id']} was due {b['due']}",
                             rule_id=b["obligation_id"][:40], details=f"Task {b['id']}. {b.get('cite', '')}",
                             owner=b.get("owner") or b["owner_role"], due="", source="obligation")
            t.body = dict(b, escalated=case["id"])


@router.get("/api/regulations/state")
def state(request: Request):
    user = auth.require_user(request)
    auth.require_role(user, *VIEW_ROLES)
    from ..entities import resolve
    from .trading import model, positions
    lib = R.library()
    m = model()
    ent = resolve()
    with _store().Session.begin() as s:
        tasks = list(s.execute(select(ComplianceTask)).scalars())
        fyes = {fid: fye_for(s, fid) for fid in m.funds}
        _escalate_overdue(s, tasks)
        tags = active_tags(s)
        tasks_out = [t.body for t in tasks]
        removed = [r.body for r in s.execute(select(FundRegulation).where(FundRegulation.status == "removed")).scalars()]
    funds = []
    for fid, f in m.funds.items():
        ft = [t for t in tags if t["fund_id"] == fid]
        ctrl = R.evaluate_controls(R.holdings_rows(positions(fid), m.instruments), m.instruments, ft) if ft else []
        regs = [lib["regulations"][t["reg_id"]] for t in ft if t["reg_id"] in lib["regulations"]]
        roles = sorted({r for g in regs for r in g.get("required_roles", [])})
        funds.append(dict(f.as_dict(), tags=ft, fiscal_year_end=fyes[fid], fiscal_year_end_label=R.fye_label(fyes[fid]), suggested=[x for x in lib["suggestions"].get(f.vehicle, [])
                                                              if x not in {t["reg_id"] for t in ft}],
                          controls=ctrl, controls_status=R.overall(ctrl) if ctrl else "—",
                          retention_years=max([g.get("retention_years", 0) for g in regs], default=None),
                          roles=[{"role": r, "holder": ent.holder_label(r), "filled": r not in ent.unfilled_roles
                                  and bool(ent.role_holder(r)[0])} for r in roles],
                          open_tasks=sum(1 for t in tasks_out if t["fund_id"] == fid and t["status"] in ("open", "in_progress"))))
    return {"today": _today().isoformat(), "default_fye": R.DEFAULT_FYE, "library": lib["regulations"], "funds": funds, "tasks": tasks_out,
            "removed": removed,
            "records": [r for r in _store().ledger("governance") if r.get("dr_type") == "regulation"][-200:]}


# ---------------------------------------------------------------------------------------------- tagging
@router.post("/api/regulations/tags")
def add_tags(request: Request, body: dict = Body(...)):
    """Tag one or more funds with a regulation (or update its parameters). Creates the obligation tasks."""
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *TAG_ROLES)
    reason = _reason(body)
    lib = R.library()["regulations"]
    reg = lib.get(body.get("reg_id"))
    if not reg:
        raise HTTPException(400, "Unknown regulation")
    funds = _funds()
    fids = list(dict.fromkeys(body.get("fund_ids") or []))
    if not fids or any(f not in funds for f in fids):
        raise HTTPException(400, "Choose one or more known funds")
    params = {k: bool(v) for k, v in (body.get("params") or {}).items() if k in ("rule_12d1_4",)}
    added, updated, n_tasks = [], [], 0
    with _store().Session.begin() as s:
        for fid in fids:
            key = f"{fid}|{reg['id']}"
            row = s.get(FundRegulation, key)
            if row and row.status == "active":
                if row.body.get("params", {}) != params:
                    row.body = dict(row.body, params=params, history=row.body["history"] + [
                        {"at": _ts(), "by": _who(user), "action": "params", "params": params, "reason": reason}])
                    updated.append(fid)
                continue
            b = {"id": key, "fund_id": fid, "reg_id": reg["id"], "regulation": reg.get("short", reg["name"]),
                 "jurisdiction": reg["jurisdiction"], "scope": reg["scope"], "params": params, "added_by": _who(user),
                 "added_at": _ts(), "reason": reason,
                 "fits_vehicle": funds[fid].vehicle in reg.get("applies_to", [funds[fid].vehicle]),
                 "history": [{"at": _ts(), "by": _who(user), "action": "add", "reason": reason}]}
            if row:
                row.body, row.status = dict(b, history=row.body["history"] + b["history"]), "active"
            else:
                s.add(FundRegulation(id=key, status="active", body=b))
            for ob in reg.get("obligations", []):
                _new_task(s, fid, reg, ob, R.first_task(ob, _today(), fye_for(s, fid)), _who(user))
                n_tasks += 1
            added.append(fid)
        if not added and not updated:
            raise HTTPException(400, "Nothing changed: every chosen fund already has this regulation")
        dr = _record(s, _who(user), "regulation.tag",
                     f"{reg.get('short', reg['name'])} added to {len(added)} funds"
                     + (f", parameters updated on {len(updated)}" if updated else "") + f"; {n_tasks} obligations created",
                     {"reg_id": reg["id"], "added": added, "updated": updated, "params": params,
                      "controls": [c["id"] for c in reg.get("controls", [])],
                      "obligations": [o["id"] for o in reg.get("obligations", [])]}, reason, added + updated)
    return {"ok": True, "added": added, "updated": updated, "tasks_created": n_tasks, "dr_id": dr}


@router.post("/api/regulations/tags/remove")
def remove_tags(request: Request, body: dict = Body(...)):
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    if REMOVE_PERMISSION not in user["roles"]:
        raise HTTPException(403, "Removing a regulation lowers a fund's controls: it needs the Chief Compliance "
                                 "Officer permission")
    reason = _reason(body)
    reg_id = body.get("reg_id")
    fids = list(dict.fromkeys(body.get("fund_ids") or []))
    removed, cancelled = [], 0
    with _store().Session.begin() as s:
        for fid in fids:
            row = s.get(FundRegulation, f"{fid}|{reg_id}")
            if not row or row.status != "active":
                continue
            row.body = dict(row.body, removed_by=_who(user), removed_at=_ts(), history=row.body["history"] + [
                {"at": _ts(), "by": _who(user), "action": "remove", "reason": reason}])
            row.status = "removed"
            for t in s.execute(select(ComplianceTask).where(ComplianceTask.status.in_(("open", "in_progress")))).scalars():
                if t.body["fund_id"] == fid and t.body["reg_id"] == reg_id:
                    t.body = dict(t.body, status="cancelled", history=t.body["history"] + [
                        {"at": _ts(), "by": _who(user), "action": "cancelled", "note": "Regulation removed: " + reason}])
                    t.status = "cancelled"
                    cancelled += 1
            removed.append(fid)
        if not removed:
            raise HTTPException(400, "None of the chosen funds carries this regulation")
        dr = _record(s, _who(user), "regulation.remove", f"{reg_id} removed from {len(removed)} funds; "
                     f"{cancelled} open obligations cancelled", {"reg_id": reg_id, "removed": removed,
                                                                  "cancelled_tasks": cancelled}, reason, removed)
    return {"ok": True, "removed": removed, "cancelled_tasks": cancelled, "dr_id": dr}


# ---------------------------------------------------------------------------------------------- fiscal year ends
@router.put("/api/regulations/fiscal-year-end")
def set_fiscal_year_end(request: Request, body: dict = Body(...)):
    """Set the fiscal year end of one or more funds. Open obligations that follow the fiscal year are moved to
    the matching fiscal period (the one that just ended if it is still due, otherwise the current one); done,
    waived and calendar-based obligations are left as they are. Compliance only; recorded in the ledger."""
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *TAG_ROLES)
    reason = _reason(body)
    fye = str(body.get("fiscal_year_end", "")).strip()
    try:
        R.parse_fye(fye)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if fye.startswith("02-"):
        fye = "02-28"
    funds = _funds()
    fids = list(dict.fromkeys(body.get("fund_ids") or []))
    if not fids or any(f not in funds for f in fids):
        raise HTTPException(400, "Choose one or more known funds")
    lib = R.library()["regulations"]
    changed, moved = [], []
    with _store().Session.begin() as s:
        for fid in fids:
            old = fye_for(s, fid)
            if old == fye:
                continue
            row = s.get(FundProfile, fid)
            hist = (row.body.get("history", []) if row else []) + [
                {"at": _ts(), "by": _who(user), "from": old, "to": fye, "reason": reason}]
            if row:
                row.body = dict(row.body, fiscal_year_end=fye, history=hist)
            else:
                s.add(FundProfile(fund_id=fid, body={"fund_id": fid, "fiscal_year_end": fye, "history": hist}))
            changed.append({"fund_id": fid, "from": old, "to": fye})
            for t in s.execute(select(ComplianceTask).where(ComplianceTask.status.in_(("open", "in_progress")))).scalars():
                b = t.body
                if b["fund_id"] != fid:
                    continue
                ob = next((o for o in (lib.get(b["reg_id"]) or {}).get("obligations", []) if o["id"] == b["obligation_id"]), None)
                occ = R.reschedule(ob, _today(), fye) if ob else None
                if not occ or (occ["period_end"] == b["period_end"] and occ["due"] == b["due"]):
                    continue
                moved.append({"task": b["id"], "fund_id": fid, "obligation": b["obligation_id"],
                              "from": {"period": b["period"], "due": b["due"]}, "to": {"period": occ["period"], "due": occ["due"]}})
                t.body = dict(b, **occ, history=b["history"] + [
                    {"at": _ts(), "by": _who(user), "action": "rescheduled",
                     "note": f"Fiscal year end changed to {R.fye_label(fye)}: {b['period']} due {b['due']} → "
                             f"{occ['period']} due {occ['due']}"}])
        if not changed:
            raise HTTPException(400, f"Nothing changed: the chosen funds already end their fiscal year on {R.fye_label(fye)}")
        dr = _record(s, _who(user), "fund.fiscal_year_end",
                     f"Fiscal year end set to {R.fye_label(fye)} for {len(changed)} funds; {len(moved)} open obligations moved",
                     {"fiscal_year_end": fye, "funds": changed, "moved": moved}, reason, [c["fund_id"] for c in changed])
    return {"ok": True, "changed": [c["fund_id"] for c in changed], "moved": moved, "dr_id": dr}


# ---------------------------------------------------------------------------------------------- obligations
@router.post("/api/regulations/tasks/{tid}/actions")
def task_action(request: Request, tid: str, body: dict = Body(...)):
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *WORK_ROLES)
    action = body.get("action")
    lib = R.library()["regulations"]
    with _store().Session.begin() as s:
        row = s.get(ComplianceTask, tid)
        if not row:
            raise HTTPException(404, "Unknown obligation")
        b = dict(row.body)
        if b["status"] in ("done", "waived", "cancelled"):
            raise HTTPException(409, f"This obligation is {b['status']}")
        note = str(body.get("note", "")).strip()
        nxt = None
        if action == "assign":
            owner = str(body.get("owner", "")).strip()
            if not owner:
                raise HTTPException(400, "Name the owner")
            b["owner"] = owner
        elif action == "start":
            b["status"] = "in_progress"
        elif action == "note":
            if len(note) < 5:
                raise HTTPException(400, "Write a note")
        elif action == "complete":
            evidence = _reason(body, "evidence", 10)
            b.update(status="done", evidence=evidence, completed_by=_who(user), completed_at=_ts())
            reg = lib.get(b["reg_id"])
            ob = next((o for o in (reg or {}).get("obligations", []) if o["id"] == b["obligation_id"]), None)
            active = s.get(FundRegulation, f"{b['fund_id']}|{b['reg_id']}")
            occ = R.next_task(ob, b["period_end"], fye_for(s, b["fund_id"])) if ob else None
            if occ and active and active.status == "active":
                nxt = _new_task(s, b["fund_id"], reg, ob, occ, {"name": "Meridian (obligation tracker)", "email": ""})
        elif action == "waive":
            if REMOVE_PERMISSION not in user["roles"]:
                raise HTTPException(403, "Only the Chief Compliance Officer can waive an obligation")
            _reason(body, "note", 10)
            b["status"] = "waived"
            reg = lib.get(b["reg_id"])
            ob = next((o for o in (reg or {}).get("obligations", []) if o["id"] == b["obligation_id"]), None)
            occ = R.next_task(ob, b["period_end"], fye_for(s, b["fund_id"])) if ob else None
            if occ:
                nxt = _new_task(s, b["fund_id"], reg, ob, occ, {"name": "Meridian (obligation tracker)", "email": ""})
        else:
            raise HTTPException(400, "Action must be assign, start, note, complete or waive")
        b["history"] = b["history"] + [{"at": _ts(), "by": _who(user), "action": action,
                                        "note": note or body.get("evidence", "") or body.get("owner", "")}]
        if nxt:
            b["next_task"] = nxt
        row.body, row.status = b, b["status"]
        dr = _record(s, _who(user), f"obligation.{action}", f"{b['title']} ({b['fund_id']}, {b['period']}): {action}",
                     {"task": tid, "fund_id": b["fund_id"], "reg_id": b["reg_id"], "obligation": b["obligation_id"],
                      "status": b["status"], "evidence": b.get("evidence"), "next_task": nxt},
                     note or b.get("evidence", ""), [b["fund_id"]])
    return {"ok": True, "status": b["status"], "next_task": nxt, "dr_id": dr}
