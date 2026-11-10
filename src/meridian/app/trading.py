"""Trading workspace (doc 17): cashflows in, trades out, routed and exported for Charles River.

Shadow mode: Meridian proposes and records orders and produces the Charles River import file. It never sends
or executes anything. Every step (cashflows loaded, target table and setting changes, trade lists generated,
approved, cancelled, exported) is written to the hash-chained governance ledger with dr_type "trading".
"""
from __future__ import annotations

import csv
import hmac
import io
import json
import os
import uuid
from datetime import UTC, date, datetime
from functools import lru_cache

import numpy as np
from fastapi import APIRouter, Body, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import JSON, Column, DateTime, String, select

from ..trading import (
    CRD_COLUMNS,
    STRATEGIES,
    VEHICLES,
    allocate_fund,
    crd_rows,
    load_model,
)
from ..trading.allocate import asset_class_weights
from . import auth
from .oversight import governance_record
from .store import Base, now

router = APIRouter()

VIEW_ROLES = ("portfolio_manager", "analyst", "risk", "compliance", "audit", "admin", "leadership")
PREPARE_ROLES = ("portfolio_manager", "analyst")          # load cashflows, generate trade lists
APPROVE_ROLES = ("portfolio_manager",)                    # approve trade lists, change target tables
SETTINGS_ROLES = ("portfolio_manager", "admin")           # routes, buffer, exclusions
CF_TYPES = ("subscription", "redemption")
STATUS_ORDER = ("draft", "approved", "exported", "cancelled")


class Cashflow(Base):
    __tablename__ = "cashflows"
    id = Column(String(40), primary_key=True)
    status = Column(String(20), nullable=False, index=True)       # new | in_trade_list | cancelled
    body = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


class TradeList(Base):
    __tablename__ = "trade_lists"
    id = Column(String(40), primary_key=True)
    status = Column(String(20), nullable=False, index=True)
    body = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


class TradingSetting(Base):
    __tablename__ = "trading_settings"
    key = Column(String(60), primary_key=True)                    # "settings" or "strategic:<fund_id>"
    body = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


@lru_cache(maxsize=1)
def model():
    return load_model()


def _store():
    from .main import store
    return store()


def _who(user: dict) -> dict:
    return {"name": user.get("name"), "email": user.get("email", "")}


def _reason(body: dict, n: int = 10) -> str:
    r = str(body.get("reason", "")).strip()
    if len(r) < n:
        raise HTTPException(400, f"Give a reason of at least {n} characters")
    return r


def _ts() -> str:
    return datetime.now(UTC).isoformat()


def _record(s, user_or_actor: dict, step: str, summary: str, output: dict, rationale: str = "", scope=None) -> str:
    return governance_record(s, step=step, actor=user_or_actor, summary=summary, output=output, rationale=rationale,
                             scope=scope or [], dr_type="trading")


# ---------------------------------------------------------------------------------------------- settings
def default_settings() -> dict:
    raw = model().raw
    return {"routes": dict(raw["routes"]), "buffer_bps": float(raw.get("cash_buffer_bps", 0)), "buffer_overrides": {},
            "excluded": [], "excluded_share": "redistribute", "history": []}


def get_settings(s) -> dict:
    row = s.get(TradingSetting, "settings")
    return row.body if row else default_settings()


def _put(s, key: str, body: dict) -> None:
    row = s.get(TradingSetting, key)
    if row:
        row.body = json.loads(json.dumps(body))
    else:
        s.add(TradingSetting(key=key, body=body))


def strategic_table(s, fund_id: str) -> dict:
    row = s.get(TradingSetting, f"strategic:{fund_id}")
    m = model()
    body = row.body if row else {"follows_glide_path": True, "weights": {}, "version": 0, "history": []}
    weights = m.neutral_table(fund_id) if body.get("follows_glide_path", True) else body.get("weights", {})
    return dict(body, effective=weights)


def fund_buffer(settings: dict, fund_id: str) -> float:
    return max(float(settings.get("buffer_bps", 0)), float(settings.get("buffer_overrides", {}).get(fund_id, 0)))


def excluded_for(settings: dict, fund_id: str) -> set[str]:
    today = date.today().isoformat()
    return {e["instrument"] for e in settings.get("excluded", [])
            if e.get("fund") in ("*", fund_id) and (not e.get("until") or e["until"] >= today)}


def positions(fund_id: str) -> dict:
    return model().example_positions(fund_id)


