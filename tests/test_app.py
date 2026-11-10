"""Hosted app: auth, roles, ingest, approvals, adjustments, risk-budget change requests (SQLite, dev auth)."""
import io
import json
import tarfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_AUTH", "dev")
    monkeypatch.setenv("MERIDIAN_DB_URL", f"sqlite:///{tmp_path}/app.db")
    monkeypatch.setenv("INGEST_TOKEN", "test-ingest-token")
    import meridian.app.main as m
    m._store = None
    return TestClient(m.app)


def bundle(run_dir):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for f in ("results.json", "ledger.jsonl", "board_memo.md", "compliance_report.md"):
            tf.add(run_dir / f, arcname=f"{run_dir.name}/{f}")
    return buf.getvalue()


def login(c, name, *roles):
    c.cookies.clear()
    r = c.post("/dev-login", data={"name": name, "roles": list(roles)}, follow_redirects=False)
    assert r.status_code == 303
    from meridian.app import auth
    sess = auth._serializer().loads(c.cookies.get(auth.SESSION_COOKIE))
    return {"X-CSRF-Token": sess["csrf"]}


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    from meridian.pipelines.target_date import run
    return run(out_root=tmp_path_factory.mktemp("runs")).out_dir


def test_end_to_end(client, run_dir):
    # unauthenticated -> login; machine endpoints need token
    assert client.get("/runs/latest", follow_redirects=False).status_code in (302, 307)
    assert client.post("/api/ingest", files={"bundle": ("b.tgz", bundle(run_dir))}).status_code == 401
    r = client.post("/api/ingest", headers={"Authorization": "Bearer test-ingest-token"},
                    files={"bundle": ("b.tgz", bundle(run_dir))})
    assert r.status_code == 200, r.text
    rid = r.json()["run_id"]
    assert client.post("/api/ingest", headers={"Authorization": "Bearer test-ingest-token"},
                       files={"bundle": ("b.tgz", bundle(run_dir))}).status_code == 409

    h = login(client, "Pat PM", "portfolio_manager")
    page = client.get("/runs/latest")
    assert page.status_code == 200 and '"console_roles": ["pm"]' in page.text and rid in page.text

    # CSRF required
    assert client.post(f"/api/runs/{rid}/approvals", json={"vintage": 2050, "role": "portfolio_manager",
                       "decision": "approve", "reason": "fine and within budget"}).status_code == 403
    # cannot act as a role you don't hold
    assert client.post(f"/api/runs/{rid}/approvals", headers=h, json={"vintage": 2050, "role": "risk",
                       "decision": "approve", "reason": "pretending to be risk"}).status_code == 403
    # adjustment by PM
    r = client.post(f"/api/runs/{rid}/adjustments", headers=h, json={"vintage": 2050, "reason": "Shorten duration a bit.",
                    "specs": ["Fixed Income/Short-dated=+1pp from Fixed Income/Long-dated"]})
    assert r.status_code == 200 and r.json()["compliance_summary"]["FAIL"] == 0, r.text
    assert client.post(f"/api/runs/{rid}/approvals", headers=h, json={"vintage": 2050, "role": "portfolio_manager",
                       "decision": "approve", "reason": "Adjusted proposal reviewed."}).status_code == 200
    # risk approves -> positions recorded as approved
    h2 = login(client, "Riley Risk", "risk")
    assert client.post(f"/api/runs/{rid}/approvals", headers=h2, json={"vintage": 2050, "role": "risk",
                       "decision": "approve", "reason": "Within the 1.2% budget."}).status_code == 200
    import meridian.app.main as m
    from sqlalchemy import select
    from meridian.app.store import Position
    with m.store().Session() as s:
        assert s.execute(select(Position).where(Position.status == "approved", Position.vintage == 2050)).scalars().first()
    # ledger remains intact after API writes
    led = m.store().ledger(rid)
    ok, msg = m._verify_records(led)
    assert ok and any(r["step"] == "pm.adjustment" for r in led)

    # risk budget change request: PM requests, PM can't self-approve, risk + another PM approve -> override
    h = login(client, "Pat PM", "portfolio_manager")
    cr = client.post("/api/risk-budget/requests", headers=h, json={"vintage": "2050", "te": 0.01,
                     "reason": "Tighter budget in this regime."}).json()
    assert cr["status"] == "pending"
    assert client.post(f"/api/risk-budget/requests/{cr['id']}/decisions", headers=h,
                       json={"role": "portfolio_manager", "decision": "approve", "reason": "self approve attempt"}).status_code == 400
    h3 = login(client, "Sam PM2", "portfolio_manager")
    client.post(f"/api/risk-budget/requests/{cr['id']}/decisions", headers=h3,
                json={"role": "portfolio_manager", "decision": "approve", "reason": "Agree with the change."})
    h2 = login(client, "Riley Risk", "risk")
    out = client.post(f"/api/risk-budget/requests/{cr['id']}/decisions", headers=h2,
                      json={"role": "risk", "decision": "approve", "reason": "Risk agrees with tightening."}).json()
    assert out["status"] == "applied"
    ov = client.get("/api/export/policy-overrides", headers={"Authorization": "Bearer test-ingest-token"}).json()
    assert ov == {"risk_budgets.vintages.2050": 0.01}
    pos = client.get("/api/export/positions.csv", headers={"Authorization": "Bearer test-ingest-token"}).text
    assert "approved" in pos

    # audit evidence export restricted
    assert client.get(f"/api/runs/{rid}/evidence").status_code == 403
    login(client, "Avery Audit", "audit")
    ev = client.get(f"/api/runs/{rid}/evidence")
    assert ev.status_code == 200 and ev.json()["integrity"]["ok"]


