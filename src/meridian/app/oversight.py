"""Oversight features shared by several personas (docs: personas gap summary).

- Exception workflow: breaches and warnings with owner, due date, notes, remediation, CCO acceptance with expiry
  and closure. Every event is written to the hash-chained governance ledger.
- Ledger search across all runs (population queries for compliance testing and audit sampling), with CSV export.
- Previous-run summary used by "Changes since last run".
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import JSON, Column, DateTime, String, select

from . import auth
from .store import Base, LedgerRecord, now

router = APIRouter()

STATUSES = ("open", "in_progress", "remediated", "accepted", "closed")
WRITE_ROLES = ("compliance", "risk")                 # open, assign, close, reopen
NOTE_ROLES = ("compliance", "risk", "portfolio_manager", "leadership")
VIEW_ROLES = ("compliance", "risk", "portfolio_manager", "leadership", "audit", "admin")
MAX_ACCEPT_DAYS = 365


class ExceptionCase(Base):
    __tablename__ = "exceptions"
    id = Column(String(40), primary_key=True)
    status = Column(String(20), nullable=False, index=True)
    body = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


def _store():
    from .main import store
    return store()


def _who(user: dict) -> dict:
    return {"name": user.get("name"), "email": user.get("email", "")}


def _date(v, field: str) -> str:
    try:
        return date.fromisoformat(str(v)[:10]).isoformat()
    except ValueError:
        raise HTTPException(400, f"{field}: use a date like 2026-12-31") from None


def _reason(body: dict) -> str:
    r = str(body.get("reason", "")).strip()
    if len(r) < 10:
        raise HTTPException(400, "Give a reason or note of at least 10 characters")
    return r


def governance_record(s, *, step: str, actor: dict, summary: str, output: dict, rationale: str = "",
                      scope: list | None = None, dr_type: str = "exception") -> str:
    """Append one record to the hash-chained governance ledger inside session `s`."""
    from ..ledger import GENESIS, _hash
    last = s.execute(select(LedgerRecord).where(LedgerRecord.run_id == "governance")
                     .order_by(LedgerRecord.seq.desc()).limit(1)).scalar()
    body = {"dr_id": "dr_" + uuid.uuid4().hex[:20], "dr_type": dr_type, "run_id": "governance", "step": step,
            "actor": {"kind": "human", "id": actor.get("name"), "email": actor.get("email", "")},
            "portfolio_scope": scope or [], "inputs": [], "policy_version": "", "output": output,
            "summary": summary, "rationale": rationale, "alternatives_considered": [], "constraints_checked": [],
            "dissent": [], "approvals": [], "data_flags": {}, "created_at": datetime.now(timezone.utc).isoformat(),
            "prev_hash": last.record["record_hash"] if last else GENESIS}
    body["record_hash"] = _hash(body)
    s.add(LedgerRecord(run_id="governance", seq=(last.seq + 1) if last else 0, dr_id=body["dr_id"],
                       record=body, record_hash=body["record_hash"]))
    return body["dr_id"]


def _event(case: dict, actor: dict, action: str, note: str, **changes) -> None:
    case.setdefault("history", []).append({"at": datetime.now(timezone.utc).isoformat(), "by": actor,
                                           "action": action, "note": note, "changes": changes})


def open_case(s, *, title: str, severity: str, actor: dict, reason: str, rule_id: str = "", run_id: str = "",
              vintage=None, details: str = "", owner: str = "", due: str = "", source: str = "manual") -> dict:
    cid = "EXC-" + datetime.now(timezone.utc).strftime("%y%m%d") + "-" + uuid.uuid4().hex[:4].upper()
    case = {"id": cid, "title": title, "severity": severity, "rule_id": rule_id, "run_id": run_id,
            "vintage": vintage, "details": details, "owner": owner, "due": due, "status": "open",
            "opened_by": actor, "opened_at": datetime.now(timezone.utc).isoformat(), "source": source,
            "accepted_until": None, "resolution": ""}
    _event(case, actor, "open", reason, status="open", owner=owner, due=due)
    case["dr_ids"] = [governance_record(s, step="exception.open", actor=actor, summary=f"{cid} opened: {title}",
                                        output={k: case[k] for k in ("id", "severity", "rule_id", "run_id", "vintage",
                                                                     "owner", "due", "source")},
                                        rationale=reason, scope=[f"MTRS-{vintage}"] if vintage else [])]
    s.add(ExceptionCase(id=cid, status="open", body=case))
    return case


def open_from_run(run_id: str, results: dict) -> list[str]:
    """Open one exception per WARN or FAIL rule result in a newly published run (system-raised)."""
    st = _store()
    out = []
    with st.Session.begin() as s:
        existing = {(c.body.get("run_id"), c.body.get("vintage"), c.body.get("rule_id"))
                    for c in s.execute(select(ExceptionCase)).scalars()}
        for v, d in results.get("vintages", {}).items():
            for r in d.get("compliance", []):
                if r.get("status") not in ("WARN", "FAIL") or (run_id, int(v), r["rule_id"]) in existing:
                    continue
                days = 5 if r["status"] == "FAIL" else 30
                c = open_case(s, title=f"{r['rule_id']} {r['status']} on {v}", severity=r["status"].lower(),
                              actor={"name": "Meridian (system)", "email": ""},
                              reason=f"Rule engine result {r['status']}: {r.get('detail') or r.get('message') or ''}".strip(),
                              rule_id=r["rule_id"], run_id=run_id, vintage=int(v),
                              details=f"Measured {r.get('measured')} vs limit {r.get('limit')} ({r.get('ips', '')}, "
                                      f"{r.get('severity', '')}). {r.get('detail') or ''}".strip(), source="rule-engine",
                              due=(date.today() + timedelta(days=days)).isoformat())
                out.append(c["id"])
    return out


def list_cases() -> list[dict]:
    with _store().Session() as s:
        return sorted((c.body for c in s.execute(select(ExceptionCase)).scalars()),
                      key=lambda b: (STATUSES.index(b["status"]) if b["status"] in STATUSES else 9, b.get("due") or "9"))


@router.get("/api/exceptions")
def get_exceptions(request: Request):
    user = auth.require_user(request)
    auth.require_role(user, *VIEW_ROLES)
    return {"exceptions": list_cases(), "today": date.today().isoformat()}


@router.post("/api/exceptions")
def create_exception(request: Request, body: dict = Body(...)):
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *WRITE_ROLES)
    title = str(body.get("title", "")).strip()
    if not 5 <= len(title) <= 200:
        raise HTTPException(400, "Give the exception a short title")
    sev = body.get("severity", "warn")
    if sev not in ("fail", "warn", "info"):
        raise HTTPException(400, "Severity must be fail, warn or info")
    due = _date(body["due"], "Due date") if body.get("due") else ""
    with _store().Session.begin() as s:
        c = open_case(s, title=title, severity=sev, actor=_who(user), reason=_reason(body),
                      rule_id=str(body.get("rule_id", ""))[:40], run_id=str(body.get("run_id", ""))[:64],
                      vintage=int(body["vintage"]) if body.get("vintage") else None,
                      details=str(body.get("details", ""))[:4000], owner=str(body.get("owner", ""))[:200], due=due)
    return c


@router.post("/api/exceptions/{cid}/actions")
def act(request: Request, cid: str, body: dict = Body(...)):
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    action = body.get("action")
    note = _reason(body)
    me = _who(user)
    with _store().Session.begin() as s:
        row = s.get(ExceptionCase, cid)
        if not row:
            raise HTTPException(404, "No such exception")
        c = dict(row.body)
        st = c["status"]
        is_owner = bool(c.get("owner")) and c["owner"].strip().lower() in {(me["name"] or "").lower(), (me["email"] or "").lower()}
        changes = {}
        if action == "assign":
            auth.require_role(user, *WRITE_ROLES)
            if st == "closed":
                raise HTTPException(400, "Reopen the exception first")
            if "owner" in body:
                changes["owner"] = str(body["owner"]).strip()[:200]
            if body.get("due"):
                changes["due"] = _date(body["due"], "Due date")
            if st == "open" and changes.get("owner"):
                changes["status"] = "in_progress"
        elif action == "note":
            if not is_owner:
                auth.require_role(user, *NOTE_ROLES)
        elif action == "remediate":
            if not is_owner:
                auth.require_role(user, *WRITE_ROLES)
            if st not in ("open", "in_progress"):
                raise HTTPException(400, f"Can't mark a {st} exception as remediated")
            changes = {"status": "remediated", "resolution": note}
        elif action == "accept":
            auth.require_role(user, "chief_compliance_officer")
            if st not in ("open", "in_progress"):
                raise HTTPException(400, f"Can't accept a {st} exception")
            until = _date(body.get("until", ""), "Accepted until")
            if not date.today() < date.fromisoformat(until) <= date.today() + timedelta(days=MAX_ACCEPT_DAYS):
                raise HTTPException(400, f"Acceptance must expire within {MAX_ACCEPT_DAYS} days")
            changes = {"status": "accepted", "accepted_until": until, "resolution": note}
        elif action == "close":
            auth.require_role(user, "compliance")
            if st not in ("remediated", "accepted"):
                raise HTTPException(400, "Only remediated or accepted exceptions can be closed")
            if c.get("opened_by", {}).get("name") == me["name"] and c.get("source") == "manual" and \
                    not any(h["by"].get("name") != me["name"] for h in c.get("history", [])[1:]):
                raise HTTPException(400, "Separation of duties: someone other than the person who opened it must "
                                         "have worked it before you close it")
            changes = {"status": "closed"}
        elif action == "reopen":
            auth.require_role(user, *WRITE_ROLES)
            if st not in ("remediated", "accepted", "closed"):
                raise HTTPException(400, "Only remediated, accepted or closed exceptions can be reopened")
            changes = {"status": "in_progress" if c.get("owner") else "open", "accepted_until": None}
        else:
            raise HTTPException(400, "Unknown action")
        c.update(changes)
        _event(c, me, action, note, **changes)
        c["dr_ids"] = c.get("dr_ids", []) + [governance_record(
            s, step=f"exception.{action}", actor=me, summary=f"{cid} {action} by {me['name']}" +
            (f" → {changes['status']}" if "status" in changes else ""), output={"id": cid, **changes},
            rationale=note, scope=[f"MTRS-{c['vintage']}"] if c.get("vintage") else [])]
        row.body, row.status = c, c["status"]
    return c


# ------------------------------------------------------------------ ledger search across runs
SEARCH_ROLES = ("compliance", "audit", "admin")


def _match(rec: dict, run_id: str, q: str, f: dict) -> bool:
    if f.get("run_id") and run_id != f["run_id"]:
        return False
    if f.get("dr_type") and rec.get("dr_type") != f["dr_type"]:
        return False
    if f.get("step") and f["step"].lower() not in rec.get("step", "").lower():
        return False
    if f.get("vintage") and f"MTRS-{f['vintage']}" not in (rec.get("portfolio_scope") or []):
        return False
    if f.get("actor") and f["actor"].lower() not in str(rec.get("actor", {}).get("id", "")).lower():
        return False
    ts = rec.get("created_at", "")[:10]
    if f.get("date_from") and ts < f["date_from"]:
        return False
    if f.get("date_to") and ts > f["date_to"]:
        return False
    if q:
        hay = " ".join([rec.get("dr_id", ""), rec.get("step", ""), rec.get("summary", ""), rec.get("rationale", ""),
                        str(rec.get("actor", {}).get("id", "")), " ".join(rec.get("portfolio_scope") or [])]).lower()
        return all(t in hay for t in q.lower().split())
    return True


@router.get("/api/ledger/search")
def ledger_search(request: Request, q: str = "", run_id: str = "", dr_type: str = "", step: str = "", vintage: str = "",
                  actor: str = "", date_from: str = "", date_to: str = "", limit: int = 500, format: str = "json"):
    user = auth.require_user(request)
    auth.require_role(user, *SEARCH_ROLES)
    f = {"run_id": run_id, "dr_type": dr_type, "step": step, "vintage": vintage, "actor": actor,
         "date_from": date_from[:10], "date_to": date_to[:10]}
    hits, total = [], 0
    with _store().Session() as s:
        for row in s.execute(select(LedgerRecord).order_by(LedgerRecord.run_id, LedgerRecord.seq)).scalars():
            total += 1
            if _match(row.record, row.run_id, q.strip(), f):
                r = row.record
                hits.append({"run_id": row.run_id, "seq": row.seq, "dr_id": r["dr_id"], "dr_type": r.get("dr_type"),
                             "step": r.get("step"), "actor": r.get("actor", {}).get("id"),
                             "scope": ", ".join(r.get("portfolio_scope") or []), "created_at": r.get("created_at"),
                             "summary": r.get("summary"), "rationale": r.get("rationale", ""),
                             "record_hash": r.get("record_hash")})
    if format == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(hits[0].keys()) if hits else ["run_id", "dr_id"])
        w.writeheader()
        w.writerows(hits)
        return Response(buf.getvalue(), media_type="text/csv", headers={
            "Content-Disposition": f'attachment; filename="meridian-ledger-search-{date.today().isoformat()}.csv"'})
    return {"total_records": total, "matches": len(hits), "results": hits[:max(1, min(limit, 2000))]}


# ------------------------------------------------------------------ previous run, for "Changes since last run"
def previous_summary(st, run) -> dict | None:
    prev = next((r for r in st.list_runs() if r["as_of"] < run.as_of), None)
    if not prev:
        return None
    pr = st.get_run(prev["id"]).results
    vint = {}
    for v, d in pr.get("vintages", {}).items():
        vint[v] = {"final": d.get("final", {}), "exp_ret": d.get("exp_ret"), "vol": d.get("vol"), "te": d.get("te"),
                   "equity_final": d.get("equity_final"), "ensemble": d.get("ensemble"),
                   "status": d.get("compliance_summary", {}).get("overall")}
    return {"run_id": prev["id"], "as_of": prev["as_of"], "regime": pr.get("macro", {}).get("regime"),
            "cma": {c["asset"]: c.get("judge") for c in pr.get("cma", [])}, "vintages": vint}