def tables(s, fund_id: str) -> dict[str, dict]:
    m = model()
    return {"previous_close": m.previous_close_table(fund_id, positions(fund_id)["values"]),
            "neutral": m.neutral_table(fund_id), "strategic": strategic_table(s, fund_id)["effective"]}


# ---------------------------------------------------------------------------------------------- page and state
@router.get("/trading")
def trading_page(request: Request):
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login")
    auth.require_role(user, *VIEW_ROLES)
    from importlib.resources import files
    html = (files("meridian.app") / "trading.html").read_text()
    roles = user["roles"]
    boot = {"user": {"name": user["name"], "email": user.get("email", ""), "roles": roles}, "csrf": user["csrf"],
            "can_prepare": any(r in roles for r in PREPARE_ROLES), "can_approve": any(r in roles for r in APPROVE_ROLES),
            "can_settings": any(r in roles for r in SETTINGS_ROLES)}
    return HTMLResponse(html.replace("/*BOOT*/null", json.dumps(boot).replace("</", "<\\/")))


def _cashflows(s) -> list[dict]:
    return sorted((c.body for c in s.execute(select(Cashflow)).scalars()),
                  key=lambda b: (b["trade_date"], b["fund_id"], b["loaded_at"]), reverse=True)


def _trade_lists(s) -> list[dict]:
    return sorted((t.body for t in s.execute(select(TradeList)).scalars()), key=lambda b: b["created_at"], reverse=True)


@router.get("/api/trading/state")
def state(request: Request):
    user = auth.require_user(request)
    auth.require_role(user, *VIEW_ROLES)
    m = model()
    with _store().Session() as s:
        settings = get_settings(s)
        funds = []
        for fid, f in m.funds.items():
            p = positions(fid)
            funds.append(dict(f.as_dict(), cash=p["cash"], invested=sum(p["values"].values()),
                              buffer_bps=fund_buffer(settings, fid),
                              strategic_follows=strategic_table(s, fid).get("follows_glide_path", True)))
        return {"as_of": m.as_of.isoformat(), "funds": funds, "instruments": list(m.instruments.values()),
                "strategies": STRATEGIES, "vehicles": VEHICLES, "settings": settings,
                "route_names": m.raw.get("route_names", []), "sources": m.raw.get("cashflow_sources", []),
                "cashflows": _cashflows(s), "trade_lists": _trade_lists(s),
                "trading_records": [r for r in _store().ledger("governance") if r.get("dr_type") == "trading"][-200:]}


@router.get("/api/trading/funds/{fund_id}")
def fund_detail(request: Request, fund_id: str):
    user = auth.require_user(request)
    auth.require_role(user, *VIEW_ROLES)
    m = model()
    if fund_id not in m.funds:
        raise HTTPException(404, "Unknown fund")
    p = positions(fund_id)
    nav = p["cash"] + sum(p["values"].values())
    with _store().Session() as s:
        t = tables(s, fund_id)
        st = strategic_table(s, fund_id)
        excl = excluded_for(get_settings(s), fund_id)
    rows = []
    for i in m.fund_instruments(fund_id):
        v = p["values"].get(i["id"], 0.0)
        status = ("no_target" if i["status"] == "no_target" else "held" if v > 0 else
                  "candidate" if i["status"] == "candidate" else "not_held")
        rows.append({"instrument": i["id"], "name": i["name"], "type": i["type"], "asset_class": i["asset_class"],
                     "status": status, "note": i.get("note", ""), "value": v, "weight": v / nav,
                     "price": i["price"], "excluded": i["id"] in excl,
                     **{f"t_{k}": t[k].get(i["id"], 0.0) for k in STRATEGIES}})
    return {"fund": m.funds[fund_id].as_dict(), "nav": nav, "cash": p["cash"], "positions_source": p["source"],
            "as_of": p["as_of"], "rows": rows, "strategic": {k: st.get(k) for k in ("follows_glide_path", "version", "history")}}


# ---------------------------------------------------------------------------------------------- cashflows
def _machine_ok(request: Request) -> bool:
    token = os.getenv("INGEST_TOKEN")
    got = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    return bool(token and got and hmac.compare_digest(got, token))