def test_risk_history_export(client, run_dir):
    client.post("/api/ingest", headers={"Authorization": "Bearer test-ingest-token"},
                files={"bundle": ("b.tgz", bundle(run_dir))})
    assert client.get("/api/export/risk-history.csv").status_code == 401
    r = client.get("/api/export/risk-history.csv", headers={"Authorization": "Bearer test-ingest-token"})
    assert r.status_code == 200
    import pandas as pd
    df = pd.read_csv(io.StringIO(r.text))
    assert {"total_risk", "active_var", "factor:equity", "factor:specific"} <= set(df["metric"]) and df["vintage"].nunique() == 9


def test_origin_verify_blocks_direct_access(client, monkeypatch):
    monkeypatch.setenv("ORIGIN_VERIFY", "s3cret")
    assert client.get("/login").status_code == 403
    assert client.get("/login", headers={"x-origin-verify": "s3cret"}).status_code == 200
    assert client.get("/healthz").status_code == 200


def test_no_role_page(client):
    login(client, "Nobody")
    assert client.get("/runs/latest").status_code == 403


def test_ledger_is_append_only_in_database(tmp_path):
    """Decision records can be added but never changed or deleted, even with direct SQL (doc 05 §3)."""
    import pytest as _pt
    from sqlalchemy import text
    from sqlalchemy.exc import DatabaseError
    from meridian.app.store import Store
    st = Store(f"sqlite:///{tmp_path}/ledger.db")
    Store(f"sqlite:///{tmp_path}/ledger.db")          # second start-up: triggers are idempotent
    with st.engine.begin() as c:
        c.execute(text("INSERT INTO ledger_records (run_id, seq, dr_id, record, record_hash) "
                       "VALUES ('r1', 0, 'dr_1', '{}', 'h')"))
    for sql in ("UPDATE ledger_records SET record_hash='x'", "DELETE FROM ledger_records"):
        with _pt.raises(DatabaseError, match="append-only"):
            with st.engine.begin() as c:
                c.execute(text(sql))
    with st.engine.begin() as c:
        assert c.execute(text("SELECT record_hash FROM ledger_records")).scalar() == "h"


def test_placeholder_role_holder_never_fills_a_required_role():
    from meridian.entities import resolve
    reg = resolve(["sec_ria"], profile={"human_roles": {"chief_compliance_officer": {"name": "Robert Hayes", "placeholder": True},
                                                         "portfolio_manager": "Real Person"}})
    assert "chief_compliance_officer" in reg.unfilled_roles
    assert "portfolio_manager" not in reg.unfilled_roles
    assert "fictional placeholder" in reg.holder_label("chief_compliance_officer")
    assert any("placeholder: Robert Hayes" in b for b in reg.production_blockers)
