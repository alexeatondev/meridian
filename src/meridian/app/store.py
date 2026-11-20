"""Database store for the hosted app (SQLite locally, PostgreSQL on AWS).

Runs, their hash-chained decision records, positions history, governance change requests and
policy overrides live here. Business logic is reused unchanged: a run is materialized into a
temporary working directory, the existing file-based functions run on it, and the results are
written back inside one locked transaction.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint, create_engine,
                        select)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()


def now():
    return datetime.now(timezone.utc)


class Run(Base):
    __tablename__ = "runs"
    id = Column(String(64), primary_key=True)
    as_of = Column(String(10), index=True)
    created_at = Column(DateTime(timezone=True), default=now)
    source = Column(String(32), default="ingest")          # ingest | local
    results = Column(JSON)
    board_memo = Column(Text)
    compliance_report = Column(Text)


class LedgerRecord(Base):
    __tablename__ = "ledger_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), index=True)                # "governance" for the governance chain
    seq = Column(Integer)
    dr_id = Column(String(64), index=True)
    record = Column(JSON)
    record_hash = Column(String(64))
    __table_args__ = (UniqueConstraint("run_id", "seq"),)


class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    as_of = Column(String(10), index=True)
    vintage = Column(Integer, index=True)
    asset = Column(String(64))
    weight = Column(Float)
    run_id = Column(String(64))
    status = Column(String(16))


class ChangeRequest(Base):
    __tablename__ = "change_requests"
    id = Column(String(32), primary_key=True)
    body = Column(JSON)
    status = Column(String(16), index=True)


class AccessEvent(Base):
    """Every change to a user's access, made in the User access screen. Append-only (doc 05 §4)."""
    __tablename__ = "access_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    at = Column(DateTime(timezone=True), default=now, nullable=False)
    actor = Column(JSON, nullable=False)           # {name, email, sub}
    action = Column(String(40), nullable=False)    # create | set_access | rename | disable | enable | resend_invite | delete
    target = Column(String(320), nullable=False)   # the user's email
    before = Column(JSON)
    after = Column(JSON)
    reason = Column(Text, nullable=False)


class DevUser(Base):
    """User directory for development sign-in and tests only (production uses Cognito)."""
    __tablename__ = "dev_users"
    email = Column(String(320), primary_key=True)
    name = Column(String(200), nullable=False)
    roles = Column(JSON, nullable=False, default=list)
    enabled = Column(Boolean, nullable=False, default=True)
    status = Column(String(40), nullable=False, default="FORCE_CHANGE_PASSWORD")
    created = Column(DateTime(timezone=True), default=now, nullable=False)


class SecurityEvent(Base):
    """Security-relevant events: sign-in and sign-out, failed sign-ins, expired or revoked sessions, refused
    requests (403), CSRF failures, bad machine tokens, direct hits on the load balancer. Append-only
    (NIST SP 800-53 AU-2, AU-3, AU-9); reviewed on User access → Security log (AU-6)."""
    __tablename__ = "security_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    at = Column(DateTime(timezone=True), default=now, nullable=False, index=True)
    kind = Column(String(40), nullable=False, index=True)     # e.g. signin.success, access.denied
    outcome = Column(String(12), nullable=False)               # success | failure | denied | info
    user_id = Column(String(320))                              # Cognito sub (or dev id)
    email = Column(String(320), index=True)
    name = Column(String(200))
    ip = Column(String(64))
    user_agent = Column(String(300))
    method = Column(String(10))
    path = Column(String(300))
    detail = Column(JSON)


class SessionRevocation(Base):
    """Sessions issued before `revoked_at` for this email are no longer accepted (access changed)."""
    __tablename__ = "session_revocations"
    email = Column(String(320), primary_key=True)
    revoked_at = Column(DateTime(timezone=True), nullable=False)


class PolicyOverride(Base):
    __tablename__ = "policy_overrides"
    key = Column(String(128), primary_key=True)            # e.g. risk_budgets.vintages.2050
    value = Column(JSON)
    cr_id = Column(String(32))
    updated_at = Column(DateTime(timezone=True), default=now)