def _parse_cashflow(row: dict, n: int) -> tuple[dict | None, str | None]:
    m = model()
    norm = {str(k or "").strip().lower().replace(" ", "_"): ("" if v is None else str(v).strip()) for k, v in row.items()}
    if not any(norm.values()):
        return None, None
    fund = norm.get("fund_id") or norm.get("fund") or norm.get("account") or ""
    accounts = {f.account: f.id for f in m.funds.values()}
    fund = accounts.get(fund, fund)
    if fund not in m.funds:
        return None, f"Row {n}: unknown fund or account '{fund}'"
    try:
        td = date.fromisoformat(norm.get("trade_date", "")[:10]).isoformat()
    except ValueError:
        return None, f"Row {n}: trade_date must look like 2026-11-10"
    try:
        amt = float(norm.get("amount", "").replace(",", "").replace("$", ""))
    except ValueError:
        return None, f"Row {n}: amount is not a number"
    typ = (norm.get("type") or ("subscription" if amt >= 0 else "redemption")).lower()
    if typ in ("purchase", "inflow", "sub"):
        typ = "subscription"
    if typ in ("outflow", "red", "withdrawal"):
        typ = "redemption"
    if typ not in CF_TYPES:
        return None, f"Row {n}: type must be subscription or redemption"
    amt = abs(amt) if typ == "subscription" else -abs(amt)
    if amt == 0:
        return None, f"Row {n}: amount is zero"
    return {"trade_date": td, "fund_id": fund, "amount": round(amt, 2), "type": typ,
            "source": norm.get("source") or "Manual entry", "reference": norm.get("reference", "")}, None


def _load_cashflows(rows: list[dict], actor: dict, how: str, file_name: str = "") -> dict:
    parsed, errors = [], []
    for n, r in enumerate(rows, start=2 if how == "file" else 1):
        cf, err = _parse_cashflow(r, n)
        if err:
            errors.append(err)
        elif cf:
            parsed.append(cf)
    if errors:
        raise HTTPException(400, "Nothing loaded. " + "; ".join(errors[:10]) + (" …" if len(errors) > 10 else ""))
    if not parsed:
        raise HTTPException(400, "No cashflow rows found")
    batch = "CFB-" + uuid.uuid4().hex[:8].upper()
    with _store().Session.begin() as s:
        ids = []
        for cf in parsed:
            cid = "CF-" + uuid.uuid4().hex[:10].upper()
            body = dict(cf, id=cid, status="new", batch=batch, loaded_by=actor, loaded_at=_ts(), how=how,
                        file_name=file_name, trade_list=None)
            s.add(Cashflow(id=cid, status="new", body=body))
            ids.append(cid)
        net = sum(c["amount"] for c in parsed)
        dr = _record(s, actor, "cashflow.load", f"{len(parsed)} cashflows loaded ({how}), net ${net:,.0f}",
                     {"batch": batch, "count": len(parsed), "net": net, "file": file_name, "ids": ids,
                      "funds": sorted({c["fund_id"] for c in parsed})},
                     scope=sorted({c["fund_id"] for c in parsed}))
    return {"loaded": len(parsed), "batch": batch, "dr_id": dr, "net": net}


@router.post("/api/trading/cashflows")
def add_cashflows(request: Request, body: dict | list = Body(...)):
    """Cashflows from a signed-in user (JSON) or from a transfer agent / custodian connection (Bearer token)."""
    rows = body if isinstance(body, list) else body.get("cashflows") or [body]
    if _machine_ok(request):
        src = rows[0].get("source") if rows and isinstance(rows[0], dict) else ""
        actor = {"name": f"API connection ({src or 'unnamed source'})", "email": ""}
        return _load_cashflows(rows, actor, "api")
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *PREPARE_ROLES)
    return _load_cashflows(rows, _who(user), "manual")


@router.post("/api/trading/cashflows/upload")
async def upload_cashflows(request: Request, file: UploadFile = File(...)):
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *PREPARE_ROLES)
    data = await file.read()
    name = file.filename or "upload"
    if len(data) > 5_000_000:
        raise HTTPException(400, "File is larger than 5 MB")
    if name.lower().endswith((".xlsx", ".xlsm")):
        try:
            from openpyxl import load_workbook
            ws = load_workbook(io.BytesIO(data), read_only=True, data_only=True).active
            it = ws.iter_rows(values_only=True)
            head = [str(h or "") for h in next(it)]
            rows = [{head[i]: (v.date().isoformat() if hasattr(v, "date") else v) for i, v in enumerate(r) if i < len(head)}
                    for r in it]
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"Could not read the Excel file: {e}") from None
    elif name.lower().endswith((".csv", ".txt")):
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    else:
        raise HTTPException(400, "Upload an Excel (.xlsx) or CSV file")
    return _load_cashflows(rows, _who(user), "file", name)


TEMPLATE = [["trade_date", "fund_id", "type", "amount", "source", "reference"],
            ["2026-11-10", "MTRS-2050", "subscription", "12500000", "SS&C (formerly DST)", "TA batch 1"],
            ["2026-11-10", "MTRS-2030", "redemption", "8000000", "SS&C (formerly DST)", "TA batch 1"],
            ["2026-11-10", "CIT2050", "subscription", "6000000", "State Street", "Plan contribution"]]


@router.get("/api/trading/cashflows/template.{ext}")
def cashflow_template(request: Request, ext: str):
    user = auth.require_user(request)
    auth.require_role(user, *VIEW_ROLES)
    if ext == "csv":
        buf = io.StringIO()
        csv.writer(buf).writerows(TEMPLATE)
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=meridian-cashflows-template.csv"})
    if ext == "xlsx":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Cashflows"
        for r in TEMPLATE:
            ws.append([float(x) if r is not TEMPLATE[0] and i == 3 else x for i, x in enumerate(r)])
        out = io.BytesIO()
        wb.save(out)
        return Response(out.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": "attachment; filename=meridian-cashflows-template.xlsx"})
    raise HTTPException(404, "Use .csv or .xlsx")


@router.post("/api/trading/cashflows/{cid}/cancel")
def cancel_cashflow(request: Request, cid: str, body: dict = Body(...)):
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *PREPARE_ROLES)
    reason = _reason(body)
    with _store().Session.begin() as s:
        row = s.get(Cashflow, cid)
        if not row:
            raise HTTPException(404, "Unknown cashflow")
        if row.status != "new":
            raise HTTPException(409, "Only cashflows not yet in a trade list can be cancelled")
        b = dict(row.body, status="cancelled", cancelled_by=_who(user), cancel_reason=reason)
        row.body, row.status = b, "cancelled"
        _record(s, _who(user), "cashflow.cancel", f"{cid} cancelled", {"id": cid, "amount": b["amount"],
                "fund_id": b["fund_id"]}, reason, [b["fund_id"]])
    return {"ok": True}


# ---------------------------------------------------------------------------------------------- targets and settings
@router.put("/api/trading/targets/{fund_id}/strategic")
def set_strategic(request: Request, fund_id: str, body: dict = Body(...)):
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *APPROVE_ROLES)
    m = model()
    if fund_id not in m.funds:
        raise HTTPException(404, "Unknown fund")
    reason = _reason(body)
    follows = bool(body.get("follows_glide_path"))
    weights = {}
    if not follows:
        allowed = {i["id"] for i in m.fund_instruments(fund_id) if i["status"] != "no_target"}
        try:
            weights = {k: float(v) for k, v in (body.get("weights") or {}).items() if float(v) != 0}
        except (TypeError, ValueError):
            raise HTTPException(400, "Weights must be numbers") from None
        bad = sorted(set(weights) - allowed)
        if bad:
            raise HTTPException(400, f"Not allowed in this fund's table: {', '.join(bad)}")
        if any(v < 0 for v in weights.values()):
            raise HTTPException(400, "Weights can't be negative")
        tot = sum(weights.values())
        if abs(tot - 1) > 0.0001:
            raise HTTPException(400, f"Weights add up to {tot * 100:.2f}%, not 100%")
    with _store().Session.begin() as s:
        cur = strategic_table(s, fund_id)
        ver = int(cur.get("version", 0)) + 1
        hist = list(cur.get("history", [])) + [{"at": _ts(), "by": _who(user), "version": ver, "reason": reason,
                                                 "follows_glide_path": follows}]
        _put(s, f"strategic:{fund_id}", {"follows_glide_path": follows, "weights": weights, "version": ver,
                                         "history": hist[-50:]})
        dr = _record(s, _who(user), "targets.strategic", f"Strategic table for {fund_id} v{ver}: "
                     + ("follows the glide path" if follows else "custom weights"),
                     {"fund_id": fund_id, "version": ver, "follows_glide_path": follows, "weights": weights,
                      "before": {"follows_glide_path": cur.get("follows_glide_path", True),
                                 "weights": cur.get("effective")}}, reason, [fund_id])
    return {"ok": True, "version": ver, "dr_id": dr}