class Store:
    def __init__(self, url: str | None = None):
        url = url or os.getenv("MERIDIAN_DB_URL") or db_url_from_env() or "sqlite:///./meridian-app.db"
        kw = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kw["connect_args"] = {"check_same_thread": False}
        self.engine = create_engine(url, **kw)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        self._protect_ledger()

    def _protect_ledger(self) -> None:
        """Make ledger_records and access_events append-only in the database itself (doc 05 §3, REC-2).

        Any UPDATE or DELETE on these records is rejected by a trigger, whoever issues it. Idempotent.
        """
        for table in ("ledger_records", "access_events", "security_events"):
            self._append_only(table)

    def _append_only(self, table: str) -> None:
        from sqlalchemy import text
        dialect = self.engine.dialect.name
        with self.engine.begin() as c:
            if dialect == "postgresql":
                c.execute(text("""
                    CREATE OR REPLACE FUNCTION meridian_ledger_append_only() RETURNS trigger AS $$
                    BEGIN
                      RAISE EXCEPTION '% is append-only: % is not allowed', TG_TABLE_NAME, TG_OP;
                    END; $$ LANGUAGE plpgsql"""))
                if table == "ledger_records":   # names used before 2026-11-10
                    c.execute(text("DROP TRIGGER IF EXISTS ledger_append_only ON ledger_records"))
                    c.execute(text("DROP TRIGGER IF EXISTS ledger_no_truncate ON ledger_records"))
                c.execute(text(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}"))
                c.execute(text(f"""CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table}
                                  FOR EACH ROW EXECUTE FUNCTION meridian_ledger_append_only()"""))
                c.execute(text(f"DROP TRIGGER IF EXISTS {table}_no_truncate ON {table}"))
                c.execute(text(f"""CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table}
                                  FOR EACH STATEMENT EXECUTE FUNCTION meridian_ledger_append_only()"""))
            elif dialect == "sqlite":
                for op in ("UPDATE", "DELETE"):
                    c.execute(text(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_{op.lower()} BEFORE {op} ON {table}
                                      BEGIN SELECT RAISE(ABORT, '{table} is append-only: {op} is not allowed'); END"""))

    # ------------------------------------------------------------------ runs
    def ingest_run(self, run_dir: Path, source: str = "ingest") -> str:
        run_dir = Path(run_dir)
        res = json.loads((run_dir / "results.json").read_text())
        recs = [json.loads(l) for l in (run_dir / "ledger.jsonl").read_text().splitlines() if l.strip()]
        with self.Session.begin() as s:
            if s.get(Run, res["run_id"]):
                raise ValueError(f"run {res['run_id']} already ingested")
            s.add(Run(id=res["run_id"], as_of=res["as_of"], results=res, source=source,
                      board_memo=(run_dir / "board_memo.md").read_text(),
                      compliance_report=(run_dir / "compliance_report.md").read_text()))
            for i, r in enumerate(recs):
                s.add(LedgerRecord(run_id=res["run_id"], seq=i, dr_id=r["dr_id"], record=r, record_hash=r["record_hash"]))
            for v, d in res["vintages"].items():
                for a, w in d["final"].items():
                    s.add(Position(as_of=res["as_of"], vintage=int(v), asset=a, weight=float(w),
                                   run_id=res["run_id"], status="proposed"))
        return res["run_id"]

    def list_runs(self) -> list[dict]:
        with self.Session() as s:
            rows = s.execute(select(Run.id, Run.as_of, Run.created_at, Run.source).order_by(Run.as_of.desc(), Run.created_at.desc())).all()
            return [{"id": r.id, "as_of": r.as_of, "created_at": r.created_at.isoformat() if r.created_at else None,
                     "source": r.source} for r in rows]

    def get_run(self, run_id: str) -> Run | None:
        with self.Session() as s:
            return s.get(Run, run_id)

    def latest_run_id(self) -> str | None:
        runs = self.list_runs()
        return runs[0]["id"] if runs else None

    def ledger(self, run_id: str) -> list[dict]:
        with self.Session() as s:
            return [r.record for r in s.execute(select(LedgerRecord).where(LedgerRecord.run_id == run_id)
                                                .order_by(LedgerRecord.seq)).scalars()]

    @contextlib.contextmanager
    def run_workspace(self, run_id: str):
        """Materialize a run into a temp dir; on success write back results + any new ledger records atomically."""
        tmp = Path(tempfile.mkdtemp(prefix="meridian-run-"))
        try:
            with self.Session.begin() as s:
                q = select(Run).where(Run.id == run_id)
                if self.engine.dialect.name == "postgresql":
                    q = q.with_for_update()
                run = s.execute(q).scalar_one_or_none()
                if run is None:
                    raise KeyError(run_id)
                recs = [r.record for r in s.execute(select(LedgerRecord).where(LedgerRecord.run_id == run_id)
                                                    .order_by(LedgerRecord.seq)).scalars()]
                (tmp / "results.json").write_text(json.dumps(run.results, default=str))
                (tmp / "ledger.jsonl").write_text("".join(json.dumps(r, default=str) + "\n" for r in recs))
                n0 = len(recs)
                yield tmp
                run.results = json.loads((tmp / "results.json").read_text())
                new = [json.loads(l) for l in (tmp / "ledger.jsonl").read_text().splitlines() if l.strip()][n0:]
                for i, r in enumerate(new):
                    s.add(LedgerRecord(run_id=run_id, seq=n0 + i, dr_id=r["dr_id"], record=r, record_hash=r["record_hash"]))
                for r in new:   # approved positions become the reference for "last week / last month"
                    if r["dr_type"] == "approval" and r["step"] == "approval.decision":
                        self._maybe_mark_approved(s, run, r)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _maybe_mark_approved(self, s: Session, run: Run, rec: dict) -> None:
        v = int(rec["portfolio_scope"][0].split("-")[1])
        d = run.results["vintages"][str(v)]
        needed = set(d["approvers"]) | set((d.get("adjusted") or {}).get("approvers", []))
        decided = {r.record["approvals"][0]["role"] for r in s.execute(select(LedgerRecord).where(
            LedgerRecord.run_id == run.id)).scalars()
                   if r.record["step"] == "approval.decision" and f"MTRS-{v}" in r.record["portfolio_scope"]
                   and r.record["approvals"][0]["decision"] == "approve"} | (
            {rec["approvals"][0]["role"]} if rec["approvals"][0]["decision"] == "approve" else set())
        if needed <= decided:
            final = (d.get("adjusted") or {}).get("final") or d["final"]
            for a, w in final.items():
                s.add(Position(as_of=run.as_of, vintage=v, asset=a, weight=float(w), run_id=run.id, status="approved"))

    def positions_csv(self, path: Path) -> Path:
        import pandas as pd
        with self.Session() as s:
            rows = [{"as_of": p.as_of, "vintage": p.vintage, "asset": p.asset, "weight": p.weight,
                     "run_id": p.run_id, "status": p.status} for p in s.execute(select(Position)).scalars()]
        pd.DataFrame(rows, columns=["as_of", "vintage", "asset", "weight", "run_id", "status"]).to_csv(path, index=False)
        return path

    def risk_history_csv(self, path: Path) -> Path:
        """Point-in-time risk snapshots recorded by every ingested run (one row per run, vintage, metric)."""
        import pandas as pd
        cols = ["as_of", "vintage", "run_id", "source", "metric", "value"]
        rows = []
        with self.Session() as s:
            for run in s.execute(select(Run)).scalars():
                for v, d in ((run.results or {}).get("vintages") or {}).items():
                    ra = d.get("risk_analytics")
                    if not ra:
                        continue
                    for k, val in ra["metrics"].items():
                        if isinstance(val, (int, float)) and not k.startswith("var_"):
                            rows.append([run.as_of, int(v), run.id, "recorded", k, float(val)])
                    for f in ra["factors"]["total"]["factors"]:
                        rows.append([run.as_of, int(v), run.id, "recorded", f"factor:{f['id']}", float(f["pct"])])
                    rows.append([run.as_of, int(v), run.id, "recorded", "factor:specific",
                                 float(ra["factors"]["total"]["specific"]["pct"])])
        pd.DataFrame(rows, columns=cols).to_csv(path, index=False)
        return path

    # ------------------------------------------------------------------ governance
    @contextlib.contextmanager
    def governance_workspace(self, policy_path: Path):
        tmp = Path(tempfile.mkdtemp(prefix="meridian-gov-"))
        try:
            with self.Session.begin() as s:
                crs = {c.id: c.body for c in s.execute(select(ChangeRequest)).scalars()}
                recs = [r.record for r in s.execute(select(LedgerRecord).where(LedgerRecord.run_id == "governance")
                                                    .order_by(LedgerRecord.seq)).scalars()]
                gov = tmp / "gov"
                gov.mkdir()
                (gov / "change_requests.json").write_text(json.dumps(crs))
                (gov / "ledger.jsonl").write_text("".join(json.dumps(r, default=str) + "\n" for r in recs))
                pol = tmp / "policy.yaml"
                self.write_effective_policy(policy_path, pol, s)
                n0 = len(recs)
                yield gov, pol
                for cid, body in json.loads((gov / "change_requests.json").read_text()).items():
                    row = s.get(ChangeRequest, cid)
                    if row is None:
                        s.add(ChangeRequest(id=cid, body=body, status=body["status"]))
                    else:
                        row.body, row.status = body, body["status"]
                    if body["status"] == "applied":
                        key = f"risk_budgets.{'default' if body['target']['vintage'] == 'default' else 'vintages.' + str(body['target']['vintage'])}"
                        o = s.get(PolicyOverride, key)
                        if o is None or o.cr_id != cid:
                            if o is None:
                                s.add(PolicyOverride(key=key, value=body["proposed"], cr_id=cid))
                            else:
                                o.value, o.cr_id, o.updated_at = body["proposed"], cid, now()
                new = [json.loads(l) for l in (gov / "ledger.jsonl").read_text().splitlines() if l.strip()][n0:]
                for i, r in enumerate(new):
                    s.add(LedgerRecord(run_id="governance", seq=n0 + i, dr_id=r["dr_id"], record=r, record_hash=r["record_hash"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def log_access(self, actor: dict, action: str, target: str, before, after, reason: str) -> None:
        with self.Session.begin() as s:
            s.add(AccessEvent(actor={k: actor.get(k) for k in ("name", "email", "sub")}, action=action,
                              target=target, before=before, after=after, reason=reason))

    def log_security(self, **e) -> None:
        with self.Session.begin() as s:
            s.add(SecurityEvent(**e))

    def security_events(self, limit: int = 1000, kind: str = "", email: str = "", since=None) -> list[dict]:
        with self.Session() as s:
            q = select(SecurityEvent).order_by(SecurityEvent.id.desc())
            if kind:
                q = q.where(SecurityEvent.kind.startswith(kind))
            if email:
                q = q.where(SecurityEvent.email == email.lower())
            if since is not None:
                q = q.where(SecurityEvent.at >= since)
            return [{"id": e.id, "at": e.at.isoformat(), "kind": e.kind, "outcome": e.outcome, "user_id": e.user_id,
                     "email": e.email, "name": e.name, "ip": e.ip, "user_agent": e.user_agent, "method": e.method,
                     "path": e.path, "detail": e.detail or {}} for e in s.execute(q.limit(limit)).scalars()]

    def last_signins(self) -> dict[str, str]:
        """Most recent successful sign-in per email (for inactive-account review, AC-2(3))."""
        from sqlalchemy import func
        with self.Session() as s:
            q = (select(SecurityEvent.email, func.max(SecurityEvent.at)).where(SecurityEvent.kind == "signin.success")
                 .group_by(SecurityEvent.email))
            return {e: (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).isoformat() for e, t in s.execute(q) if e}

    def revoke_sessions(self, email: str) -> None:
        with self.Session.begin() as s:
            row = s.get(SessionRevocation, email.lower())
            if row:
                row.revoked_at = now()
            else:
                s.add(SessionRevocation(email=email.lower(), revoked_at=now()))

    def revoked_after(self, email: str) -> float | None:
        if not email:
            return None
        with self.Session() as s:
            row = s.get(SessionRevocation, email.lower())
            if not row:
                return None
            t = row.revoked_at
            return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).timestamp()

    def access_events(self, limit: int = 500) -> list[dict]:
        with self.Session() as s:
            q = select(AccessEvent).order_by(AccessEvent.id.desc()).limit(limit)
            return [{"id": e.id, "at": e.at.isoformat(), "actor": e.actor, "action": e.action, "target": e.target,
                     "before": e.before, "after": e.after, "reason": e.reason} for e in s.execute(q).scalars()]

    def overrides(self) -> dict:
        with self.Session() as s:
            return {o.key: o.value for o in s.execute(select(PolicyOverride)).scalars()}

    def change_requests(self) -> list[dict]:
        with self.Session() as s:
            return [c.body for c in s.execute(select(ChangeRequest)).scalars()]

    def write_effective_policy(self, src: Path, dst: Path, s: Session | None = None) -> Path:
        """Repo policy + approved operating overrides (risk budgets) = the effective policy."""
        from ruamel.yaml import YAML
        y = YAML()
        y.preserve_quotes = True
        doc = y.load(Path(src).read_text())
        ovs = ({o.key: o.value for o in s.execute(select(PolicyOverride)).scalars()} if s is not None else self.overrides())
        apply_overrides(doc, ovs)
        with open(dst, "w") as f:
            y.dump(doc, f)
        return dst


def apply_overrides(doc, overrides: dict) -> None:
    for key, val in overrides.items():
        parts = key.split(".")
        node = doc
        for p in parts[:-1]:
            p2 = int(p) if p.isdigit() else p
            if node.get(p2) is None:
                node[p2] = {}
            node = node[p2]
        last = parts[-1]
        node[int(last) if last.isdigit() else last] = val


def db_url_from_env() -> str | None:
    """On AWS the database credentials arrive as the RDS-generated JSON secret in DB_SECRET."""
    raw = os.getenv("DB_SECRET")
    if not raw:
        return None
    d = json.loads(raw)
    from urllib.parse import quote_plus
    return (f"postgresql+psycopg://{quote_plus(d['username'])}:{quote_plus(d['password'])}"
            f"@{d['host']}:{d.get('port', 5432)}/{d.get('dbname', 'meridian')}"
            "?sslmode=require")          # encrypted connection to RDS (800-53 SC-8); the server also forces TLS