@router.put("/api/trading/settings")
def set_settings(request: Request, body: dict = Body(...)):
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *SETTINGS_ROLES)
    reason = _reason(body)
    m = model()
    with _store().Session.begin() as s:
        cur = get_settings(s)
        new = json.loads(json.dumps(cur))
        changes = {}
        if "routes" in body:
            names = set(m.raw.get("route_names", []))
            r = {k: str(v) for k, v in (body["routes"] or {}).items()}
            if set(r) - set(cur["routes"]) or any(v not in names for v in r.values()):
                raise HTTPException(400, f"Routes must be one of: {', '.join(sorted(names))}")
            new["routes"].update(r)
        if "buffer_bps" in body:
            b = float(body["buffer_bps"])
            if not 0 <= b <= 500:
                raise HTTPException(400, "Cash buffer must be between 0 and 500 bp")
            new["buffer_bps"] = b
        if "buffer_overrides" in body:
            ov = {k: float(v) for k, v in (body["buffer_overrides"] or {}).items() if v not in (None, "")}
            if set(ov) - set(m.funds):
                raise HTTPException(400, "Unknown fund in buffer overrides")
            new["buffer_overrides"] = ov
        if "excluded" in body:
            ex = []
            for e in body["excluded"] or []:
                if e.get("instrument") not in m.instruments or e.get("fund", "*") not in set(m.funds) | {"*"}:
                    raise HTTPException(400, f"Unknown security or fund in exclusion: {e}")
                ex.append({"instrument": e["instrument"], "fund": e.get("fund", "*"),
                           "reason": str(e.get("reason", "")).strip() or reason, "until": e.get("until") or "",
                           "by": e.get("by") or _who(user), "at": e.get("at") or _ts()})
            new["excluded"] = ex
        if "excluded_share" in body:
            if body["excluded_share"] not in ("redistribute", "cash"):
                raise HTTPException(400, "excluded_share must be redistribute or cash")
            new["excluded_share"] = body["excluded_share"]
        for k in ("routes", "buffer_bps", "buffer_overrides", "excluded", "excluded_share"):
            if new.get(k) != cur.get(k):
                changes[k] = {"before": cur.get(k), "after": new.get(k)}
        if not changes:
            raise HTTPException(400, "Nothing changed")
        new["history"] = (list(cur.get("history", [])) + [{"at": _ts(), "by": _who(user), "reason": reason,
                                                           "changed": sorted(changes)}])[-100:]
        _put(s, "settings", new)
        dr = _record(s, _who(user), "settings.change", "Trading settings changed: " + ", ".join(sorted(changes)),
                     changes, reason)
    return {"ok": True, "dr_id": dr, "changed": sorted(changes)}


# ---------------------------------------------------------------------------------------------- trade lists
def _run_context():
    """Latest run: neutral weights and covariance per vintage for post-trade compliance, if a run exists."""
    st = _store()
    rid = st.latest_run_id()
    run = st.get_run(rid) if rid else None
    if not run:
        return None
    res = run.results
    return {"run_id": rid, "assets": res["model"]["assets"], "cov": np.array(res["model"]["cov"]),
            "neutral": {int(v): d["neutral"] for v, d in res["vintages"].items()},
            "rb": {int(v): d.get("risk_budget") for v, d in res["vintages"].items()}}


def _compliance(fund_id: str, rows: list[dict], ctx) -> dict:
    if not ctx:
        return {"status": "NOT RUN", "detail": "No agent run published yet, so the IPS check needs a run's risk model",
                "results": []}
    from ..compliance import evaluate, summarize
    from ..entities import resolve
    from ..policy import load_universe
    m = model()
    f = m.funds[fund_id]
    acw = asset_class_weights(m, rows)
    assets = ctx["assets"]
    w = np.array([acw.get(a, 0.0) for a in assets])
    fn = m.neutral_asset_weights(fund_id)          # the fund's own glide-path point on its roll-down schedule
    n = np.array([fn.get(a, 0.0) for a in assets])
    res = evaluate(w, n, ctx["cov"], m.policy, resolve(), load_universe(), risk_budget=ctx["rb"].get(f.vintage))
    summ = summarize(res)
    hard = [r.to_dict() for r in res if r.status in ("FAIL", "WARN")]
    return {"status": summ["overall"], "counts": summ,
            "run_id": ctx["run_id"], "results": hard, "asset_class_post": acw,
            "detail": f"Post-trade asset-class weights checked against the IPS rules vs this fund's glide path ({f.roll_down} roll-down)"}


@router.post("/api/trading/trade-lists")
def generate(request: Request, body: dict = Body(...)):
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *PREPARE_ROLES)
    m = model()
    strategy = body.get("strategy", "previous_close")
    if strategy not in STRATEGIES:
        raise HTTPException(400, f"Strategy must be one of: {', '.join(STRATEGIES)}")
    try:
        td = date.fromisoformat(str(body.get("trade_date", ""))[:10]).isoformat()
    except ValueError:
        raise HTTPException(400, "trade_date must look like 2026-11-10") from None
    vehicle = body.get("vehicle", "all")
    funds_in = set(m.fund_ids(vehicle))
    ctx = _run_context()
    with _store().Session.begin() as s:
        settings = get_settings(s)
        cfs = [c for c in s.execute(select(Cashflow).where(Cashflow.status == "new")).scalars()
               if c.body["trade_date"] == td and c.body["fund_id"] in funds_in]
        if not cfs:
            raise HTTPException(400, f"No new cashflows for {td}" + ("" if vehicle == "all" else f" ({VEHICLES[vehicle]})"))
        net: dict[str, float] = {}
        for c in cfs:
            net[c.body["fund_id"]] = net.get(c.body["fund_id"], 0.0) + c.body["amount"]
        tl_id = "TL-" + td.replace("-", "")[2:] + "-" + uuid.uuid4().hex[:4].upper()
        out_funds = []
        for fid in sorted(net, key=lambda x: (m.funds[x].vehicle, m.funds[x].vintage)):
            pos = positions(fid)
            table = tables(s, fid)[strategy]
            r = allocate_fund(m, fid, net[fid], pos, table, routes=settings["routes"],
                              excluded=excluded_for(settings, fid), excluded_share=settings.get("excluded_share", "redistribute"),
                              buffer_bps=fund_buffer(settings, fid))
            r["compliance"] = _compliance(fid, r["preview"], ctx)
            r["vehicle"] = m.funds[fid].vehicle
            r["cashflows"] = [c.id for c in cfs if c.body["fund_id"] == fid]
            r["buffer_bps"] = fund_buffer(settings, fid)
            out_funds.append(r)
        orders = sum(len(f["orders"]) for f in out_funds)
        blocked = [f["fund_id"] for f in out_funds if f["errors"] or f["compliance"]["status"] == "FAIL"]
        body_tl = {"id": tl_id, "status": "draft", "trade_date": td, "strategy": strategy,
                   "strategy_name": STRATEGIES[strategy], "vehicle": vehicle, "created_by": _who(user),
                   "created_at": _ts(), "funds": out_funds, "order_count": orders, "blocked_funds": blocked,
                   "gross": round(sum(abs(o["est_amount"]) for f in out_funds for o in f["orders"]), 2),
                   "net_flow": round(sum(net.values()), 2), "settings_used": {
                       "routes": settings["routes"], "buffer_bps": settings["buffer_bps"],
                       "excluded": settings.get("excluded", []), "excluded_share": settings.get("excluded_share")},
                   "history": [{"at": _ts(), "by": _who(user), "action": "generate", "note": ""}]}
        dr = _record(s, _who(user), "trades.generate",
                     f"{tl_id}: {orders} orders for {len(out_funds)} funds from {len(cfs)} cashflows ({STRATEGIES[strategy]})",
                     {"trade_list": tl_id, "trade_date": td, "strategy": strategy, "net_flow": body_tl["net_flow"],
                      "orders": [dict(o, fund_id=f["fund_id"]) for f in out_funds for o in f["orders"]],
                      "compliance": {f["fund_id"]: f["compliance"]["status"] for f in out_funds},
                      "cashflows": [c.id for c in cfs], "settings_used": body_tl["settings_used"]},
                     f"Pro rata allocation of net cashflows using the {STRATEGIES[strategy]} table", sorted(net))
        body_tl["dr_ids"] = [dr]
        s.add(TradeList(id=tl_id, status="draft", body=body_tl))
        for c in cfs:
            c.body = dict(c.body, status="in_trade_list", trade_list=tl_id)
            c.status = "in_trade_list"
    return body_tl


def _get_tl(s, tid: str) -> TradeList:
    row = s.get(TradeList, tid)
    if not row:
        raise HTTPException(404, "Unknown trade list")
    return row


@router.get("/api/trading/trade-lists/{tid}")
def get_trade_list(request: Request, tid: str):
    user = auth.require_user(request)
    auth.require_role(user, *VIEW_ROLES)
    with _store().Session() as s:
        return _get_tl(s, tid).body


@router.post("/api/trading/trade-lists/{tid}/approve")
def approve(request: Request, tid: str, body: dict = Body(...)):
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *APPROVE_ROLES)
    if not body.get("checked"):
        raise HTTPException(400, "Confirm you reviewed the post-trade preview and compliance")
    reason = _reason(body)
    with _store().Session.begin() as s:
        row = _get_tl(s, tid)
        b = dict(row.body)
        if b["status"] != "draft":
            raise HTTPException(409, f"Trade list is {b['status']}, not draft")
        if b["blocked_funds"]:
            raise HTTPException(409, "Blocked: " + ", ".join(b["blocked_funds"]) + " have errors or a compliance FAIL")
        self_approved = b["created_by"].get("email") == user.get("email") and b["created_by"].get("name") == user["name"]
        dr = _record(s, _who(user), "trades.approve", f"{tid} approved ({b['order_count']} orders)",
                     {"trade_list": tid, "self_approved": self_approved, "orders": b["order_count"]}, reason,
                     [f["fund_id"] for f in b["funds"]])
        b.update(status="approved", approved_by=_who(user), approved_at=_ts(), approve_reason=reason,
                 self_approved=self_approved, dr_ids=b["dr_ids"] + [dr],
                 history=b["history"] + [{"at": _ts(), "by": _who(user), "action": "approve", "note": reason}])
        row.body, row.status = b, "approved"
    return {"ok": True, "dr_id": dr, "self_approved": self_approved}


@router.post("/api/trading/trade-lists/{tid}/cancel")
def cancel(request: Request, tid: str, body: dict = Body(...)):
    user = auth.require_user(request)
    auth.check_csrf(request, user)
    auth.require_role(user, *PREPARE_ROLES)
    reason = _reason(body)
    with _store().Session.begin() as s:
        row = _get_tl(s, tid)
        b = dict(row.body)
        if b["status"] not in ("draft", "approved"):
            raise HTTPException(409, "Exported trade lists can't be cancelled here; cancel the orders in Charles River")
        cf_ids = [c for f in b["funds"] for c in f["cashflows"]]
        for c in s.execute(select(Cashflow).where(Cashflow.id.in_(cf_ids))).scalars():
            c.body = dict(c.body, status="new", trade_list=None)
            c.status = "new"
        dr = _record(s, _who(user), "trades.cancel", f"{tid} cancelled; {len(cf_ids)} cashflows released",
                     {"trade_list": tid, "cashflows": cf_ids}, reason)
        b.update(status="cancelled", dr_ids=b["dr_ids"] + [dr],
                 history=b["history"] + [{"at": _ts(), "by": _who(user), "action": "cancel", "note": reason}])
        row.body, row.status = b, "cancelled"
    return {"ok": True}


@router.get("/api/trading/trade-lists/{tid}/crd.csv")
def crd_file(request: Request, tid: str):
    user = auth.require_user(request)
    auth.require_role(user, *PREPARE_ROLES)
    with _store().Session.begin() as s:
        row = _get_tl(s, tid)
        b = dict(row.body)
        if b["status"] not in ("approved", "exported"):
            raise HTTPException(409, "Approve the trade list before exporting it for Charles River")
        rows = crd_rows(b, model())
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=CRD_COLUMNS)
        w.writeheader()
        w.writerows(rows)
        text = buf.getvalue()
        import hashlib
        digest = hashlib.sha256(text.encode()).hexdigest()
        dr = _record(s, _who(user), "trades.export", f"{tid} exported for Charles River ({len(rows)} orders)",
                     {"trade_list": tid, "orders": len(rows), "sha256": digest, "format": "Charles River import (mock)"},
                     "Export of the approved trade list", [f["fund_id"] for f in b["funds"]])
        exports = list(b.get("exports", [])) + [{"at": _ts(), "by": _who(user), "sha256": digest, "dr_id": dr}]
        b.update(status="exported", exports=exports, dr_ids=b["dr_ids"] + [dr],
                 history=b["history"] + [{"at": _ts(), "by": _who(user), "action": "export", "note": digest[:12]}])
        row.body, row.status = b, "exported"
    return Response(text, media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=charles-river-import-{tid}.csv"})
